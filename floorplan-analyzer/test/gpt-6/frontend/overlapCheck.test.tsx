// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, within } from "@testing-library/react";
import App from "../../../frontend/src/App";
import sample from "./fixtures/sample-result.json";

// 同梱サンプルの実際の解析結果（部屋の重複 9 件）で、確認事項の「部屋の重複」と図面の連動を確かめる。
vi.mock("../../../frontend/src/hooks/useAnalysis", () => ({ useAnalysis: () => ({
  pending: null, file: null, isSample: true, imageUrl: null, appliedSettings: sample.settings,
  result: sample, status: { state: "idle" }, updatedAt: null,
  cancelPending: vi.fn(), loadFile: vi.fn(), loadSample: vi.fn(), reanalyze: vi.fn(),
}) }));
beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function openOverlaps() {
  const { container } = render(<App />);
  const details = container.querySelector<HTMLDetailsElement>("details.overlap-check")!;
  fireEvent.click(details.querySelector("summary")!);
  return { container, details, rows: Array.from(details.querySelectorAll<HTMLElement>(".overlap-row")) };
}

test("the summary shows the scale, and pairs are listed by area without repeated buttons", () => {
  const { details, rows } = openOverlaps();
  expect(within(details).getByText("部屋の重複 9 か所")).toBeTruthy();
  expect(details.querySelector("summary")!.textContent).toContain("重複計上 0.18 m²（床面積合計の 0.4%）・最大 0.04 m²");
  expect(rows).toHaveLength(9);
  expect(rows[0].textContent).toContain("ホール");
  expect(rows[0].textContent).toContain("玄関");
  expect(rows[0].querySelector(".overlap-area")!.textContent).toBe("0.04 m²");
  expect(rows[8].querySelector(".overlap-area")!.textContent).toBe("0.01 m² 未満");
  const areas = sample.overlaps.map((o) => o.area_m2).sort((a, b) => b - a);
  expect(areas[0]).toBeGreaterThan(areas[8]);
  expect(within(details).queryByRole("button", { name: /部屋 #\d+ を確認/ })).toBeNull();
  expect(rows[0].querySelector(".overlap-bar")!.getAttribute("aria-hidden")).toBe("true");
  expect(within(rows[0]).getByRole("button", { name: "玄関（部屋 #11）を選んで図面で確認" })).toBeTruthy();
});

test("hovering a row rings the overlap on the plan; pressing a room chip selects the room and keeps the ring", () => {
  const { container, rows } = openOverlaps();
  const ring = () => container.querySelector('[data-overlap-focus="true"]');
  expect(ring()).toBeNull();
  fireEvent.mouseEnter(rows[0]);
  expect(ring()).not.toBeNull();
  expect(ring()!.getAttribute("pointer-events")).toBe("none");
  fireEvent.mouseLeave(rows[0]);
  expect(ring()).toBeNull();
  expect(container.querySelector("#room-detail-heading")).toBeNull();
  fireEvent.click(within(rows[0]).getByRole("button", { name: "玄関（部屋 #11）を選んで図面で確認" }));
  expect(container.querySelector("#room-detail-heading")).not.toBeNull();
  expect(ring()).not.toBeNull();
  expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
});

test("keyboard focus keeps the ring even when the mouse leaves; it clears only when focus leaves the row", () => {
  const { container, rows } = openOverlaps();
  const ring = () => container.querySelector('[data-overlap-focus="true"]');
  const [first, second] = within(rows[0]).getAllByRole("button");
  fireEvent.focus(first);
  expect(ring()).not.toBeNull();
  fireEvent.mouseEnter(rows[0]);
  fireEvent.mouseLeave(rows[0]);
  expect(ring()).not.toBeNull(); // フォーカスが残っている間は、マウスが離れても消えない
  fireEvent.blur(first, { relatedTarget: second }); // 同じ行の隣のチップへ移動
  fireEvent.focus(second);
  expect(ring()).not.toBeNull();
  fireEvent.blur(second, { relatedTarget: document.body }); // 行の外へ
  expect(ring()).toBeNull();
});
