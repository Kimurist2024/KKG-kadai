"""幾何計算だけを再利用し、縮尺・高さの変更時は換算と集計をやり直す。

画像やファイルは保存しない。キャッシュが空でも通常どおり計算できる。
"""
import hashlib
import json
import threading
import time
from collections import OrderedDict
from pydantic_core import to_json

from .schemas import AnalyzeResponse, AnalysisSettings, GeometryProcessing, Vertex, Warning
from .door_openings import apply_openings


class GeometryCache:
    """容量・件数・期限を制限したプロセス内 LRU キャッシュ。

    JSON bytes を保存し、読み出し時に復元することでレスポンス同士の変更を分離する。
    get/put/clear はロックで保護するが、幾何計算中はロックを保持しない。"""

    def __init__(self, max_bytes=16 * 1024 * 1024, max_entries=8, ttl=300):
        self.max_bytes, self.max_entries, self.ttl = max_bytes, max_entries, ttl
        self._entries = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def clear(self):
        with self._lock:
            self._entries.clear()
            self._bytes = 0

    def _expire(self, now):
        for key, (created, value) in list(self._entries.items()):
            if now - created >= self.ttl:
                self._bytes -= len(value)
                del self._entries[key]

    def get(self, key):
        with self._lock:
            self._expire(time.monotonic())
            entry = self._entries.get(key)
            if entry is None:
                return None
            self._entries.move_to_end(key)
            return entry[1]

    def put(self, key, value):
        if len(value) > self.max_bytes:
            return
        with self._lock:
            now = time.monotonic()
            self._expire(now)
            previous = self._entries.pop(key, None)
            if previous is not None:
                self._bytes -= len(previous[1])
            self._entries[key] = (now, value)
            self._bytes += len(value)
            while self._bytes > self.max_bytes or len(self._entries) > self.max_entries:
                _, (_, removed) = self._entries.popitem(last=False)
                self._bytes -= len(removed)


cache = GeometryCache()


def get_geometry(mask, geometry_key, compute, *compute_args):
    """輪郭と幾何計算条件をキーに結果を取得する。"""
    # 穴・id・名前・元の面積等もキーに含める。画像と表示メタデータは再利用しない。
    source = mask.model_dump_json(exclude={"image_data", "timestamp", "image_width", "image_height"})
    key = hashlib.sha256(("geometry-v2:" + str(geometry_key) + ":" + source).encode()).digest()
    stored = cache.get(key)
    if stored is not None:
        return json.loads(stored)
    geometry = compute(*compute_args)
    # 画像情報・日時・設定は保存せず、warm の materialize で付け直す。
    # 既存依存のネイティブ serializer を利用。復元は従来の json.loads のまま。
    stored = to_json(geometry, inf_nan_mode="constants",
                     exclude={"response": {"image", "timestamp", "settings"}})
    cache.put(key, stored)
    return geometry


def materialize(geometry, mask, settings):
    """今回の設定で実寸を再計算し、API レスポンスを組み立てる。

    get_geometry が返すリクエスト専用の辞書を更新する。単位縮尺で保存した
    overlap/union の *_m2 もここでは px²。換算前の辞書を繰り返し渡してはいけない。
    浮動小数点の結果を変えないよう、analyzer と加算・乗算の順番を揃える。
    """
    if isinstance(geometry["response"], AnalyzeResponse):
        response = _materialize_response(geometry["response"], geometry["pairs"], settings)
        apply_openings(response, geometry["door_openings"], settings)
        return response
    data = geometry["response"]
    mpp = settings.meters_per_px
    # 1. 区間 → 辺 → 部屋の順で換算する。先に集約してから掛けると丸め差が出る。
    for room in data["rooms"]:
        room["floor_area_m2"] = room["floor_area_px2"] * mpp * mpp
        room["perimeter_m"] = room["perimeter_px"] * mpp
        for edge in room["edges"]:
            edge["length_m"] = edge["length_px"] * mpp
            for kind in ("wall", "opening", "door", "inferred_wall"):
                for iv in edge[kind + "_intervals"]:
                    iv["length_m"] = iv["length_px"] * mpp
            for kind in ("wall", "opening", "door"):
                edge[kind + "_length_m"] = sum(iv["length_px"] for iv in edge[kind + "_intervals"]) * mpp
            edge["wall_area_gross_m2"] = edge["wall_length_m"] * settings.ceiling_height_m
            edge["door_area_m2"] = edge["door_length_m"] * settings.door_height_m
            edge["wall_area_m2"] = edge["wall_area_gross_m2"] - edge["door_area_m2"]
        for field in ("wall_length_m", "opening_length_m", "door_length_m",
                      "wall_area_gross_m2", "door_area_m2"):
            room[field] = sum(edge[field] for edge in room["edges"])
        room["wall_area_m2"] = room["wall_area_gross_m2"] - room["door_area_m2"]
    # 2. 描画用の元線分と、重複領域の面積・警告を実寸に合わせる。
    for segment in data["walls"] + data["doors"]:
        segment["length_m"] = segment["length_px"] * mpp
    for overlap, (i, j) in zip(data["overlaps"], geometry["pairs"]):
        overlap["area_m2"] = overlap["area_m2"] * mpp * mpp
        for a, b in ((i, j), (j, i)):
            first, second = data["rooms"][a], data["rooms"][b]
            data["warnings"].append(dict(code="room_overlap", contour_id=first["id"],
                message=f"部屋 '{first['name']}' と '{second['name']}' の床領域が {overlap['area_m2']:.4f} m² 重複しています。部屋別面積は自動で削減していません。"))
    # 3. 全体を再集計し、今回のファイル情報を付ける。
    summary = data["summary"]
    summary["total_floor_area_m2"] = sum(r["floor_area_m2"] for r in data["rooms"])
    summary["union_floor_area_m2"] = summary["union_floor_area_m2"] * mpp * mpp
    summary["overlap_floor_area_m2"] = max(0.0, summary["total_floor_area_m2"] - summary["union_floor_area_m2"]) if data["overlaps"] else 0.0
    summary["total_wall_area_m2"] = sum(r["wall_area_m2"] for r in data["rooms"])
    apply_openings(data, geometry["door_openings"], settings)
    data["settings"] = settings.model_dump()
    data["timestamp"] = mask.timestamp
    data["image"] = dict(width=mask.image_width, height=mask.image_height,
                         mime_type=mask.image_data.mime_type if mask.image_data else None,
                         has_image=bool(mask.image_data and mask.image_data.base64))
    return AnalyzeResponse.model_validate(data)


def _materialize_response(response, pairs, settings):
    """cold の検証済み実寸モデルに重複情報を付ける。保存済み bytes は変更しない。

    __dict__ はこの応答だけの計算済み数値の更新に使う。公開スキーマの検証や
    default は通常のモデル生成時に適用済み。辺・部屋の実寸は core で計算済みで、
    演算順序は materialize と同じ。重複・和集合だけは保存用 px² から換算する。
    入力由来の頂点はコピーし、従来の辞書往復と同様に入力から切り離す。
    """
    mpp = settings.meters_per_px
    for room in response.rooms:
        room.__dict__["vertices"] = [Vertex(x=vertex.x, y=vertex.y) for vertex in room.vertices]
    # 辞書往復では default も明示フィールドになる。exclude_unset の挙動を維持。
    for warning in response.warnings:
        warning.model_fields_set.add("contour_id")
    if response.geometry_processing is not None:
        response.geometry_processing = GeometryProcessing.model_validate(
            response.geometry_processing.model_dump(mode="json"))
    for overlap, (i, j) in zip(response.overlaps, pairs):
        overlap.__dict__["area_m2"] = overlap.area_m2 * mpp * mpp
        for a, b in ((i, j), (j, i)):
            first, second = response.rooms[a], response.rooms[b]
            response.warnings.append(Warning(code="room_overlap", contour_id=first.id,
                message=f"部屋 '{first.name}' と '{second.name}' の床領域が {overlap.area_m2:.4f} m² 重複しています。部屋別面積は自動で削減していません。"))
    summary = response.summary.__dict__
    summary["union_floor_area_m2"] = summary["union_floor_area_m2"] * mpp * mpp
    summary["overlap_floor_area_m2"] = max(0.0, summary["total_floor_area_m2"] - summary["union_floor_area_m2"]) if response.overlaps else 0.0
    response.settings = AnalysisSettings.model_validate(settings.model_dump())
    return response
