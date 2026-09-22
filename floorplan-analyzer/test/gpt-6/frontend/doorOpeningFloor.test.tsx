// @vitest-environment jsdom
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import RoomDetail from "../../../frontend/src/components/RoomDetail";
import sample from "./fixtures/sample-result.json";
import type { AnalyzeResponse } from "../../../frontend/src/types";
import { floorAreaFormula, roomsToCsv } from "../../../frontend/src/format";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const result = sample as unknown as AnalyzeResponse;
const ld = result.rooms.find((r) => r.name === "LD")!;
const k = result.rooms.find((r) => r.name === "K")!;

test("the sample response carries the door-opening floor transfer and LD+K rounds to the drawing value", () => {
  expect(result.settings.door_opening_depth_m).toBe(0.126);
  expect(ld.door_opening_transfers.map((t) => t.door_id)).toEqual([33, 34, 38]);
  expect(ld.door_opening_adjustment_m2).toBeLessThan(0);
  expect(ld.floor_area_m2).toBeCloseTo(ld.floor_area_raw_m2 + ld.door_opening_adjustment_m2, 9);
  expect((ld.floor_area_m2 + k.floor_area_m2).toFixed(2)).toBe("27.22");
  // 室内の受け渡しなので、合計は補正前と同じ
  const raw = result.rooms.reduce((s, r) => s + r.floor_area_raw_m2, 0);
  expect(result.summary.total_floor_area_m2).toBeCloseTo(raw, 9);
  expect(result.summary.door_opening_adjusted_room_count).toBe(9);
});

test("the floor-area formula shows raw area, the transfer, and the displayed area", () => {
  const mpp = result.settings.meters_per_px;
  expect(floorAreaFormula(ld, mpp)).toMatch(/= 21\.27 m² − ドア開口部の床 0\.31 m² = 20\.97 m²$/);
  expect(floorAreaFormula(k, mpp)).toMatch(/= 6\.25 m²$/);   // 補正が無い部屋は従来の式のまま
});

test("RoomDetail lists each door transfer with the partner room and the depth", () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  const noop = () => {};
  render(<RoomDetail result={result} room={ld} originalRoomName={ld.room_name} hoverEdge={null} selectedEdge={null}
    onHoverEdge={noop} onSelectEdge={noop} onHoverSegments={noop} pinnedSegments={[]} onPinSegments={noop}
    onRename={noop} onShowOnPlan={noop} onClose={noop} />);
  const list = screen.getByLabelText("ドア開口部の床の受け渡し");
  const items = Array.from(list.querySelectorAll("li")).map((li) => li.textContent);
  expect(items).toHaveLength(3);
  expect(items[0]).toContain("ドア id33");
  expect(items[0]).toContain("洗面所 へ");
  expect(items[0]).toContain("奥行き 0.126 m");
});

test("RoomDetail shows the partner room's current display name after a rename", () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  const noop = () => {};
  const renamed = structuredClone(result) as AnalyzeResponse;
  const partner = renamed.rooms.find((r) => r.name === "未命名 #3")!;
  partner.name = "納戸";
  const ldNow = renamed.rooms.find((r) => r.name === "LD")!;
  render(<RoomDetail result={renamed} room={ldNow} originalRoomName={ldNow.room_name} hoverEdge={null} selectedEdge={null}
    onHoverEdge={noop} onSelectEdge={noop} onHoverSegments={noop} pinnedSegments={[]} onPinSegments={noop}
    onRename={noop} onShowOnPlan={noop} onClose={noop} />);
  const items = Array.from(screen.getByLabelText("ドア開口部の床の受け渡し").querySelectorAll("li")).map((li) => li.textContent);
  expect(items.find((s) => s!.includes("ドア id34"))).toContain("納戸 へ");
});

test("CSV includes the raw floor area and the transfer columns", () => {
  const lines = roomsToCsv(result).split("\n");
  expect(lines[0]).toContain("頂点からの床面積[m2]");
  expect(lines[0]).toContain("ドア開口部の床の増減[m2]");
  const ldRow = lines.find((l) => l.startsWith("LD,"))!;
  expect(ldRow).toContain(ld.floor_area_m2.toFixed(3));
  expect(ldRow).toContain(ld.floor_area_raw_m2.toFixed(3));
  expect(ldRow).toContain(ld.door_opening_adjustment_m2.toFixed(3));
});
