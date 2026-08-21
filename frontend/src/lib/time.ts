/** Compact relative time ("2h ago") without pulling in date-fns. */
export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

/** "Aug 2, 2026" — for showing an absolute "data as of" date next to a relative one. */
export function formatDate(iso: string): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** "Sep 4, 8:30 AM ET" — economic-calendar release times are quoted in US
 * market convention regardless of the viewer's own timezone, so the
 * timezone must be explicit rather than left to the browser's locale
 * (specs/026-macro-market-dashboard FR-022). */
export function formatEasternTime(iso: string): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const formatted = new Intl.DateTimeFormat(undefined, {
    timeZone: "America/New_York",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(d);
  return `${formatted} ET`;
}
