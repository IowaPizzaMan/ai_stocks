// Spec: specs/026-macro-market-dashboard/contracts/macro-api.md
//
// Upcoming US high/medium-impact releases and what recently reported. The
// comparison label is deliberately neutral — above/below/in line against the
// estimate, nothing asserting whether a result is good or bad for the market
// (FR-021b). GET /market/economic-calendar already filters and classifies
// server side; this only lays it out.
import type { EconomicEvent, ReportedEconomicEvent } from "../../api/types";
import { formatEasternTime } from "../../lib/time";

const COMPARISON_LABEL: Record<NonNullable<ReportedEconomicEvent["comparison"]>, string> = {
  above: "above estimate",
  below: "below estimate",
  in_line: "in line",
};

function ImpactBadge({ impact }: { impact: "High" | "Medium" }) {
  return (
    <span className="rounded-full border border-zinc-700 px-1.5 py-0.5 text-[10px] uppercase text-zinc-400">
      {impact}
    </span>
  );
}

function UpcomingRow({ event }: { event: EconomicEvent }) {
  return (
    <li className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <div className="flex min-w-0 items-center gap-2">
        <ImpactBadge impact={event.impact} />
        <span className="truncate text-zinc-200">{event.event}</span>
      </div>
      <div className="flex shrink-0 items-center gap-3 text-xs text-zinc-500">
        <span>{formatEasternTime(event.date)}</span>
        <span>
          est. {event.estimate != null ? `${event.estimate}${event.unit ?? ""}` : "unavailable"}
        </span>
      </div>
    </li>
  );
}

function ReportedRow({ event }: { event: ReportedEconomicEvent }) {
  return (
    <li className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <div className="flex min-w-0 items-center gap-2">
        <ImpactBadge impact={event.impact} />
        <span className="truncate text-zinc-200">{event.event}</span>
      </div>
      <div className="flex shrink-0 items-center gap-3 text-xs text-zinc-500">
        <span>{formatEasternTime(event.date)}</span>
        <span className="text-zinc-300">
          {event.actual}
          {event.unit ?? ""}
        </span>
        <span>{event.comparison ? COMPARISON_LABEL[event.comparison] : "no estimate"}</span>
      </div>
    </li>
  );
}

export default function EconomicCalendarPanel({
  upcoming,
  reported,
}: {
  upcoming: EconomicEvent[];
  reported: ReportedEconomicEvent[];
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div>
        <p className="mb-1 text-[10px] uppercase tracking-wide text-zinc-600">Upcoming releases</p>
        {upcoming.length === 0 ? (
          <p className="py-3 text-sm text-zinc-600">No major releases scheduled.</p>
        ) : (
          <ul className="divide-y divide-zinc-800">
            {upcoming.map((event) => (
              <UpcomingRow key={`${event.date}-${event.event}`} event={event} />
            ))}
          </ul>
        )}
      </div>
      <div>
        <p className="mb-1 text-[10px] uppercase tracking-wide text-zinc-600">Recently reported</p>
        {reported.length === 0 ? (
          <p className="py-3 text-sm text-zinc-600">Nothing has reported in this window yet.</p>
        ) : (
          <ul className="divide-y divide-zinc-800">
            {reported.map((event) => (
              <ReportedRow key={`${event.date}-${event.event}`} event={event} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
