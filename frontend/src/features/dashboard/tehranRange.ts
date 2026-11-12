/**
 * Convert Asia/Tehran calendar dates to UTC day boundaries for the dashboard API.
 * Iran standard offset is UTC+03:30 year-round (no DST).
 */

const TEHRAN_OFFSET = "+03:30";

export function tehranDayStartUtcIso(dateYmd: string): string {
  return new Date(`${dateYmd}T00:00:00${TEHRAN_OFFSET}`).toISOString();
}

export function tehranDayEndUtcIso(dateYmd: string): string {
  return new Date(`${dateYmd}T23:59:59.999${TEHRAN_OFFSET}`).toISOString();
}

/** Today as YYYY-MM-DD in Asia/Tehran. */
export function todayTehranYmd(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

export function isValidYmdRange(fromYmd: string, toYmd: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(fromYmd) || !/^\d{4}-\d{2}-\d{2}$/.test(toYmd)) {
    return false;
  }
  return fromYmd <= toYmd;
}
