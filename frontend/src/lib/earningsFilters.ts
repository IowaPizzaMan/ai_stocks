// Pure client-side predicate for the earnings table's size sliders and
// "big movers only" toggle. Everything here filters rows already held by the
// client — no network call (FR-027b). spec: specs/025-earnings-page-filters
// data-model.md ss6.
import type { EarningsCalendarEntry } from "../api/types";

export const BIG_MOVER_THRESHOLD_PCT = 10;

export interface EarningsFilterOptions {
  minRev: number;
  minEps: number;
  moversOnly: boolean;
}

export function filterEntries(
  entries: EarningsCalendarEntry[],
  { minRev, minEps, moversOnly }: EarningsFilterOptions,
): EarningsCalendarEntry[] {
  return entries.filter((e) => {
    const rev = e.revenue_actual ?? e.revenue_estimate;
    // FR-016: abs() so a large loss (e.g. -2.50) is never filtered out by a
    // magnitude floor — the sign doesn't make the number less significant.
    const eps = e.eps_actual ?? e.eps_estimate;
    const epsMagnitude = eps === null ? null : Math.abs(eps);

    // A floor at zero filters nothing — keeps rows with no figure at all
    // (FR-017). Above zero, a missing figure is exactly the noise this
    // control exists to remove.
    if (minRev > 0 && (rev === null || rev < minRev)) return false;
    if (minEps > 0 && (epsMagnitude === null || epsMagnitude < minEps)) return false;

    if (moversOnly) {
      const epsSurprise = e.eps_surprise_pct;
      const revSurprise = e.revenue_surprise_pct;
      if (epsSurprise === null && revSurprise === null) return false;
      const maxAbsSurprise = Math.max(Math.abs(epsSurprise ?? 0), Math.abs(revSurprise ?? 0));
      if (maxAbsSurprise < BIG_MOVER_THRESHOLD_PCT) return false;
    }

    return true;
  });
}
