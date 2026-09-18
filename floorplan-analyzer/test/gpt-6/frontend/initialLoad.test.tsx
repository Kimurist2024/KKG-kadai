// @vitest-environment jsdom
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import App from "../../../frontend/src/App";
import { DEFAULT_SETTINGS } from "../../../frontend/src/types";

// 初期表示では同梱サンプルを読み込まない。読み込むのは人が選んだとき（ボタン、または使い方ページの ?sample=1）だけ。
const loadSample = vi.hoisted(() => vi.fn());
vi.mock("../../../frontend/src/hooks/useAnalysis", () => ({ useAnalysis: () => ({
  pending: null, file: null, isSample: false, imageUrl: null, appliedSettings: DEFAULT_SETTINGS,
  result: null, status: { state: "idle" }, updatedAt: null,
  cancelPending: vi.fn(), loadFile: vi.fn(), loadSample, reanalyze: vi.fn(),
}) }));

afterEach(() => { cleanup(); loadSample.mockReset(); window.history.replaceState({}, "", "/"); vi.unstubAllGlobals(); });

function open(url: string) {
  window.history.replaceState({}, "", url);
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  return render(<App />);
}

test.each(["/", "/?start=upload", "/?room=3"])("opening %s shows the chooser without loading the sample", (url) => {
  open(url);
  expect(loadSample).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "サンプルで試す" })).toBeTruthy();
  expect(screen.getByText("JSON ファイルを選択")).toBeTruthy();
  expect(screen.getByRole("heading", { name: "課題指定の計算条件（固定）" })).toBeTruthy();
  expect(screen.queryByRole("heading", { name: "図面（可視化結果）" })).toBeNull();
  // 初期画面は読み幅に絞った 1 カラム。枠の入れ子（panel の中のドロップ枠）を作らない
  const main = screen.getByRole("main");
  expect(main.classList.contains("app-landing")).toBe(true);
  expect(main.querySelector(".landing > .dropzone")).not.toBeNull();
  expect(main.querySelector(".panel")).toBeNull();
  expect(screen.getByRole("heading", { name: "JSON をドロップして面積を計算" }).tagName).toBe("H2");
  expect(screen.getByRole("list", { name: "解析するとできること" }).querySelectorAll("li")).toHaveLength(3);
  expect(screen.getByText(/サンプル: 同梱の平面図（11 部屋・約 360 KB）/)).toBeTruthy();
});

test("the guide's sample link (?sample=1) loads the sample once", () => {
  open("/?sample=1");
  expect(loadSample).toHaveBeenCalledTimes(1);
});

test("pressing サンプルで試す loads the sample", () => {
  open("/");
  fireEvent.click(screen.getByRole("button", { name: "サンプルで試す" }));
  expect(loadSample).toHaveBeenCalledTimes(1);
});
