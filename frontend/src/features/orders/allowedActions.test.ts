import { describe, expect, it } from "vitest";
import { allowedOrderActions } from "./allowedActions";

describe("allowedOrderActions", () => {
  it("matches status and role matrix for reserve/confirm/cancel/ship", () => {
    expect(allowedOrderActions("DRAFT", "sales")).toEqual({
      reserve: true,
      confirm: false,
      cancel: true,
      ship: false,
    });
    expect(allowedOrderActions("RESERVED", "sales")).toEqual({
      reserve: false,
      confirm: true,
      cancel: true,
      ship: false,
    });
    expect(allowedOrderActions("CONFIRMED", "warehouse")).toEqual({
      reserve: false,
      confirm: false,
      cancel: false,
      ship: true,
    });
    expect(allowedOrderActions("CONFIRMED", "sales")).toEqual({
      reserve: false,
      confirm: false,
      cancel: true,
      ship: false,
    });
    expect(allowedOrderActions("RESERVED", "viewer")).toEqual({
      reserve: false,
      confirm: false,
      cancel: false,
      ship: false,
    });
    expect(allowedOrderActions("SHIPPED", "admin")).toEqual({
      reserve: false,
      confirm: false,
      cancel: false,
      ship: false,
    });
  });
});
