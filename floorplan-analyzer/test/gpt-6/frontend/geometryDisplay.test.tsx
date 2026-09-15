// @vitest-environment jsdom
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import FloorPlanView from "../../../frontend/src/components/FloorPlanView";
import RoomDetail from "../../../frontend/src/components/RoomDetail";
import sample from "./fixtures/sample-result.json";
import type { AnalyzeResponse } from "../../../frontend/src/types";
import { roomsToCsv } from "../../../frontend/src/format";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test("holes use evenodd paths, overlap is a noninteractive overlay, and inference stays visible", () => {
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} });
  const result = structuredClone(sample) as AnalyzeResponse;
  const room = result.rooms[0];
  room.holes = [[{x:10,y:10},{x:20,y:10},{x:20,y:20},{x:10,y:20}]];
  room.label_point = {x:30,y:30};
  room.edges[0].boundary_kind = "hole";
  room.edges[0].inferred_wall_intervals = [room.edges[0].wall_intervals[0]];
  result.overlaps = [{room_ids:[1,2],area_m2:1,regions:[{vertices:room.holes[0],holes:[]}]}];
  result.summary.union_floor_area_m2 = result.summary.total_floor_area_m2 - 1;
  result.summary.overlap_floor_area_m2 = 1;
  result.warnings.push({code:"room_overlap",contour_id:1,message:"重複 1 m²"}, {code:"inferred_door_wall",contour_id:1,message:"扉の壁区間を補完しました"});
  const noop = () => {};
  const { container } = render(<FloorPlanView result={result} imageUrl={null} layers={{image:true,rooms:true,walls:true,doors:true,labels:true}}
    onLayersChange={noop} selectedId={1} hoverId={null} hoverEdge={null} selectedEdge={null} highlightSegmentIds={[]}
    onSelect={noop} onHover={noop} onHoverEdge={noop} onSelectEdge={noop} />);
  const path = container.querySelector('path[fill-rule="evenodd"]')!;
  expect(path.getAttribute("d")!.match(/M /g)).toHaveLength(2);
  expect(container.querySelector('[data-overlap="true"]')!.getAttribute("pointer-events")).toBe("none");
  expect(screen.getByText("紫点線：扉から補完した壁")).toBeTruthy();
  const csv = roomsToCsv(result);
  expect(csv).toContain("重複を除いた床面積");
  expect(csv).toContain("扉の壁区間を補完しました");
  expect(csv).toContain("重複 1 m²");
  render(<RoomDetail result={result} room={room} originalRoomName={room.room_name} hoverEdge={null} selectedEdge={null}
    onHoverEdge={noop} onSelectEdge={noop} onHoverSegments={noop} pinnedSegments={[]} onPinSegments={noop} onRename={noop} onShowOnPlan={noop} onClose={noop} />);
  expect(screen.getByText(/内側の穴 1 個を床面積から除外/)).toBeTruthy();
  expect(screen.getAllByText("内周").length).toBeGreaterThan(0);
});
