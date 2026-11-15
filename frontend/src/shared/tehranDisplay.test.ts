import { describe, expect, it } from "vitest";
import { formatTehranDateTime } from "./tehranDisplay";

describe("formatTehranDateTime", () => {
  it("formats a known UTC instant in Asia/Tehran with Persian digits", () => {
    // 2024-03-20T12:00:00Z = 15:30 Tehran (+03:30, no DST)
    const out = formatTehranDateTime("2024-03-20T12:00:00.000Z");
    expect(out).toContain("۲۰۲۴");
    expect(out).toContain("۱۵");
    expect(out).not.toMatch(/[0-9]/);
  });
});
