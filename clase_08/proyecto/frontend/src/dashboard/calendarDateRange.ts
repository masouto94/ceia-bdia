export type CalendarDateRangeValidation = {
  valid: boolean;
  inclusiveDays: number;
};

const calendarOrdinal = (value: string): number | null => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const timestamp = Date.UTC(year, month - 1, day);
  const parsed = new Date(timestamp);
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    return null;
  }
  return timestamp / 86_400_000;
};

export function validateCalendarDateRange(
  from: string,
  to: string,
  maximumInclusiveDays: number,
): CalendarDateRangeValidation {
  const start = calendarOrdinal(from);
  const end = calendarOrdinal(to);
  if (start === null || end === null) return { valid: false, inclusiveDays: 0 };
  const inclusiveDays = end - start + 1;
  return {
    valid: inclusiveDays >= 1 && inclusiveDays <= maximumInclusiveDays,
    inclusiveDays,
  };
}
