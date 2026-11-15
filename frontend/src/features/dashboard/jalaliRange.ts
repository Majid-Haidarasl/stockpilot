/**
 * Jalali display helpers + Tehran-day presets for the dashboard date range.
 * All "today" / preset math uses Asia/Tehran, never browser-local calendar day.
 */

import { toPersianDigits } from "../../shared/money";
import { todayTehranYmd } from "./tehranRange";

const TEHRAN_TZ = "Asia/Tehran";

/** Parse YYYY-MM-DD as a Tehran calendar day → Date at noon UTC for adapter safety. */
export function ymdToUtcNoon(ymd: string): Date {
  return new Date(`${ymd}T12:00:00.000Z`);
}

/** Format a Date as Gregorian YYYY-MM-DD in Asia/Tehran. */
export function dateToTehranYmd(date: Date): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: TEHRAN_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

/** Shift a Tehran YMD by `deltaDays` (calendar days in Asia/Tehran). */
export function addTehranDays(ymd: string, deltaDays: number): string {
  const base = new Date(`${ymd}T12:00:00+03:30`);
  base.setTime(base.getTime() + deltaDays * 24 * 60 * 60 * 1000);
  return dateToTehranYmd(base);
}

export type DatePresetId = "today" | "last7" | "last30" | "thisMonth";

export type DatePreset = {
  id: DatePresetId;
  label: string;
  fromYmd: string;
  toYmd: string;
};

/** Presets relative to "now" interpreted in Asia/Tehran. */
export function tehranDatePresets(now = new Date()): DatePreset[] {
  const today = todayTehranYmd(now);
  const last7From = addTehranDays(today, -6);
  const last30From = addTehranDays(today, -29);

  // Jalali month start: walk back until month changes in Tehran timezone (fa-IR calendar).
  const thisMonthFrom = jalaliMonthStartTehranYmd(now);

  return [
    { id: "today", label: "امروز", fromYmd: today, toYmd: today },
    { id: "last7", label: "۷ روز اخیر", fromYmd: last7From, toYmd: today },
    { id: "last30", label: "۳۰ روز اخیر", fromYmd: last30From, toYmd: today },
    { id: "thisMonth", label: "این ماه", fromYmd: thisMonthFrom, toYmd: today },
  ];
}

/**
 * First day of the current Jalali month, as Gregorian YYYY-MM-DD in Tehran.
 * Uses fa-IR calendar parts so browser locale does not affect the month boundary.
 */
export function jalaliMonthStartTehranYmd(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-u-ca-persian", {
    timeZone: TEHRAN_TZ,
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).formatToParts(now);

  const year = Number(parts.find((p) => p.type === "year")?.value);
  const month = Number(parts.find((p) => p.type === "month")?.value);
  const day = Number(parts.find((p) => p.type === "day")?.value);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
    return todayTehranYmd(now);
  }

  // Walk back (day - 1) Tehran calendar days to land on Jalali day 1.
  return addTehranDays(todayTehranYmd(now), -(day - 1));
}

/** Display helper: Gregorian YMD → Persian digits Jalali short date via Intl. */
export function formatJalaliDisplay(ymd: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(ymd)) return ymd;
  const date = new Date(`${ymd}T12:00:00+03:30`);
  const formatted = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    timeZone: TEHRAN_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
  return toPersianDigits(formatted);
}
