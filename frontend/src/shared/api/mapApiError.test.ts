import { describe, expect, it } from "vitest";
import { mapApiProblem } from "./mapApiError";

describe("mapApiError stock shortfall", () => {
  it("renders product name and available quantity in Persian", () => {
    const message = mapApiProblem(
      {
        status: 409,
        code: "INSUFFICIENT_STOCK",
        title: "Insufficient stock for reservation",
        errors: [{ sku: "SKU-100", requested: 5, available: 2 }],
      },
      { titleBySku: { "SKU-100": "برنج طارم" } },
    );

    expect(message).toContain("برنج طارم");
    expect(message).toContain("۲");
    expect(message).toMatch(/قابل فروش/);
  });
});
