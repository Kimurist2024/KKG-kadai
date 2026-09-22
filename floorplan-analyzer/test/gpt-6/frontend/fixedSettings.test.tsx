// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, renderHook, screen } from "@testing-library/react";
import App from "../../../frontend/src/App";
import { useAnalysis } from "../../../frontend/src/hooks/useAnalysis";
import { analyzeFile } from "../../../frontend/src/api";
import { DEFAULT_SETTINGS, type AnalyzeResponse } from "../../../frontend/src/types";
import { roomsToCsv } from "../../../frontend/src/format";
import sample from "./fixtures/sample-result.json";

vi.mock("../../../frontend/src/api", () => ({ analyzeFile: vi.fn() }));
const response = sample as AnalyzeResponse;
const file = (name: string, text = async () => "{}") => Object.assign(new File(["{}"], name), { text });
beforeEach(() => {
  vi.mocked(analyzeFile).mockReset().mockResolvedValue(response);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(["{}"]) }));
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState({}, "", "/"); });

test("guide upload entry skips the sample and offers JSON selection", () => {
  window.history.replaceState({}, "", "/?start=upload");
  render(<App />);
  expect(fetch).not.toHaveBeenCalled();
  expect(analyzeFile).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "JSON ファイルを選択" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "はじめての方へ：使い方を見る" }).getAttribute("href")).toBe("/guide");
});

test("uploads analyze immediately using the fixed assignment values and raw geometry", async () => {
  const { result } = renderHook(useAnalysis);
  for (const name of ["a.json", "b.json"]) {
    const drawing = file(name);
    await act(() => result.current.loadFile(drawing));
    expect(analyzeFile).toHaveBeenLastCalledWith(drawing, {
      ceiling_height_m: 2.4, door_height_m: 2, scale_px: 96.7, scale_m: 1.365,
      tolerance_px: 10, door_opening_depth_m: 0.126, geometry_mode: "raw", boundary_reference: "unknown",
    }, expect.any(AbortSignal));
    expect(result.current.file).toBe(drawing);
  }
});

test("late image read and analysis cannot overwrite a newer drawing", async () => {
  const { result } = renderHook(useAnalysis);
  let finishImage!: (s: string) => void;
  let finishAnalysis!: (r: AnalyzeResponse) => void;
  vi.mocked(analyzeFile).mockImplementationOnce(() => new Promise(r => { finishAnalysis = r; }));
  let slow!: Promise<void>;
  act(() => { slow = result.current.loadFile(file("slow.json", () => new Promise(r => { finishImage = r; }))); });
  const latest = file("latest.json");
  await act(() => result.current.loadFile(latest));
  await act(async () => { finishImage("{}"); finishAnalysis(response); await slow; });
  expect(result.current.file).toBe(latest);
});

test("failed upload preserves the prior snapshot and can be retried", async () => {
  const { result } = renderHook(useAnalysis);
  const previous = file("previous.json"), next = file("next.json");
  await act(() => result.current.loadFile(previous));
  vi.mocked(analyzeFile).mockRejectedValueOnce(new Error("network"));
  await act(() => result.current.loadFile(next));
  expect(result.current.status).toEqual({ state: "error", message: "network" });
  expect(result.current.file).toBe(previous);
  await act(() => result.current.loadFile(next));
  expect(result.current.file).toBe(next);
});

test("sample and upload show results without editable conditions or image AI; CSV remains", async () => {
  const { container } = render(<App />);
  // サンプルは自動では読み込まれない。人が「サンプルで試す」を押したときだけ表示する。
  expect(analyzeFile).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "サンプルで試す" }));
  await screen.findByText("サンプル表示中");
  expect(screen.getByRole("heading", { name: "課題指定の計算条件（固定）" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "計算条件を変更" })).toBeNull();
  expect(screen.queryByRole("spinbutton")).toBeNull();
  expect(screen.getByRole("button", { name: /CSV/ })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "画像から AI で輪郭を作成" })).toBeNull();
  expect(screen.queryByText("AI 利用トークン")).toBeNull();
  fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file("drawing.json")] } });
  await screen.findByText("drawing.json");
  expect(screen.queryByText("この図面の縮尺を確認")).toBeNull();
  expect(vi.mocked(analyzeFile).mock.lastCall?.[1]).toEqual(DEFAULT_SETTINGS);
  expect(screen.getByRole("img", { name: "平面図の解析結果" })).toBeTruthy();
  expect(container.querySelector("table.rooms")).not.toBeNull();
});

test("CSV retains missing-wall and door caveats", () => {
  const csv = roomsToCsv({ ...response, warnings: [
    { code: "missing_wall_data", contour_id: null, message: "壁データがありません。" },
    { code: "inferred_door_wall", contour_id: null, message: "扉部分の壁を補完しました。" },
  ] });
  expect(csv).toContain("壁データがありません。");
  expect(csv).toContain("扉部分の壁を補完しました。");
});
