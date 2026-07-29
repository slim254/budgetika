/**
 * Formats a Date using its local calendar date (year-month-day), not UTC.
 *
 * `date.toISOString().split("T")[0]` is a common but incorrect shortcut: it
 * converts to UTC first, so for users east of UTC (e.g. UTC+2), anything
 * before 2am/3am local time gets stamped with *yesterday's* date. This
 * helper reads the local year/month/day directly instead.
 */
export function formatDateForAPI(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
