import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_defaults():
    d = client.get("/api/defaults").json()
    assert d["ceiling_height_m"] == 2.4 and d["scale_px"] == 96.7


def test_analyze_upload(sample_bytes):
    res = client.post(
        "/api/analyze",
        files={"file": ("mask.json", sample_bytes, "application/json")},
        params={"ceiling_height_m": 2.4},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["summary"]["room_count"] == 11
    assert body["image"]["width"] == 1024
    assert "base64" not in body["image"]  # 画像本体はレスポンスに含めない


def test_analyze_json_body(sample_json):
    res = client.post("/api/analyze/json", json=sample_json, params={"tolerance_px": 8})
    assert res.status_code == 200
    assert res.json()["settings"]["tolerance_px"] == 8


def test_invalid_json():
    res = client.post("/api/analyze", files={"file": ("x.json", b"{not json", "application/json")})
    assert res.status_code == 400


def test_wrong_schema():
    res = client.post("/api/analyze", files={"file": ("x.json", b'{"foo": 1}', "application/json")})
    assert res.status_code == 422


def test_bad_parameter():
    res = client.post("/api/analyze/json", json={"contours": [], "image_width": 1, "image_height": 1},
                      params={"ceiling_height_m": 0})
    assert res.status_code == 422


def test_root_guidance():
    res = client.get("/")
    assert res.status_code == 200 and "5173" in res.json()["message"]


def test_door_taller_than_ceiling_returns_422(sample_bytes):
    res = client.post(
        "/api/analyze",
        files={"file": ("mask.json", sample_bytes, "application/json")},
        params={"ceiling_height_m": 2.0, "door_height_m": 2.4},
    )
    assert res.status_code == 422
    assert "天井高" in res.text


@pytest.mark.parametrize("route", ["/api/analyze", "/api/analyze/json"])
def test_non_finite_vertex_is_rejected_on_both_routes(route):
    body = {"contours": [{"id": 1, "vertices": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}],
                          "label_id": 1}], "image_width": 10, "image_height": 10}
    body["contours"][0]["vertices"][0]["x"] = float("nan")
    raw = json.dumps(body).encode()  # Python の json は NaN を出力できる (JSON 仕様外)
    if route == "/api/analyze":
        res = client.post(route, files={"file": ("x.json", raw, "application/json")})
    else:
        res = client.post(route, content=raw, headers={"content-type": "application/json"})
    assert res.status_code == 422, res.text
    assert "detail" in res.json()


def test_upload_and_json_routes_agree(sample_bytes, sample_json):
    a = client.post("/api/analyze", files={"file": ("m.json", sample_bytes, "application/json")}).json()
    b = client.post("/api/analyze/json", json=sample_json).json()
    assert a["rooms"] == b["rooms"]
