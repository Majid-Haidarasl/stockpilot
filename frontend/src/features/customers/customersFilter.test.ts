import { describe, expect, it } from "vitest";
import type { Customer } from "../../shared/api";
import { filterCustomersBySearch } from "./customersFilter";

const items: Customer[] = [
  {
    id: "1",
    tenant_id: "t1",
    name: "علی رضایی",
    phone: "09121234567",
    email: null,
    notes: null,
    version: 1,
  },
  {
    id: "2",
    tenant_id: "t1",
    name: "مریم احمدی",
    phone: null,
    email: null,
    notes: null,
    version: 1,
  },
  {
    id: "3",
    tenant_id: "t1",
    name: "Shop One",
    phone: "0218899",
    email: null,
    notes: null,
    version: 1,
  },
];

describe("filterCustomersBySearch", () => {
  it("returns all items when search is empty", () => {
    expect(filterCustomersBySearch(items, "  ")).toEqual(items);
  });

  it("filters by name (case-insensitive)", () => {
    expect(filterCustomersBySearch(items, "shop")).toEqual([items[2]]);
  });

  it("filters by phone", () => {
    expect(filterCustomersBySearch(items, "0912")).toEqual([items[0]]);
  });
});
