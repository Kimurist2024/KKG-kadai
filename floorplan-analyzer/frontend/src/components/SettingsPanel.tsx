import { useEffect, useState, type FormEvent } from "react";
import { DEFAULT_SETTINGS, type Settings } from "../types";

interface Props {
  /** 直近に適用された条件。下書きの初期値と「変更あり」判定に使う */
  applied: Settings;
  disabled: boolean;
  onApply: (s: Settings) => void;
  confirmScale?: boolean;
}

type NumericSettingKey = "ceiling_height_m" | "door_height_m" | "scale_px" | "scale_m" | "tolerance_px";
const LIMITS: Record<NumericSettingKey, { label: string; min: number; step: number }> = {
  ceiling_height_m: { label: "天井高", min: 0.01, step: 0.01 },
  door_height_m: { label: "ドア高さ", min: 0, step: 0.01 },
  scale_px: { label: "画像上の長さ", min: 0.1, step: 0.1 },
  scale_m: { label: "実寸", min: 0.001, step: 0.001 },
  tolerance_px: { label: "許容誤差", min: 0, step: 1 },
};

type Draft = Record<NumericSettingKey, string> & Pick<Settings, "geometry_mode" | "boundary_reference">;
const toDraft = (settings: Settings): Draft => ({
  ceiling_height_m: String(settings.ceiling_height_m),
  door_height_m: String(settings.door_height_m),
  scale_px: String(settings.scale_px),
  scale_m: String(settings.scale_m),
  tolerance_px: String(settings.tolerance_px),
  geometry_mode: settings.geometry_mode,
  boundary_reference: settings.boundary_reference,
});

/** 初回解析では前の図面の縮尺を使わせず、入力を空欄から始める。 */
function createDraft(settings: Settings, confirmScale: boolean): Draft {
  const draft = toDraft(settings);
  return confirmScale ? { ...draft, scale_px: "", scale_m: "", geometry_mode: "raw", boundary_reference: "unknown" } : draft;
}

/** 文字列の下書きを検証して Settings にする。問題があればエラーメッセージを返す。 */
function parseDraft(draft: Draft): { ok: true; value: Settings } | { ok: false; error: string } {
  const value = { geometry_mode: draft.geometry_mode, boundary_reference: draft.boundary_reference } as Settings;
  for (const key of Object.keys(LIMITS) as NumericSettingKey[]) {
    const limit = LIMITS[key];
    const number = Number(draft[key]);
    if (draft[key].trim() === "" || !Number.isFinite(number)) return { ok: false, error: `${limit.label} に数値を入力してください` };
    if (number < limit.min) return { ok: false, error: `${limit.label} は ${limit.min} 以上にしてください` };
    value[key] = number;
  }
  if (value.door_height_m > value.ceiling_height_m) return { ok: false, error: "ドア高さは天井高以下にしてください" };
  return { ok: true, value };
}

/** 計算条件の下書き・入力検証と、図面ごとの縮尺確認を担当するフォーム。 */
export default function SettingsPanel({ applied, disabled, onApply, confirmScale = false }: Props) {
  const [draft, setDraft] = useState<Draft>(() => createDraft(applied, confirmScale));
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 適用済み条件が変わったとき (別条件で再計算が完了したとき) だけ下書きを同期する
  useEffect(() => {
    setDraft(createDraft(applied, confirmScale));
    setConfirmed(false);
    setError(null);
  }, [applied, confirmScale]);

  const update = (key: NumericSettingKey, text: string) => {
    if (key === "scale_px" || key === "scale_m") setConfirmed(false);
    const next = { ...draft, [key]: text };
    setDraft(next); // 入力中の表記 ("2.40" など) はそのまま保持する
    const parsed = parseDraft(next);
    setError(parsed.ok ? null : parsed.error);
  };
  const reset = () => {
    setDraft(toDraft(DEFAULT_SETTINGS));
    setError(null);
  };

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const parsed = parseDraft(draft);
    if (!parsed.ok) {
      setError(parsed.error);
      return;
    }
    setError(null);
    if (confirmScale && !confirmed) return;
    onApply(parsed.value);
  };

  const parsed = parseDraft(draft);
  const dirty = parsed.ok && (
    (Object.keys(LIMITS) as NumericSettingKey[]).some((key) => parsed.value[key] !== applied[key])
    || parsed.value.geometry_mode !== applied.geometry_mode
    || parsed.value.boundary_reference !== applied.boundary_reference
  );
  const scalePx = Number(draft.scale_px);
  const scaleM = Number(draft.scale_m);
  const metersPerPixel = scalePx > 0 && Number.isFinite(scaleM) ? scaleM / scalePx : NaN;

  const numInput = (key: NumericSettingKey, width = 90) => (
    <input
      type="number"
      inputMode="decimal"
      step={LIMITS[key].step}
      min={LIMITS[key].min}
      value={draft[key]}
      disabled={disabled}
      aria-label={LIMITS[key].label}
      aria-invalid={!!error}
      aria-describedby="settings-error"
      style={{ width }}
      onChange={(e) => update(key, e.target.value)}
    />
  );

  return (
    <form className="settings" onSubmit={submit} noValidate>
      <div className="settings-grid">
        <div className="field">
          <span className="field-label">天井高</span>
          <span className="field-input">{numInput("ceiling_height_m")}<span className="unit">m</span></span>
          <span className="field-help">壁面積 ＝ 壁長 × 天井高</span>
        </div>
        <div className="field">
          <span className="field-label">ドア高さ</span>
          <span className="field-input">{numInput("door_height_m")}<span className="unit">m</span></span>
          <span className="field-help">ドア幅 × ドア高 を壁面積から控除</span>
        </div>
        <div className="field field-wide">
          <span className="field-label">スケール</span>
          <span className="field-input">
            画像上 {numInput("scale_px", 80)}<span className="unit">px</span>
            <span className="eq">＝</span>
            実寸 {numInput("scale_m", 80)}<span className="unit">m</span>
          </span>
          <span className="field-help">1 px = {Number.isFinite(metersPerPixel) ? metersPerPixel.toFixed(5) : "—"} m</span>
        </div>
      </div>
      <details className="settings-advanced">
        <summary>詳細設定</summary>
        <div className="field">
          <span className="field-label">壁判定の許容誤差</span>
          <span className="field-input">{numInput("tolerance_px")}<span className="unit">px</span></span>
          <span className="field-help">部屋の辺からこの距離以内にある壁・ドア線分を「その辺に沿う」とみなします。これより短い隙間は壁として補完します。</span>
        </div>
        {!confirmScale && <div className="field field-wide">
          <label className="scale-confirm-check">
            <input
              type="checkbox"
              checked={draft.geometry_mode === "regularized_shared"}
              disabled={disabled}
              onChange={(e) => setDraft((current) => ({
                ...current,
                geometry_mode: e.target.checked ? "regularized_shared" : "raw",
                boundary_reference: e.target.checked ? "centerline" : "unknown",
              }))}
            />
            図面の傾き・ずれを自動で整える
          </label>
          <span className="field-help">壁中心線の輪郭を前提に、方向をソフトに補正し、近い部屋境界を共有化します。適用が安全でない場合は元座標に戻します。</span>
        </div>}
      </details>
      {confirmScale && <label className="scale-confirm-check"><input type="checkbox" checked={confirmed} disabled={disabled} onChange={(e) => setConfirmed(e.target.checked)} />この図面の基準寸法と、元画像上のピクセル距離を確認しました</label>}
      <div className="settings-footer">
        {error && <span id="settings-error" className="error-text" role="alert">{error}</span>}
        {!confirmScale && !error && dirty && <span className="muted">変更は未反映です。「この条件で再計算」を押してください</span>}
        <span className="spacer" />
        {!confirmScale && <button type="button" className="btn btn-secondary" onClick={reset} disabled={disabled}>既定値に戻す</button>}
        <button type="submit" className="btn btn-primary" disabled={disabled || !parsed.ok || (confirmScale ? !confirmed : !dirty) || !!error}>{confirmScale ? "縮尺を確認して解析" : "この条件で再計算"}</button>
      </div>
    </form>
  );
}
