import { describe, expect, it } from "vitest";
import { formatRial } from "./money";

describe("formatRial", () => {
  it("keeps big integer amounts exact without JS number coercion", () => {
    const amount = "9007199254740993"; // beyond Number.MAX_SAFE_INTEGER
    const formatted = formatRial(amount);
    expect(formatted).toContain("۹٬۰۰۷٬۱۹۹٬۲۵۴٬۷۴۰٬۹۹۳");
    expect(formatted.endsWith("ریال")).toBe(true);
    // Reconstruct digits from grouped Persian output (proves no Number rounding).
    const ascii = formatted
      .replace(/[^\u06F0-\u06F9]/g, "")
      .replace(/[\u06F0-\u06F9]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)));
    expect(ascii).toBe(amount);
    expect(String(Number(amount))).not.toBe(amount);
  });
});
