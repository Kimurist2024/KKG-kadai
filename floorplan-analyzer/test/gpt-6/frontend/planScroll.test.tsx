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

test("selecting rooms while zoomed in whole-plan mode keeps the pan position; fitting resets it", () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  const { container } = render(<App />);
  const zoomIn = screen.getByRole("button", { name: "拡大" });
  fireEvent.click(zoomIn); fireEvent.click(zoomIn); fireEvent.click(zoomIn);
  expect(screen.getByText("200%")).toBeTruthy();
  const canvas = container.querySelector(".plan-canvas")!;
  canvas.scrollTop = 180; canvas.scrollLeft = 70;

  fireEvent.click(container.querySelectorAll("polygon")[2]);
  expect(container.querySelector("#room-detail-heading")).not.toBeNull();
  expect(canvas.scrollTop).toBe(180);
  expect(canvas.scrollLeft).toBe(70);

  fireEvent.click(container.querySelectorAll("table.rooms tbody tr")[4]);
  expect(canvas.scrollTop).toBe(180);
  expect(canvas.scrollLeft).toBe(70);
  expect(screen.getByText("200%")).toBeTruthy();

  fireEvent.click(screen.getByRole("button", { name: "選択部屋に合わせる" }));
  expect(canvas.scrollTop).toBe(0);
  expect(canvas.scrollLeft).toBe(0);
  expect(screen.getByText("フィット 100%")).toBeTruthy();

  canvas.scrollTop = 50; canvas.scrollLeft = 20;
  fireEvent.click(container.querySelectorAll("table.rooms tbody tr")[1]);
  expect(canvas.scrollTop).toBe(0);
  expect(canvas.scrollLeft).toBe(0);
});
