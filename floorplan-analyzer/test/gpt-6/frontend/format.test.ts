import { expect, test } from "vitest";
import { fmt } from "../../../frontend/src/format";

test("reused number format preserves Japanese rounding and precision across calls", () => {
  for (const digits of [2, 0, 1, 3, 2]) {
    for (const n of [0, -0, 0.005, -0.005, 1234567.8915, -12.999, NaN, Infinity]) {
      expect(fmt(n, digits)).toBe(n.toLocaleString("ja-JP", { minimumFractionDigits: digits, maximumFractionDigits: digits }));
    }
  }
});
