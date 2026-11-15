import { describe, expect, it } from "vitest";
import type { Product } from "../../shared/api";
import { filterProductsBySearch } from "./productsFilter";

const sample: Product[] = [
  {
    id: "1",
    tenant_id: "t",
    sku: "SKU-100",
    title: "برنج طارم",
    unit_price: { amount: "1000", currency: "IRR" },
    is_active: true,
    stock_warning_threshold: 5,
    version: 1,
  },
  {
    id: "2",
    tenant_id: "t",
    sku: "OIL-9",
    title: "روغن",
    unit_price: { amount: "2000", currency: "IRR" },
    is_active: true,
    stock_warning_threshold: 5,
    version: 1,
  },
];

describe("filterProductsBySearch", () => {
  it("filters by title", () => {
    expect(filterProductsBySearch(sample, "برنج")).toHaveLength(1);
    expect(filterProductsBySearch(sample, "برنج")[0]?.sku).toBe("SKU-100");
  });

  it("filters by sku case-insensitively", () => {
    expect(filterProductsBySearch(sample, "oil")).toHaveLength(1);
  });

  it("returns all when search is empty", () => {
    expect(filterProductsBySearch(sample, "  ")).toHaveLength(2);
  });
});
