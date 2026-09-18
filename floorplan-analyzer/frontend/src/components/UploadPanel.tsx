import { useRef, useState, type DragEvent } from "react";

interface Props {
  fileName: string | null;
  loading: boolean;
  onFile: (file: File) => void;
  onLoadSample: () => void;
  compact?: boolean;
  isSample?: boolean;
}

/** ファイル選択。ドロップ領域は通常のコンテナで、操作は独立したボタンで行う (入れ子ボタンを避ける)。 */
export default function UploadPanel({ fileName, loading, onFile, onLoadSample, compact, isSample = false }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };

  const input = (
    <input
      ref={inputRef}
      type="file"
      accept=".json,application/json"
      hidden
      onChange={(e) => {
        const f = e.target.files?.[0];
        if (f) onFile(f);
        e.target.value = "";
      }}
    />
  );

  return (
    <div
      className={`dropzone ${dragging ? "dragging" : ""} ${compact ? "compact" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      // 子要素の上を通過しただけでは解除しない（枠の外へ出たときだけ）
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false); }}
      onDrop={handleDrop}
    >
      {input}
      {compact ? (
        <div className="dropzone-compact-row">
          <span className="dropzone-icon" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M14 3H5v18h14V8zM14 3v5h5M8 12h8M8 16h8" /></svg></span>
          <span className="dropzone-file">{fileName ?? (loading ? "サンプル図面を読み込み中…" : "ファイル未選択")}</span>
          {/* 初回の自動読込中は「待てばよい」ことを、完了後はドロップでも読み込めることを伝える */}
          <span className="muted small dropzone-drop-hint">{loading ? "完了すると図面と結果表が下に表示されます" : "JSON をこの行にドロップしても読み込めます"}</span>
          <span className="spacer" />
          <button type="button" className="btn btn-primary" disabled={loading} onClick={() => inputRef.current?.click()}>
            {fileName ? "別の JSON を選択" : "JSON ファイルを選択"}
          </button>
          {isSample ? <span className="file-badge">サンプル表示中</span> : !loading && <button type="button" className="btn btn-secondary" onClick={onLoadSample}>
            サンプルを読み込む
          </button>}
        </div>
      ) : (
        <div className="dropzone-body">
          <div className="dropzone-icon big" aria-hidden="true"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M12 15V4M8 8l4-4 4 4M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" /></svg></div>
          {/* 初期画面の文字は最小限に。強調するのは見出しと主ボタンだけ（形式の詳細は折りたたみの中） */}
          <h2 className="dropzone-title">{dragging ? "ここにドロップして解析" : "JSON をドロップして面積を計算"}</h2>
          <p className="dropzone-lead">部屋ごとの床面積・周長・壁面積を求めます</p>
          <div className="dropzone-actions">
            <button type="button" className="btn btn-primary btn-lg" disabled={loading} onClick={() => inputRef.current?.click()}>
              JSON ファイルを選択
            </button>
            <button type="button" className="btn btn-secondary btn-lg" disabled={loading} onClick={onLoadSample}>
              サンプルで試す
            </button>
          </div>
          <p className="sr-only" aria-live="polite">{dragging ? "ファイルをドロップできます" : ""}</p>
          <details className="dropzone-details">
            <summary>入力形式について</summary>
            <p>
              <code>contours</code>（部屋の多角形、壁・ドアの線分）と <code>image_data</code>（元画像の Base64）、
              <code>image_width</code> / <code>image_height</code> を含む JSON。セグメンテーション結果の出力形式そのままで読み込めます。
            </p>
          </details>
        </div>
      )}
    </div>
  );
}
