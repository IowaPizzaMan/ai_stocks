// Spec: specs/026-macro-market-dashboard/contracts/macro-api.md,
//       specs/026-macro-market-dashboard/data-model.md §6
//
// GET /market/treasury-curve already returns one row per maturity with
// current/month_ago/year_ago aligned and spreads pre-computed — the backend
// owns the arithmetic (research D7). What's left here is display-only:
// deciding whether a comparison overlay has anything to draw, and formatting
// basis-point/yield values consistently across the curve chart and spread
// tiles.
import type { CurvePoint, Spread } from "../api/types";

/** True when at least one maturity has a value for this overlay — a
 * comparison_sessions entry of null means every point is null too, but this
 * also protects against the (unexpected) case of a partially-null overlay. */
export function hasOverlay(curve: CurvePoint[], key: "month_ago" | "year_ago"): boolean {
  return curve.some((p) => p[key] != null);
}

/** "+46 bps" / "-20 bps" / "—" for a missing reading. Sign is always shown on
 * a non-zero value so a widening vs. narrowing spread reads at a glance. */
export function formatBps(value: number | null): string {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(0)} bps`;
}

/** "4.65%" / "—" for a missing yield reading. */
export function formatYield(value: number | null): string {
  if (value == null) return "—";
  return `${value.toFixed(2)}%`;
}

/** Session-over-session change, signed and labeled for a spread tile. */
export function formatChange(changeBps: number | null): string {
  if (changeBps == null) return "no prior session";
  const sign = changeBps > 0 ? "+" : "";
  return `${sign}${changeBps.toFixed(0)} bps vs prior session`;
}

/** Whether a spread has anything at all to render — an empty-collection
 * response still carries all three spread keys with null values (contracts),
 * so callers need this to decide whether to show a value or an unavailable state. */
export function hasSpreadData(spread: Spread): boolean {
  return spread.current_bps != null;
}
