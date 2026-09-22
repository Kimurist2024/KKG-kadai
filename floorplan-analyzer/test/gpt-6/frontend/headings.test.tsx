// @vitest-environment jsdom
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import App from "../../../frontend/src/App";
import sample from "./fixtures/sample-result.json";

vi.mock("../../../frontend/src/hooks/useAnalysis", () => ({ useAnalysis: () => ({
  pending: null, file: null, imageUrl: null, appliedSettings: sample.settings,
  result: sample, status: { state: "idle" }, updatedAt: null,
  cancelPending: vi.fn(), loadFile: vi.fn(), loadSample: vi.fn(), reanalyze: vi.fn(),
}) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("main landmark and section headings name the visualization, the table and the rationale", () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  const { container } = render(<App />);
  expect(screen.getByRole("main")).toBeTruthy();
  expect(screen.getByRole("main").classList.contains("app-landing")).toBe(false); // 結果表示では通常の幅に戻る
  expect(container.querySelector("main.app header")).not.toBeNull();
  expect(container.querySelector("main.app footer")).not.toBeNull();
  expect(screen.getByRole("heading", { name: "図面（可視化結果）" }).tagName).toBe("H2");
  expect(screen.getByRole("heading", { name: "部屋別の床面積・壁面積" }).tagName).toBe("H2");
  expect(screen.getByRole("heading", { name: "課題指定の計算条件（固定）" })).toBeTruthy();
  expect(screen.getByText(/画面下部に算出根拠パネルが開きます/)).toBeTruthy();
  expect(container.querySelector(".detail")).toBeNull();
  fireEvent.click(container.querySelectorAll("table.rooms tbody tr")[0]);
  expect(container.querySelector(".detail .section-kicker")?.textContent).toContain("算出根拠");
  const heading = container.querySelector("#room-detail-heading")!.textContent;
  expect(sample.rooms.map((r) => r.name)).toContain(heading);
});

test("fixed conditions show the wall-area formula with 2.4 m / 2.0 m and no '適用中' label or inputs", () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  const { container } = render(<App />);
  expect(screen.getByText(/壁面積 ＝ 壁長 × 天井高 2\.4 m − 控除ドア幅 × ドア高 2\.0 m/)).toBeTruthy();
  expect(screen.getByText(/入力・変更は不要/)).toBeTruthy();
  expect(screen.queryByText("適用中の計算条件")).toBeNull();
  expect(screen.queryByRole("spinbutton")).toBeNull();
  const chips = Array.from(container.querySelectorAll(".conditions .cond-chip")).map((el) => el.textContent);
  expect(chips).toContain("天井高 2.4 m");
  expect(chips).toContain("ドア高 2.0 m");
  fireEvent.click(container.querySelectorAll("table.rooms tbody tr")[0]);
  expect(container.querySelector(".headline-breakdown")?.textContent).toMatch(/壁部分 [\d.]+ m² − ドア控除 [\d.]+ m² ＝ [\d.]+ m²/);
  expect(container.textContent).not.toMatch(/ドア高 2 m/);
});
