// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import RoomTable from "../../../frontend/src/components/RoomTable";
import EdgeBreakdownTable from "../../../frontend/src/components/detail/EdgeBreakdownTable";
import type { AnalyzeResponse } from "../../../frontend/src/types";
import sample from "./fixtures/sample-result.json";

afterEach(cleanup);
const result = sample as AnalyzeResponse;
const noop = () => {};

test("rooms with undetected wall sections are marked in the table (cell, tag and total)", () => {
  const { container } = render(<RoomTable result={result} selectedId={null} hoverId={null} onSelect={noop} onHover={noop} onShowDetail={noop} />);
  const expected = result.rooms.filter((r) => r.opening_length_m > 0.005).length;
  expect(expected).toBe(5);
  expect(container.querySelectorAll("tbody td.has-opening")).toHaveLength(expected);
  expect(screen.getAllByText("壁なし区間あり")).toHaveLength(expected);
  expect(container.querySelector("tbody td.has-opening")?.getAttribute("title")).toContain("壁面積に含めません");
  expect(container.querySelector("tfoot td.has-opening")).not.toBeNull();
  expect(screen.getByRole("heading", { name: "部屋別の床面積・壁面積" }).tagName).toBe("H2");
  expect(container.querySelectorAll("tbody td .wall-review")).toHaveLength(0);
});

test("a wall warning becomes a titled 要確認 badge on the affected room only; a selected row is unique", () => {
  const target = result.rooms[2];
  const withWarning: AnalyzeResponse = {
    ...result,
    warnings: [...result.warnings, { code: "no_room_walls", contour_id: target.id, message: "壁が検出されませんでした" }],
  };
  const onSelect = vi.fn();
  const { container, rerender } = render(<RoomTable result={withWarning} selectedId={null} hoverId={null} onSelect={onSelect} onHover={noop} onShowDetail={noop} />);
  const badges = container.querySelectorAll("tbody td .wall-review");
  expect(badges).toHaveLength(1);
  expect(badges[0].getAttribute("title")).toBe("壁が検出されませんでした");
  expect(badges[0].getAttribute("aria-label")).toBe("要確認: 壁が検出されませんでした");
  const row = badges[0].closest("tr")!;
  expect(row.textContent).toContain(target.name);
  fireEvent.click(row);
  expect(onSelect).toHaveBeenCalledWith(target.id);
  rerender(<RoomTable result={withWarning} selectedId={target.id} hoverId={null} onSelect={onSelect} onHover={noop} onShowDetail={noop} />);
  expect(container.querySelectorAll("tbody tr.selected")).toHaveLength(1);
  expect(container.querySelector("tbody tr.selected")?.textContent).toContain(target.name);
});

test("pinned interval chips are filled and prefixed with a check mark", () => {
  const room = result.rooms.find((r) => r.edges.some((e) => e.wall_intervals.some((iv) => iv.ids.length > 0)))!;
  function Harness() {
    const [pinned, setPinned] = useState<number[]>([]);
    return (
      <EdgeBreakdownTable room={room} settings={result.settings} hoverEdge={null} selectedEdge={null}
        onHoverEdge={noop} onSelectEdge={noop} onHoverSegments={noop} pinnedSegments={pinned} onPinSegments={setPinned} />
    );
  }
  const { container } = render(<Harness />);
  const chip = Array.from(container.querySelectorAll<HTMLButtonElement>("button.chip-wall")).find((b) => !b.disabled)!;
  expect(chip.getAttribute("aria-pressed")).toBe("false");
  expect(chip.textContent!.startsWith("✓")).toBe(false);
  fireEvent.click(chip);
  expect(chip.getAttribute("aria-pressed")).toBe("true");
  expect(chip.classList.contains("pinned")).toBe(true);
  expect(chip.textContent!.startsWith("✓ 壁")).toBe(true);
  fireEvent.click(chip);
  expect(chip.getAttribute("aria-pressed")).toBe("false");
  expect(chip.textContent!.startsWith("✓")).toBe(false);
});
