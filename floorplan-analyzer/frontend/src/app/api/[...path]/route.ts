// Runtime proxy: one immutable frontend image can target different FastAPI hosts.
// Only the application's public endpoints are exposed through this route.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

type Context = { params: Promise<{ path: string[] }> };
const endpoints: Record<string, string> = {
  health: "GET",
  defaults: "GET",
  "ai/status": "GET",
  analyze: "POST",
  "analyze/json": "POST",
  recognize: "POST",
};

async function proxy(request: Request, context: Context): Promise<Response> {
  const { path } = await context.params;
  const endpoint = path.join("/");
  if (!Object.hasOwn(endpoints, endpoint)) {
    return Response.json({ detail: "API が見つかりません。" }, { status: 404 });
  }
  if (request.method !== endpoints[endpoint]) {
    return Response.json({ detail: "許可されていないメソッドです。" }, { status: 405 });
  }
  const headers = new Headers();
  for (const name of ["content-type", "x-ai-token"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  // Stream uploads instead of buffering JSON/image bodies twice in the frontend.
  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    cache: "no-store",
    redirect: "error",
    signal: AbortSignal.any([request.signal, AbortSignal.timeout(120_000)]),
  };
  if (request.method === "POST") {
    init.body = request.body;
    init.duplex = "half";
  }
  try {
    const target = new URL(`/api/${endpoint}`, process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000");
    target.search = new URL(request.url).search;
    const upstream = await fetch(target, init);
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return Response.json({ detail: "解析サーバーに接続できませんでした。しばらくしてから再試行してください。" }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
