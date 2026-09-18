import type { AnalyzeResponse, Settings } from "./types";

const BASE = ""; // Next.js のサーバー側プロキシを経由する。

/** HTTP ステータスと利用者向けメッセージを保持する通信エラー。status=0 は接続失敗。 */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function settingsToQuery(settings: Settings): string {
  const p = new URLSearchParams();
  (Object.keys(settings) as (keyof Settings)[]).forEach((k) => p.set(k, String(settings[k])));
  return p.toString();
}

async function extractMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail.message === "string") {
      const first = Array.isArray(detail.errors) && detail.errors[0];
      const loc = first ? ` (${first.loc?.join(".")}: ${first.msg})` : "";
      return detail.message + loc;
    }
    if (Array.isArray(detail) && detail[0]?.msg) {
      return `${detail[0].loc?.join(".")}: ${detail[0].msg}`;
    }
    return JSON.stringify(body);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

/** JSON ファイルを multipart でアップロードして解析結果を取得する。 */
export async function analyzeFile(
  file: File,
  settings: Settings,
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file, file.name);
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/analyze?${settingsToQuery(settings)}`, {
      method: "POST",
      body: form,
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "バックエンド API に接続できません。uvicorn が起動しているか確認してください。");
  }
  if (!res.ok) throw new ApiError(res.status, await extractMessage(res));
  return (await res.json()) as AnalyzeResponse;
}
