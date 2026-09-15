// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import App from "../../../frontend/src/App";
import { analyzeFile } from "../../../frontend/src/api";
import sample from "./fixtures/sample-result.json";
import { readFileSync } from "node:fs";
const styles = readFileSync("src/styles.css", "utf8");
import type { AnalyzeResponse } from "../../../frontend/src/types";

vi.mock("../../../frontend/src/api", () => ({ analyzeFile: vi.fn() }));
let stylesheet: HTMLStyleElement;

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  vi.stubGlobal("innerHeight", 800);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(["{}"]) }));
  const result = structuredClone(sample) as AnalyzeResponse;
  result.warnings = [{ code: "unnamed_room", contour_id: result.rooms[0].id, message: "部屋名を確認してください" }];
  vi.mocked(analyzeFile).mockReset().mockResolvedValue(result);
  stylesheet = document.createElement("style");
  stylesheet.textContent = styles;
  document.head.append(stylesheet);
});
afterEach(() => { cleanup(); stylesheet.remove(); vi.unstubAllGlobals(); });

async function openWorkspace() {
  render(<App />);
  return screen.findByRole("region", { name: "平面図のスクロール領域" });
}

test("確認事項は図面側にあり、見出しと計算条件はスクロール内容に含まれない", async () => {
  const plan = await openWorkspace();
  const checks = screen.getByRole("region", { name: "確認事項のスクロール領域" });
  expect(plan.closest(".panel")?.contains(checks)).toBe(true);
  expect(checks.contains(screen.getByRole("heading", { name: "解析結果の確認事項" }))).toBe(false);
  expect(plan.closest(".panel")?.contains(screen.getByRole("heading", { name: "現在の図面の計算条件" }))).toBe(false);
  const diagnostics = within(checks).getByText("診断メッセージ一覧").closest("details")!;
  fireEvent.click(within(checks).getByText("診断メッセージ一覧"));
  expect(diagnostics.open).toBe(true);
  expect(within(checks).getByText("部屋名を確認してください")).toBeTruthy();
});

test("両領域は高さ制限・標準スクロール・ページへの連鎖抑制を備える", async () => {
  const plan = await openWorkspace();
  const checks = screen.getByRole("region", { name: "確認事項のスクロール領域" });
  const planStyle = getComputedStyle(plan);
  expect(planStyle.overflow).toBe("auto");
  expect(planStyle.maxHeight).toBe("min(480px, 50vh)");
  expect(planStyle.getPropertyValue("overscroll-behavior")).toBe("contain");
  const checksStyle = getComputedStyle(checks);
  expect(checksStyle.overflowY).toBe("auto");
  expect(checksStyle.maxHeight).toBe("min(320px, 35vh)");
  expect(checksStyle.getPropertyValue("overscroll-behavior-y")).toBe("contain");
  for (const region of [plan, checks]) {
    expect(region.tabIndex).toBe(0);
    expect(getComputedStyle(region).getPropertyValue("scrollbar-gutter")).toBe("stable");
    region.focus();
    expect(document.activeElement).toBe(region);
  }
});

test("選択部屋のフィットは表示枠に収まり、200%への拡大で枠を伸ばさない", async () => {
  const plan = await openWorkspace();
  const table = screen.getByRole("table");
  fireEvent.click(within(table).getAllByRole("row")[1]);
  fireEvent.click(screen.getByRole("button", { name: "選択部屋に合わせる" }));
  const drawing = within(plan).getByRole("img", { name: "平面図の解析結果" });
  expect(plan.style.height).toBe("400px");
  expect(drawing.style.height).toBe("398px");
  fireEvent.click(screen.getByRole("button", { name: "拡大" }));
  fireEvent.click(screen.getByRole("button", { name: "拡大" }));
  fireEvent.click(screen.getByRole("button", { name: "拡大" }));
  expect(drawing.style.width).toBe("200%");
  expect(drawing.style.height).toBe("796px");
  expect(plan.style.height).toBe("400px");
  act(() => { vi.stubGlobal("innerHeight", 600); window.dispatchEvent(new Event("resize")); });
  expect(plan.style.height).toBe("300px");
  expect(drawing.style.height).toBe("596px");
  expect(analyzeFile).toHaveBeenCalledTimes(1);
});
