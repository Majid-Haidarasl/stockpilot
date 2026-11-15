import { toPersianDigits } from "./persianDigits";

/**
 * Format an ISO timestamp for display in Asia/Tehran wall time.
 * Output uses Persian digits; does not alter the underlying ISO value.
 */
export function formatTehranDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return toPersianDigits(iso);
  }
  const formatted = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
  return toPersianDigits(formatted.replace(", ", " "));
}
