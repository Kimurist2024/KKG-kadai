import { useCallback, useEffect, useRef, useState } from "react";
import { analyzeFile } from "../api";
import { DEFAULT_SETTINGS, type AnalyzeResponse, type Settings } from "../types";

export type Status = { state: "idle" } | { state: "loading" } | { state: "error"; message: string };

/** 解析が完了した図面と、その結果に対応する表示データ。 */
interface Snapshot {
  file: File;
  isSample: boolean;
  imageUrl: string | null;
  result: AnalyzeResponse;
  settings: Settings;
}

/**
 * アップロードされた JSON から元画像 (base64) を取り出して data URL にする。
 * ファイル自体はそのままバックエンドへ送るが、画像はレスポンスに含まれないのでここで取り出す。
 */
async function extractImageUrl(file: File): Promise<string | null> {
  try {
    const data = JSON.parse(await file.text());
    const b64 = data?.image_data?.base64;
    if (typeof b64 !== "string" || !b64) return null;
    const mime = typeof data.image_data.mime_type === "string" ? data.image_data.mime_type : "image/png";
    return b64.startsWith("data:") ? b64 : `data:${mime};base64,${b64}`;
  } catch {
    return null; // 解釈できない場合はバックエンドがエラーを返すのでここでは無視
  }
}

/**
 * ファイル・計算条件・解析結果と、バックエンド呼び出しをまとめたフック。
 * 画面の見た目に関する状態 (選択・ホバー・レイヤー) は持たない。
 *
 * 競合対策: 操作ごとに世代番号を進め、古い操作の完了は無視する。
 * ファイル・画像・結果は 1 つのスナップショットとして同時に確定するので、
 * 「新しい画像に古い結果が重なる」状態は起きない。
 */
export function useAnalysis() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [status, setStatus] = useState<Status>({ state: "idle" });
  const [updatedAt, setUpdatedAt] = useState<number | null>(null); // 直近の解析完了時刻 (完了通知用)
  const generation = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []); // アンマウント時に中断

  /** 操作の開始: 世代を進め、進行中のリクエストを中断する */
  const beginOperation = useCallback(() => {
    const id = ++generation.current;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus({ state: "loading" });
    return {
      id,
      signal: controller.signal,
      isCurrent: () => id === generation.current && !controller.signal.aborted,
    };
  }, []);

  type Operation = ReturnType<typeof beginOperation>;

  /** 同じ操作の中で画像取得と解析を待ち、最新の操作だけを表示に反映する。 */
  const analyzeWithinOperation = useCallback(async (
    operation: Operation,
    file: File,
    settings: Settings,
    imageUrlPromise?: Promise<string | null>,
    isSample = false,
  ) => {
    try {
      const [imageUrl, result] = await Promise.all([
        imageUrlPromise ?? Promise.resolve(null),
        analyzeFile(file, settings, operation.signal),
      ]);
      if (!operation.isCurrent()) return;
      const { ceiling_height_m, door_height_m, scale_px, scale_m, tolerance_px } = result.settings;
      setSnapshot((prev) => ({
        file,
        isSample,
        imageUrl: imageUrlPromise ? imageUrl : prev?.imageUrl ?? null,
        result,
        settings: {
          ceiling_height_m, door_height_m, scale_px, scale_m, tolerance_px,
          geometry_mode: result.settings.geometry_mode ?? settings.geometry_mode,
          boundary_reference: result.settings.boundary_reference ?? settings.boundary_reference,
        }, // サーバーが実際に適用した値
      }));
      setStatus({ state: "idle" });
      setUpdatedAt(Date.now());
    } catch (e) {
      if (!operation.isCurrent()) return;
      setStatus({ state: "error", message: (e as Error).message });
    }
  }, []);

  const loadFile = useCallback(async (file: File) => {
    const operation = beginOperation();
    await analyzeWithinOperation(operation, file, DEFAULT_SETTINGS, extractImageUrl(file));
  }, [beginOperation, analyzeWithinOperation]);

  const loadSample = useCallback(async () => {
    const operation = beginOperation(); // 取得中も同じ世代で管理し、後から選ばれたファイルを上書きしない
    try {
      const res = await fetch("/sample_mask.json", { signal: operation.signal });
      if (!res.ok) throw new Error(`サンプルの取得に失敗しました (HTTP ${res.status})`);
      const blob = await res.blob();
      if (!operation.isCurrent()) return;
      const file = new File([blob], "sample_mask.json", { type: "application/json" });
      await analyzeWithinOperation(operation, file, DEFAULT_SETTINGS, extractImageUrl(file), true);
    } catch (e) {
      if (!operation.isCurrent()) return;
      setStatus({ state: "error", message: (e as Error).message });
    }
  }, [beginOperation, analyzeWithinOperation]);

  const appliedSettings = snapshot?.settings ?? DEFAULT_SETTINGS;

  return {
    file: snapshot?.file ?? null,
    isSample: snapshot?.isSample ?? false,
    imageUrl: snapshot?.imageUrl ?? null,
    result: snapshot?.result ?? null,
    appliedSettings,
    status,
    updatedAt,
    loadFile,
    loadSample,
  };
}
