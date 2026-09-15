import { expect, test } from "vitest";
import { fitRoomViewport } from "../../../frontend/src/viewport";
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
