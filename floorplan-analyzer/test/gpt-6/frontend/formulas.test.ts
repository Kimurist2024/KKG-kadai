import { expect, test } from "vitest";
import { edgeWallFormula, roomWallFormula } from "../../../frontend/src/format";
import type { EdgeResult, RoomResult } from "../../../frontend/src/types";

test("wall formulas print ceiling and door heights with one decimal (2.0 m, never 2 m)", () => {
  const edge = { wall_length_m: 2, door_length_m: 1.2, wall_area_m2: 2.4 } as EdgeResult;
  expect(edgeWallFormula(edge, 2.4, 2)).toBe("2.00 m × 2.4 m − 1.20 m × 2.0 m = 2.40 m²");
  expect(edgeWallFormula({ ...edge, door_length_m: 0, wall_area_m2: 4.8 }, 2.4, 2)).toBe("2.00 m × 2.4 m = 4.80 m²");
  expect(edgeWallFormula({ ...edge, wall_length_m: 0 }, 2.4, 2)).toBe("壁なし (開口) → 0 m²");

  const room = { wall_length_m: 10, door_length_m: 1.2, wall_area_gross_m2: 24, door_area_m2: 2.4, wall_area_m2: 21.6 } as RoomResult;
  expect(roomWallFormula(room, 2.4, 2)).toBe("10.00 m × 2.4 m − 1.20 m × 2.0 m = 24.00 − 2.40 = 21.60 m²");
  expect(roomWallFormula({ ...room, door_length_m: 0, wall_area_m2: 24 }, 2.4, 2)).toBe("10.00 m × 2.4 m = 24.00 m²");
});
