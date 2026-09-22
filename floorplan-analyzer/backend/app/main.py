"""FastAPI アプリケーション。

エンドポイント:
  GET  /                      案内 (画面はフロントエンド側にあります)
  GET  /api/health            疎通確認
  GET  /api/defaults          計算パラメータの既定値
  POST /api/analyze           JSON ファイルをアップロードして解析 (multipart/form-data)
  POST /api/analyze/json      JSON をリクエストボディとして送って解析 (application/json)
"""
from __future__ import annotations

import json
import os
from typing import Literal, Optional, Union

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .analyzer import analyze
from .schemas import AnalysisSettings, AnalyzeJsonRequest, AnalyzeResponse, MaskFile

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))

app = FastAPI(
    title="Floor Plan Mask Analyzer API",
    description="平面図のセグメンテーション結果 (部屋・壁・ドア) から床面積・周長・壁面積を算出します。",
    version="1.0.0",
)

allowed_origins = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validation_details(exc):
    """JSON 化できない NaN 等の入力値を除き、場所・理由・種類だけを返す。"""
    return [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """検証エラーの "input" には NaN 等 JSON 化できない値が入り得るので、位置とメッセージだけ返す。"""
    errors = _validation_details(exc)
    return JSONResponse(status_code=422, content={"detail": errors})


def settings_from_query(
    ceiling_height_m: float = Query(2.4, gt=0, description="天井高 (m)"),
    door_height_m: float = Query(2.0, ge=0, description="ドア高さ (m)"),
    door_opening_depth_m: float = Query(0.126, ge=0, le=1.0, description="ドア開口部の床を隣室へ移す奥行き (m)。0 で補正なし"),
    scale_px: float = Query(96.7, gt=0, description="スケール基準 px"),
    scale_m: float = Query(1.365, gt=0, description="スケール基準 m"),
    tolerance_px: float = Query(10.0, ge=0, description="壁/ドアの辺への許容距離 (px)"),
    geometry_mode: Literal["raw", "regularized_shared"] = Query("raw", description="幾何補正モード"),
    boundary_reference: Literal["unknown", "centerline", "inner_face"] = Query("unknown", description="部屋輪郭の基準"),
) -> AnalysisSettings:
    try:
        return AnalysisSettings(
            ceiling_height_m=ceiling_height_m,
            door_height_m=door_height_m,
            door_opening_depth_m=door_opening_depth_m,
            scale_px=scale_px,
            scale_m=scale_m,
            tolerance_px=tolerance_px,
            geometry_mode=geometry_mode,
            boundary_reference=boundary_reference,
        )
    except ValidationError as e:  # 相関チェック (ドア高 ≤ 天井高) も 422 で返す
        raise HTTPException(status_code=422, detail=[err["msg"] for err in e.errors()]) from e


def _parse_mask(raw: bytes) -> MaskFile:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="ファイルサイズが上限を超えています")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"JSON として解釈できません: {e}") from e
    try:
        return MaskFile.model_validate(data)
    except ValidationError as e:
        # "input" には NaN 等 JSON 化できない値が入り得るので、位置とメッセージだけ返す
        errors = _validation_details(e)
        raise HTTPException(
            status_code=422,
            detail={"message": "JSON の形式が課題のデータ構造と一致しません", "errors": errors},
        ) from e


def _parse_and_analyze(raw: bytes, settings: AnalysisSettings) -> AnalyzeResponse:
    """JSON解析と幾何計算を同じワーカースレッドで実行する。"""
    return analyze(_parse_mask(raw), settings)


@app.get("/", include_in_schema=False)
def root() -> dict:
    """API サーバー直下を開いた人向けの案内 (画面はフロントエンド側)。"""
    return {
        "message": "これは API サーバーです。画面はフロントエンド (npm run dev → http://localhost:5173) で開いてください。",
        "docs": "/docs",
        "health": "/api/health",
        "analyze": "POST /api/analyze (multipart, field 'file')",
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/defaults", response_model=AnalysisSettings)
def defaults() -> AnalysisSettings:
    return AnalysisSettings()


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_upload(
    file: UploadFile = File(..., description="部屋・壁・ドアマスク JSON"),
    settings: AnalysisSettings = Depends(settings_from_query),
) -> AnalyzeResponse:
    raw = await file.read(MAX_UPLOAD_BYTES + 1)  # 上限を超える分は読み込まない
    # JSON 解析と幾何計算は同期処理なので、イベントループを塞がないようスレッドプールで実行
    return await run_in_threadpool(_parse_and_analyze, raw, settings)


@app.post("/api/analyze/json", response_model=AnalyzeResponse)
def analyze_body(
    mask: Union[AnalyzeJsonRequest, MaskFile],
    settings: AnalysisSettings = Depends(settings_from_query),
) -> AnalyzeResponse:
    if isinstance(mask, AnalyzeJsonRequest):
        return analyze(mask.mask, mask.settings)
    return analyze(mask, settings)
