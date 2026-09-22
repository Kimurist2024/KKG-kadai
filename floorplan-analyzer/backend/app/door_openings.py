"""共有ドアの床を配分する。輪郭と壁・重複の幾何計算には介入しない。"""
from .schemas import AnalyzeResponse, DoorOpeningTransfer


def opening_geometry(rooms, doors=None):
    """部屋ごとに door_id -> (相手の index, 共通幅 px, 符号) を保持する。

    部屋 id の重複があっても別の部屋として数え、複数辺の区間幅を合算する。
    併合区間の幅は ids 全体で一度だけ数える。複数 id には response.doors の
    length_px に比例して配分し、doors を省略した既定の呼び出しでは等分する。
    id 昇順の最後に残差を割り当て（合計は区間の幅に丸め誤差の範囲で一致）、
    単一 id の幅には配分の演算を加えない。
    向きは補正前の px² だけから決め、縮尺・奥行きには依存しない。
    """
    lengths = {door.id: door.length_px for door in doors} if doors is not None else None
    widths = {}
    for index, room in enumerate(rooms):
        for edge in room.edges:
            for interval in edge.door_intervals:
                ids = sorted(interval.ids)
                if len(ids) > 1:
                    total = sum(lengths[door_id] for door_id in ids) if lengths is not None else len(ids)
                    allocated = 0.0
                for position, door_id in enumerate(ids):
                    if len(ids) == 1:
                        width = interval.length_px
                    elif position == len(ids) - 1:
                        width = interval.length_px - allocated
                    else:
                        weight = lengths[door_id] if lengths is not None else 1
                        width = interval.length_px * weight / total
                        allocated += width
                    per_room = widths.setdefault(door_id, {})
                    per_room[index] = per_room.get(index, 0.0) + width
    result = [{} for _ in rooms]
    for door_id in sorted(widths):
        per_room = widths[door_id]
        if len(per_room) != 2:
            continue
        first, second = sorted(per_room, key=lambda i: (-rooms[i].floor_area_px2, rooms[i].id))
        width = min(per_room.values())
        result[first][door_id] = (second, width, -1)
        result[second][door_id] = (first, width, 1)
    return result


def apply_openings(response, geometry, settings):
    """cold/直接計算のモデルと warm の辞書を同じ演算順序で換算する。

    全ての経路で重複面積の集計後に呼ぶ。キャッシュに保存する幾何値は変更しない。
    """
    models = isinstance(response, AnalyzeResponse)
    rooms = [r.__dict__ for r in response.rooms] if models else response["rooms"]
    summary = response.summary.__dict__ if models else response["summary"]
    mpp, depth = settings.meters_per_px, settings.door_opening_depth_m
    adjusted_count = 0
    for room, openings in zip(rooms, geometry):
        raw = room["floor_area_px2"] * mpp * mpp
        transfers = []
        adjustment = 0.0
        if depth != 0:
            # opening_geometry の door_id 昇順を JSON キャッシュも保持する。
            for door_id, (other_index, width_px, direction) in openings.items():
                other = rooms[other_index]
                width_m = width_px * mpp
                area = width_m * depth * direction
                adjustment += area
                transfer = dict(door_id=int(door_id), other_room_id=other["id"],
                                other_room_name=other["name"], width_m=width_m, area_m2=area)
                transfers.append(DoorOpeningTransfer(**transfer) if models else transfer)
        room["floor_area_raw_m2"] = raw
        room["floor_area_m2"] = raw + adjustment if transfers else raw
        room["door_opening_adjustment_m2"] = adjustment
        room["door_opening_transfers"] = transfers
        adjusted_count += bool(transfers)
    summary["total_floor_area_m2"] = sum(r["floor_area_m2"] for r in rooms)
    summary["door_opening_adjusted_room_count"] = adjusted_count
