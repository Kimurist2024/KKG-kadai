"use client";

import { useEffect, useRef, useState } from "react";
import { recognizeImage } from "../api";
import { downloadText } from "../format";
import type { RecognitionResponse } from "../types";

/** 画像送信への同意と候補輪郭の照合を経て、課題の固定条件で解析する。 */
export default function AiImportPanel({ onFile, disabled }: { onFile: (file: File) => void; disabled: boolean }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [token, setToken] = useState("");
  const [consent, setConsent] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<RecognitionResponse | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  const cancel = () => {
    controller.current?.abort();
    controller.current = null;
    setBusy(false);
  };
  const run = async () => {
    if (!file || !token.trim() || !consent || disabled || busy) return;
    cancel();
    const ctrl = new AbortController();
    controller.current = ctrl;
    setBusy(true); setError(""); setResult(null); setConfirmed(false);
    try {
      const next = await recognizeImage(file, token.trim(), ctrl.signal);
      if (ctrl.signal.aborted) return;
      setResult(next);
    } catch (e) {
      if (!ctrl.signal.aborted) setError(e instanceof Error ? e.message : "画像認識に失敗しました。");
    } finally {
      if (controller.current === ctrl) setBusy(false);
    }
  };
  const json = result ? JSON.stringify(result.mask, null, 2) : "";
  const filename = `${file?.name.replace(/\.[^.]+$/, "") ?? "drawing"}.ai-mask.json`;
  const source = result?.mask.image_data;
  const imageUrl = source ? `data:${source.mime_type};base64,${source.base64}` : "";

  return <div className="ai-import">
    <button type="button" className="btn" disabled={disabled} aria-expanded={open} onClick={() => { if (open) cancel(); setOpen(!open); }}>
      {open ? "画像からの AI 認識を閉じる" : "画像から AI で輪郭を作成"}
    </button>
    {open && <section className="ai-input-section" aria-labelledby="ai-import-heading">
      <p className="section-kicker">新しい図面の入力 · AI 認識</p>
      <h2 id="ai-import-heading">図面画像から輪郭を作成</h2>
      <p>PNG・JPEG の図面から、部屋・壁・ドアの候補を作ります。認識結果を確認した後に、課題指定の固定条件で面積を計算します。</p>
      <p className="status warn">縮尺は 96.7 px ＝ 1.365 m 固定です。縮尺が異なる画像や拡大・縮小した画像では、実際の面積・長さと一致しません。</p>
      <p className="muted">画像はサーバー経由で OpenAI に送信されます。AI の見落としや位置ずれがあるため、結果は参考値として扱ってください。</p>
      <label className="ai-field">図面画像（10 MB 以下）
        <input type="file" accept="image/png,image/jpeg,.png,.jpg,.jpeg" disabled={busy || disabled} onChange={(e) => {
          cancel(); setResult(null); setConfirmed(false); setConsent(false); setError("");
          const next = e.target.files?.[0] ?? null;
          if (next && next.size > 10 * 1024 * 1024) { setFile(null); setError("画像は 10 MB 以下にしてください。"); }
          else setFile(next);
        }} />
      </label>
      <label className="ai-field">AI 利用トークン
        <input type="password" autoComplete="off" value={token} disabled={busy} onChange={(e) => setToken(e.target.value)} aria-describedby="ai-token-help" />
      </label>
      <p id="ai-token-help" className="muted">サイト管理者から受け取った利用トークンを入力してください。OpenAI の API キーは入力しません。トークンはこの画面を離れると破棄されます。</p>
      <label className="scale-confirm-check"><input type="checkbox" checked={consent} disabled={busy} onChange={(e) => setConsent(e.target.checked)} />この画像を OpenAI に送信して認識する</label>
      <button type="button" className="btn btn-primary" disabled={disabled || busy || !file || !token.trim() || !consent} onClick={() => void run()}>AI で輪郭を認識</button>
      {busy && <><p role="status">画像を認識しています…</p><button type="button" className="btn" onClick={cancel}>認識の待機を取り消す</button><p className="muted">送信済みの処理は、待機を取り消しても API 利用料が発生する場合があります。</p></>}
      {error && <p className="status error" role="alert">{error}</p>}
      {result && <div className="ai-review">
        <h3>認識した輪郭を確認</h3>
        <p>部屋は青、壁は赤、ドアは緑です。位置・境界・見落としを図面と照合してください。元画像は {result.mask.image_width} × {result.mask.image_height} px です。</p>
        <div className="scale-preview">
          <svg viewBox={`0 0 ${result.mask.image_width} ${result.mask.image_height}`} role="img" aria-label="元画像に重ねた AI の認識候補" style={{ display: "block", width: "100%" }}>
            <image href={imageUrl} width={result.mask.image_width} height={result.mask.image_height} />
            {result.mask.contours.map((c) => c.isLine ?
              <polyline key={c.id} points={c.vertices.map((v) => `${v.x},${v.y}`).join(" ")} fill="none" stroke={c.label_id === 3 ? "#15803d" : "#b91c1c"} strokeWidth={3} vectorEffect="non-scaling-stroke"><title>{c.label_id === 3 ? "ドア" : "壁"} #{c.id}</title></polyline> :
              <polygon key={c.id} points={c.vertices.map((v) => `${v.x},${v.y}`).join(" ")} fill="#2563eb33" stroke="#1d4ed8" strokeWidth={2} vectorEffect="non-scaling-stroke"><title>{c.room_name ?? `部屋 #${c.id}`}</title></polygon>)}
          </svg>
        </div>
        <ul>{result.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        <p className="muted">認識に誤りがあれば、JSON を保存して輪郭座標を修正し、通常の JSON 選択から読み込めます。</p>
        <button type="button" className="btn" onClick={() => downloadText(filename, json, "application/json")}>認識した JSON を保存</button>
        <label className="scale-confirm-check"><input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />認識した部屋・壁・ドアの輪郭を図面と照合しました</label>
        <button type="button" className="btn btn-primary" disabled={!confirmed || disabled} onClick={() => {
          onFile(new File([json], filename, { type: "application/json" }));
          setOpen(false); setToken(""); setResult(null); setConfirmed(false);
        }}>この認識結果を解析</button>
      </div>}
    </section>}
  </div>;
}
