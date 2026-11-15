const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

/**
 * Convert ASCII digits to Persian digits for display-only UI copy.
 *
 * Do NOT use on: controlled input values, IDs, data-testid text that tests assert
 * as ASCII, or any value sent to the API. Money formatting goes through formatRial.
 */
export function toPersianDigits(value: string): string {
  return value.replace(/\d/g, (digit) => PERSIAN_DIGITS[Number(digit)] ?? digit);
}
