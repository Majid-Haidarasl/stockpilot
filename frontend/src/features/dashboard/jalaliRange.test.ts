import { describe, expect, it } from "vitest";
import {
  addTehranDays,
  dateToTehranYmd,
  jalaliMonthStartTehranYmd,
  tehranDatePresets,
  ymdToUtcNoon,
} from "./jalaliRange";
import { todayTehranYmd } from "./tehranRange";

describe("jalaliRange Tehran presets", () => {
  it("ymdToUtcNoon parses Gregorian YMD", () => {
    const d = ymdToUtcNoon("2024-03-20");
    expect(d.toISOString()).toBe("2024-03-20T12:00:00.000Z");
  });

  it("addTehranDays shifts by calendar days in Tehran", () => {
    // Around Nowruz / DST-free Iran offset
    expect(addTehranDays("2024-03-20", -1)).toBe("2024-03-19");
    expect(addTehranDays("2024-03-20", 1)).toBe("2024-03-21");
  });

  it("today preset uses Asia/Tehran today, not a fixed UTC day", () => {
    const now = new Date("2024-03-20T01:00:00.000Z"); // still 1402-12-30 / 2024-03-20 in Tehran
    const presets = tehranDatePresets(now);
    const today = presets.find((p) => p.id === "today");
    expect(today?.fromYmd).toBe(todayTehranYmd(now));
    expect(today?.toYmd).toBe(todayTehranYmd(now));
  });

  it("last7 spans 7 Tehran days inclusive", () => {
    const now = new Date("2024-06-15T12:00:00.000Z");
    const presets = tehranDatePresets(now);
    const last7 = presets.find((p) => p.id === "last7");
    const today = todayTehranYmd(now);
    expect(last7?.toYmd).toBe(today);
    expect(last7?.fromYmd).toBe(addTehranDays(today, -6));
  });

  it("thisMonth starts on Jalali day 1 in Tehran", () => {
    // 2024-06-15 ≈ 1403-03-26 → month start ≈ 1403-03-01 → 2024-05-21
    const now = new Date("2024-06-15T08:00:00.000Z");
    const start = jalaliMonthStartTehranYmd(now);
    const dayPart = new Intl.DateTimeFormat("en-u-ca-persian", {
      timeZone: "Asia/Tehran",
      day: "numeric",
    }).format(new Date(`${start}T12:00:00+03:30`));
    expect(Number(dayPart)).toBe(1);
    expect(dateToTehranYmd(new Date(`${start}T12:00:00+03:30`))).toBe(start);
  });
});
