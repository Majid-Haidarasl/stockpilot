import { describe, expect, it } from "vitest";
import {
  isValidYmdRange,
  tehranDayEndUtcIso,
  tehranDayStartUtcIso,
} from "./tehranRange";

describe("tehranRange", () => {
  it("converts Tehran day bounds to UTC ISO", () => {
    // 2024-03-20 00:00 +03:30 = 2024-03-19 20:30 UTC
    expect(tehranDayStartUtcIso("2024-03-20")).toBe("2024-03-19T20:30:00.000Z");
    expect(tehranDayEndUtcIso("2024-03-20")).toBe("2024-03-20T20:29:59.999Z");
  });

  it("validates from <= to", () => {
    expect(isValidYmdRange("2024-01-01", "2024-01-02")).toBe(true);
    expect(isValidYmdRange("2024-01-02", "2024-01-01")).toBe(false);
  });
});
