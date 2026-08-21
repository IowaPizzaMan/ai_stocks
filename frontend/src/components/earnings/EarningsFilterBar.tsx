// Spec: specs/025-earnings-page-filters. Date presets replace what was
// originally asked for as a slider — a continuous drag makes every position a
// candidate provider request; a bounded preset set caches cleanly at one
// request per click (spec Clarifications, research.md D8). The revenue/EPS
// sliders and the "big movers" toggle stay real range inputs, since they
// filter client-side and never touch the network (FR-027b).
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

interface DatePreset {
  key: string;
  label: string;
  from: (today: Date) => string;
  to: (today: Date) => string;
}

function toISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function addDays(base: Date, days: number): Date {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  return d;
}

// data-model.md ss7 — resolved fresh against "today" each time a preset is clicked.
const PRESETS: DatePreset[] = [
  { key: "today", label: "Today", from: (t) => toISODate(t), to: (t) => toISODate(t) },
  {
    key: "pm2", label: "±2 days",
    from: (t) => toISODate(addDays(t, -2)), to: (t) => toISODate(addDays(t, 2)),
  },
  {
    key: "last7", label: "Last 7 days",
    from: (t) => toISODate(addDays(t, -7)), to: (t) => toISODate(t),
  },
  {
    key: "next7", label: "Next 7 days",
    from: (t) => toISODate(t), to: (t) => toISODate(addDays(t, 7)),
  },
  {
    key: "pm2w", label: "±2 weeks",
    from: (t) => toISODate(addDays(t, -14)), to: (t) => toISODate(addDays(t, 14)),
  },
  {
    key: "pm1m", label: "±1 month",
    from: (t) => toISODate(addDays(t, -30)), to: (t) => toISODate(addDays(t, 30)),
  },
];

const DEFAULT_PRESET = PRESETS[1]; // ±2 days — FR-002

export const DEFAULT_MIN_REV = 10_000_000; // $10M, spec Clarifications
export const DEFAULT_MIN_EPS = 0.01;

/** The page's default window absent any URL params (FR-002) — exported so
 * EarningsScan.tsx can resolve the same default when calling the calendar
 * hook, without duplicating the preset definition. */
export function getDefaultWindow(today: Date = new Date()): { from: string; to: string } {
  return { from: DEFAULT_PRESET.from(today), to: DEFAULT_PRESET.to(today) };
}

function formatWindowLabel(from: string, to: string): string {
  const fmt = (iso: string) => {
    const d = new Date(`${iso}T00:00:00`);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  };
  return `${fmt(from)} – ${fmt(to)}`;
}

interface EarningsFilterBarProps {
  visibleCount?: number;
  totalCount?: number;
}

export default function EarningsFilterBar({ visibleCount, totalCount }: EarningsFilterBarProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const today = new Date();

  const from = searchParams.get("from") ?? DEFAULT_PRESET.from(today);
  const to = searchParams.get("to") ?? DEFAULT_PRESET.to(today);
  const minRev = Number(searchParams.get("min_rev") ?? DEFAULT_MIN_REV);
  const minEps = Number(searchParams.get("min_eps") ?? DEFAULT_MIN_EPS);
  const moversOnly = searchParams.get("movers") === "1";

  const [customFrom, setCustomFrom] = useState(from);
  const [customTo, setCustomTo] = useState(to);

  // URL is the source of truth (preset click, back/forward nav) — resync local inputs.
  useEffect(() => {
    setCustomFrom(from);
    setCustomTo(to);
  }, [from, to]);

  const activePresetKey = PRESETS.find(
    (p) => p.from(today) === from && p.to(today) === to,
  )?.key;

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (value === null) next.delete(key);
    else next.set(key, value);
    setSearchParams(next, { replace: true });
  };

  const applyWindow = (newFrom: string, newTo: string) => {
    if (newFrom > newTo) return; // FR-004: never write an inverted range
    const next = new URLSearchParams(searchParams);
    next.set("from", newFrom);
    next.set("to", newTo);
    setSearchParams(next, { replace: true });
  };

  const selectPreset = (preset: DatePreset) => applyWindow(preset.from(today), preset.to(today));

  // Custom date entry commits once the user stops typing (FR-027a) — presets
  // commit immediately since a click is already exactly one window.
  useEffect(() => {
    if (customFrom === from && customTo === to) return;
    const t = setTimeout(() => applyWindow(customFrom, customTo), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [customFrom, customTo]);

  const invalidCustomRange = customFrom > customTo;
  const bounds = { min: toISODate(addDays(today, -30)), max: toISODate(addDays(today, 30)) };

  return (
    <div className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1" role="group" aria-label="Date range presets">
          {PRESETS.map((preset) => (
            <button
              key={preset.key}
              type="button"
              aria-pressed={activePresetKey === preset.key}
              onClick={() => selectPreset(preset)}
              className={`rounded px-3 py-1 text-sm ${
                activePresetKey === preset.key
                  ? "bg-indigo-600 text-white"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <label className="flex items-center gap-1">
            Custom:
            <input
              type="date"
              aria-label="Custom start date"
              value={customFrom}
              min={bounds.min}
              max={bounds.max}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-zinc-200"
            />
          </label>
          <span>to</span>
          <input
            type="date"
            aria-label="Custom end date"
            value={customTo}
            min={bounds.min}
            max={bounds.max}
            onChange={(e) => setCustomTo(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-zinc-200"
          />
        </div>
      </div>

      {invalidCustomRange && (
        <p className="text-xs text-red-400">End date must not be before start date.</p>
      )}

      <div className="flex flex-wrap items-center gap-4 border-t border-zinc-800 pt-3">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-zinc-300">{formatWindowLabel(from, to)}</span>
          <span className="text-zinc-500">
            · {visibleCount ?? 0}
            {totalCount !== undefined && totalCount !== visibleCount ? ` of ${totalCount}` : ""}{" "}
            companies
          </span>
        </div>

        <label className="flex items-center gap-2 text-sm text-zinc-400">
          Min revenue
          <input
            type="range"
            aria-label="Minimum revenue"
            min={0}
            max={1_000_000_000}
            step={1_000_000}
            value={minRev}
            onChange={(e) => setParam("min_rev", e.target.value === String(DEFAULT_MIN_REV) ? null : e.target.value)}
            className="w-32"
          />
          <span className="w-16 text-right text-zinc-300">
            {minRev >= 1_000_000 ? `$${(minRev / 1_000_000).toFixed(0)}M` : `$${minRev}`}
          </span>
        </label>

        <label className="flex items-center gap-2 text-sm text-zinc-400">
          Min |EPS|
          <input
            type="range"
            aria-label="Minimum EPS magnitude"
            min={0}
            max={2}
            step={0.01}
            value={minEps}
            onChange={(e) => setParam("min_eps", e.target.value === String(DEFAULT_MIN_EPS) ? null : e.target.value)}
            className="w-32"
          />
          <span className="w-12 text-right text-zinc-300">${minEps.toFixed(2)}</span>
        </label>

        <label className="flex items-center gap-2 text-sm text-zinc-400">
          <input
            type="checkbox"
            aria-label="Big movers only"
            checked={moversOnly}
            onChange={(e) => setParam("movers", e.target.checked ? "1" : null)}
          />
          Big movers only
        </label>
      </div>
    </div>
  );
}
