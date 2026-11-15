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

describe("mapApiError product images", () => {
  it.each([
    ["IMAGE_TOO_LARGE", "حجم تصویر بیش از حد مجاز است."],
    ["IMAGE_TYPE_NOT_ALLOWED", "فقط تصویر JPEG، PNG یا WebP پذیرفته می‌شود."],
    ["IMAGE_LIMIT_REACHED", "هر کالا حداکثر ۵ تصویر می‌تواند داشته باشد."],
    ["IMAGE_DIMENSIONS_TOO_LARGE", "ابعاد تصویر بیش از حد مجاز است."],
    ["IMAGE_DECODE_FAILED", "فایل تصویر قابل خواندن نیست."],
    ["IMAGE_DUPLICATE", "این تصویر قبلاً برای این کالا ثبت شده است."],
  ] as const)("maps %s to Persian", (code, expected) => {
    expect(mapApiProblem({ status: 422, code, title: code })).toBe(expected);
  });
});
