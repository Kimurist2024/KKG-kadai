// @vitest-environment jsdom
import { afterEach, expect, test, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import App from "../../../frontend/src/App";
import sample from "./fixtures/sample-result.json";

vi.mock("../../../frontend/src/hooks/useAnalysis", () => ({ useAnalysis: () => ({
  pending: null, file: null, imageUrl: null, appliedSettings: sample.settings,
  result: sample, status: { state: "idle" }, updatedAt: null,
  cancelPending: vi.fn(), loadFile: vi.fn(), loadSample: vi.fn(), reanalyze: vi.fn(),
}) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("room selection immediately updates results without network; keyboard clears selection", () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
  const { container } = render(<App />);
  const polygons = container.querySelectorAll("polygon");
  const timings: number[] = [];
  for (let i = 0; i < 33; i++) {
    const room = sample.rooms[i % sample.rooms.length];
    const start = performance.now();
    fireEvent.click(polygons[i % polygons.length]);
    timings.push(performance.now() - start);
    expect(container.querySelector("#room-detail-heading")?.textContent).toBe(room.name);
    expect(container.querySelector(".selection-bar")?.textContent).toContain(room.floor_area_m2.toLocaleString("ja-JP", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  }
  const source = container.querySelector<HTMLDetailsElement>(".source-check")!;
  expect(source.querySelector("table")).toBeNull();
  source.open = true;
  fireEvent(source, new Event("toggle"));
  expect(source.querySelectorAll("tbody tr")).toHaveLength(sample.rooms.at(-1)!.edges.length);
  fireEvent.click(polygons[0]);
  expect(container.querySelector<HTMLDetailsElement>(".source-check")!.open).toBe(false);
  expect(container.querySelector(".source-check table")).toBeNull();
  expect(fetch).not.toHaveBeenCalled();
  if (process.env.BENCH_SELECTION) {
    const sorted = timings.slice(11).sort((a,b) => a-b);
    console.log(JSON.stringify({ selection_median_ms: sorted[Math.floor(sorted.length/2)], selection_p95_ms: sorted[Math.floor(sorted.length*.95)], samples: sorted.length }));
  }
  fireEvent.keyDown(window, { key: "Escape" });
  expect(container.querySelector("#room-detail-heading")).toBeNull();
});


test("fit button can precede room selection, tracks selected room, and restores whole plan", () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  const { container } = render(<App />);
  const svg = container.querySelector<SVGSVGElement>(".plan-canvas svg")!;
  const full = svg.getAttribute("viewBox");
  const fit = screen.getByRole("button", { name: "選択部屋に合わせる" });
  expect((fit as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(fit);
  expect(screen.getByText(/拡大する部屋を図面または表でクリック/)).toBeTruthy();
  expect(fit.classList.contains("active")).toBe(true);
  expect(screen.getByRole("button", { name: "全体" }).classList.contains("active")).toBe(false);
  fireEvent.click(container.querySelectorAll("polygon")[1]);
  const fitted = svg.getAttribute("viewBox");
  expect(fitted).not.toBe(full);
  const fittedHeight = Number.parseFloat(svg.style.height);
  const [, , vw, vh] = fitted!.split(" ").map(Number);
  expect(vw / vh).toBeCloseTo(800 / fittedHeight, 8);
  expect(Number.parseFloat((container.querySelector(".plan-canvas") as HTMLElement).style.height)).toBe(fittedHeight + 2);
  fireEvent.click(screen.getByRole("button", { name: "拡大" }));
  expect(Number.parseFloat(svg.style.height)).toBeCloseTo(fittedHeight * 1.25);
  fireEvent.click(fit);
  expect(Number.parseFloat(svg.style.height)).toBe(fittedHeight);
  expect(fit.getAttribute("aria-pressed")).toBe("true");
  expect(fit.classList.contains("active")).toBe(true);
  expect(screen.queryByText(/拡大する部屋を図面または表でクリック/)).toBeNull();
  fireEvent.click(container.querySelectorAll("table.rooms tbody tr")[3]);
  expect(svg.getAttribute("viewBox")).not.toBe(fitted);
  fireEvent.click(screen.getByRole("button", { name: "全体" }));
  expect(svg.getAttribute("viewBox")).toBe(full);
  expect(fit.classList.contains("active")).toBe(false);
  expect(screen.getByRole("button", { name: "全体" }).classList.contains("active")).toBe(true);
  const canvas = container.querySelector(".plan-canvas")!;
  canvas.scrollTop = 200; canvas.scrollLeft = 100;
  fireEvent.click(fit);
  expect(svg.getAttribute("viewBox")).not.toBe(full);
  expect(canvas.scrollTop).toBe(0);
  expect(canvas.scrollLeft).toBe(0);
  fireEvent.keyDown(window, { key: "Escape" });
  expect(svg.getAttribute("viewBox")).toBe(full);
  fireEvent.click(fit);
  fireEvent.click(screen.getByRole("button", { name: "全体" }));
  fireEvent.click(container.querySelectorAll("polygon")[1]);
  expect(svg.getAttribute("viewBox")).toBe(full);
});


test("200 percent pan position survives scrollbar or container resize notifications", () => {
  let resize: ResizeObserverCallback = () => {};
  vi.stubGlobal("ResizeObserver", class {
    constructor(callback: ResizeObserverCallback) { resize = callback; }
    observe() {} disconnect() {}
  });
  const { container } = render(<App />);
  fireEvent.click(container.querySelectorAll("polygon")[1]);
  fireEvent.click(screen.getByRole("button", { name: "選択部屋に合わせる" }));
  for (let i = 0; i < 3; i++) fireEvent.click(screen.getByRole("button", { name: "拡大" }));
  expect(screen.getByText("フィット 200%")).toBeTruthy();
  const canvas = container.querySelector(".plan-canvas")!;
  canvas.scrollTop = 180; canvas.scrollLeft = 70;
  for (const width of [785, 800, 785]) {
    act(() => resize([{ contentRect: { width } } as ResizeObserverEntry], {} as ResizeObserver));
    expect(canvas.scrollTop).toBe(180);
    expect(canvas.scrollLeft).toBe(70);
    expect(screen.getByText("フィット 200%")).toBeTruthy();
  }
});
