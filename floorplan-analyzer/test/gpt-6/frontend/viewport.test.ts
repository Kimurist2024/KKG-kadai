import { expect, test } from "vitest";
import { fitRoomViewport, overlapRing } from "../../../frontend/src/viewport";
import sample from "./fixtures/sample-result.json";

test("every sample room fits both axes with pixel padding at desktop and mobile sizes", () => {
  for (const [width, height] of [[1000, 560], [343, 400], [600, 240]]) {
    for (const room of sample.rooms) {
      const v = fitRoomViewport(room.vertices, width, height);
      expect(v.w / v.h).toBeCloseTo(width / height, 10);
      for (const p of room.vertices) {
        const x = (p.x - v.x) * width / v.w;
        const y = (p.y - v.y) * height / v.h;
        expect(x).toBeGreaterThanOrEqual(24 - 1e-8);
        expect(x).toBeLessThanOrEqual(width - 24 + 1e-8);
        expect(y).toBeGreaterThanOrEqual(24 - 1e-8);
        expect(y).toBeLessThanOrEqual(height - 24 + 1e-8);
      }
    }
  }
});

test("edge rooms stay centered and degenerate bounds stay finite", () => {
  for (const vertices of [[{x:0,y:0},{x:10,y:1000}], [{x:0,y:0}]]) {
    const v = fitRoomViewport(vertices, 343, 480);
    expect(Object.values(v).every(Number.isFinite)).toBe(true);
    expect(v.w).toBeGreaterThan(0);
    expect(v.h).toBeGreaterThan(0);
    expect(v.x).toBeLessThan(0);
  }
});

test("overlap ring is only for overlaps that are tiny on screen; long strips are shown by their outline", () => {
  const strip = [{ x: 100, y: 50 }, { x: 226.2, y: 50 }, { x: 226.2, y: 51.2 }, { x: 100, y: 51.2 }]; // 同梱サンプルの LD × K と同じ 126×1.2px の帯
  expect(overlapRing(strip, 1)).toBeNull();
  const dot = [{ x: 10, y: 10 }, { x: 14, y: 10 }, { x: 14, y: 14 }, { x: 10, y: 14 }];
  expect(overlapRing(dot, 1)).toEqual({ cx: 12, cy: 12, r: 10 });
  // 縮小表示（1 画面 px = 8 単位）では、126 単位の帯も画面上は約 16px。見つけにくいので小さな輪を添える
  expect(overlapRing(strip, 8)).toEqual({ cx: 163.1, cy: 50.6, r: 63.1 + 64 });
  expect(overlapRing([], 1)).toBeNull();
});
