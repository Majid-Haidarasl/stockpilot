const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

/** Convert ASCII digits to Persian digits without coercing money to JS number. */
export function toPersianDigits(value: string): string {
  return value.replace(/\d/g, (digit) => PERSIAN_DIGITS[Number(digit)] ?? digit);
}

/**
 * Format an integer rial amount string with Persian digit grouping.
 * Never converts the amount to a JS number (safe for values beyond Number.MAX_SAFE_INTEGER).
 */
export function formatRial(amount: string): string {
  const trimmed = amount.trim();
  if (!/^-?\d+$/.test(trimmed)) {
    throw new Error(`Invalid rial amount: ${amount}`);
  }
  const negative = trimmed.startsWith("-");
  const digits = negative ? trimmed.slice(1) : trimmed;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, "٬");
  const withSign = negative ? `-${grouped}` : grouped;
  return `${toPersianDigits(withSign)} ریال`;
}
