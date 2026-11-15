import { describe, expect, it } from "vitest";
import { toPersianDigits } from "./persianDigits";

describe("toPersianDigits", () => {
  it("maps ASCII digits to Persian digits for display", () => {
    expect(toPersianDigits("0123456789")).toBe("۰۱۲۳۴۵۶۷۸۹");
  });

  it("leaves non-digit characters unchanged", () => {
    expect(toPersianDigits("SKU-42")).toBe("SKU-۴۲");
  });
});
