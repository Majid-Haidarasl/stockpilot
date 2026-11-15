import { describe, expect, it } from "vitest";
import { isLowStock } from "./lowStock";

describe("isLowStock", () => {
  it("is true when available equals threshold", () => {
    expect(isLowStock(5, 5)).toBe(true);
  });

  it("is true when available is below threshold", () => {
    expect(isLowStock(2, 5)).toBe(true);
  });

  it("is false when available is above threshold", () => {
    expect(isLowStock(6, 5)).toBe(false);
  });
});
