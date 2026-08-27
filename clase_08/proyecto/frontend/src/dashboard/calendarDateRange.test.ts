import { describe, expect, it } from "vitest";
import { validateCalendarDateRange } from "./calendarDateRange";

describe("validateCalendarDateRange", () => {
  it("counts inclusive calendar dates without local elapsed-time arithmetic", () => {
    expect(validateCalendarDateRange("2026-01-01", "2026-01-01", 31)).toEqual({
      valid: true,
      inclusiveDays: 1,
    });
    expect(validateCalendarDateRange("2026-01-01", "2026-01-31", 31)).toEqual({
      valid: true,
      inclusiveDays: 31,
    });
    expect(validateCalendarDateRange("2026-01-01", "2026-02-01", 31)).toEqual({
      valid: false,
      inclusiveDays: 32,
    });
  });

  it("has identical calendar semantics across a daylight-saving boundary", () => {
    expect(validateCalendarDateRange("2026-03-08", "2026-03-10", 31)).toEqual({
      valid: true,
      inclusiveDays: 3,
    });
  });

  it("enforces the dashboard's inclusive 366-day maximum and rejects reversed ranges", () => {
    expect(
      validateCalendarDateRange("2024-01-01", "2024-12-31", 366),
    ).toMatchObject({
      valid: true,
      inclusiveDays: 366,
    });
    expect(
      validateCalendarDateRange("2024-01-01", "2025-01-01", 366),
    ).toMatchObject({
      valid: false,
      inclusiveDays: 367,
    });
    expect(
      validateCalendarDateRange("2026-02-01", "2026-01-31", 366),
    ).toMatchObject({
      valid: false,
      inclusiveDays: 0,
    });
  });
});
