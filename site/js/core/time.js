// Dates and clocks, always in the newspaper's own timezone (manifest.site.timezone), not the reader's.

let zone = 'Asia/Kolkata';
let zoneLabel = 'IST';

export function setZone(timezone) {
  if (typeof timezone !== 'string' || !timezone) return; // no zone in the manifest: keep the default, never the reader's
  try {
    new Intl.DateTimeFormat('en-GB', { timeZone: timezone });
    zone = timezone;
    const part = new Intl.DateTimeFormat('en-US', { timeZone: timezone, timeZoneName: 'short' })
      .formatToParts(new Date()).find((p) => p.type === 'timeZoneName');
    zoneLabel = timezone === 'Asia/Kolkata' ? 'IST' : part?.value || '';
  } catch {
    // keep the default zone when the manifest names one this browser does not know
  }
}

export const zoneName = () => zoneLabel;
export const zoneId = () => zone;

function parts(date, options) {
  const out = {};
  for (const part of new Intl.DateTimeFormat('en-GB', { timeZone: zone, ...options }).formatToParts(date)) out[part.type] = part.value;
  return out;
}

const toDate = (value) => (value instanceof Date ? value : new Date(value));

/** "07:42" */
export function clock(value) {
  const p = parts(toDate(value), { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  return `${p.hour}:${p.minute}`;
}

/** "2026-11-11" in the paper's zone. */
export function localDate(value) {
  const p = parts(toDate(value), { year: 'numeric', month: '2-digit', day: '2-digit' });
  return `${p.year}-${p.month}-${p.day}`;
}

/** A date-only string ("2026-11-11") as a Date at noon UTC, safe to format in any zone. */
export const fromDay = (dayString) => new Date(`${dayString}T12:00:00Z`);

/** "Wednesday 11 November 2026" */
export function longDate(value) {
  const p = parts(toDate(value), { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  return `${p.weekday} ${p.day} ${p.month} ${p.year}`;
}

/** "Wed 11 Nov" */
export function shortDate(value) {
  const p = parts(toDate(value), { weekday: 'short', day: 'numeric', month: 'short' });
  return `${p.weekday} ${p.day} ${p.month}`;
}

/** "Wed" */
export const weekday = (value) => parts(toDate(value), { weekday: 'short' }).weekday;

/**
 * A stamp for a story relative to a reference day: "07:42" on that day, "Tue 21:10" otherwise,
 * "9 Nov" when it is more than six days away.
 */
export function stamp(value, referenceDay) {
  const date = toDate(value);
  const dayOf = localDate(date);
  if (dayOf === referenceDay) return clock(date);
  const apart = Math.abs(fromDay(dayOf) - fromDay(referenceDay)) / 86400000;
  if (apart <= 6) return `${weekday(date)} ${clock(date)}`;
  const p = parts(date, { day: 'numeric', month: 'short' });
  return `${p.day} ${p.month}`;
}

/** "3 min ago", "5 h ago", "2 d ago" */
export function ago(value, now = Date.now()) {
  const minutes = Math.max(0, Math.round((now - toDate(value).getTime()) / 60000));
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 36) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

export const hoursSince = (value, now = Date.now()) => (now - toDate(value).getTime()) / 3600000;
