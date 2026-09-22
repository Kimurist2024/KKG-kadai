import { afterEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "../../../frontend/src/app/api/[...path]/route";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

const context = (...path: string[]) => ({ params: Promise.resolve({ path }) });

describe("FastAPI runtime proxy", () => {
  it("reads target at request time and forwards query, streamed body and AI token", async () => {
    vi.stubEnv("API_PROXY_TARGET", "http://backend:8000");
    const fetchMock = vi.fn().mockResolvedValue(new Response('{"detail":"invalid"}', { status: 422 }));
    vi.stubGlobal("fetch", fetchMock);
    const request = new Request("http://frontend/api/recognize?scale_px=100", {
      method: "POST", body: "image-bytes", headers: { "content-type": "image/png", "x-ai-token": "test-token" },
    });
    const response = await POST(request, context("recognize"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("http://backend:8000/api/recognize?scale_px=100");
    expect(init.body).toBe(request.body);
    expect(init.headers.get("x-ai-token")).toBe("test-token");
    expect(init.headers.get("content-type")).toBe("image/png");
    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ detail: "invalid" });
    vi.stubEnv("API_PROXY_TARGET", "http://other-backend:9000");
    fetchMock.mockResolvedValueOnce(new Response("{}"));
    await GET(new Request("http://frontend/api/health"), context("health"));
    expect(String(fetchMock.mock.calls[1][0])).toBe("http://other-backend:9000/api/health");
  });

  it("rejects unrelated paths and unsupported method before contacting the backend", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect((await GET(new Request("http://frontend/api/private"), context("private"))).status).toBe(404);
    expect((await GET(new Request("http://frontend/api/analyze"), context("analyze"))).status).toBe(405);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns a clear error without leaking upstream configuration", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret backend URL")));
    const response = await GET(new Request("http://frontend/api/health"), context("health"));
    expect(response.status).toBe(502);
    expect(await response.text()).not.toContain("secret");
  });
});
