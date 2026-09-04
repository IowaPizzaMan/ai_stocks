// specs/037-stocks-conviction-and-activity US2 (FR-010).
// Renders the plain-language rule trace behind a stock's conviction rating —
// which of the three gating conditions passed/failed, so "high conviction"
// means something specific and auditable rather than an unexplained number.
import type { ConvictionDetail, StrategyCallDetail, ZScoreQuartileStatus } from "../../api/types";

const STRATEGY_LABEL: Record<string, string> = {
  the_strat: "The Strat",
  accumulation: "Accumulation",
  gap_analysis: "Gap Analysis",
};

const CALL_STYLES: Record<string, string> = {
  buy: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  "not-buy": "border-red-500/30 bg-red-500/10 text-red-400",
  "no-call": "border-zinc-700 bg-zinc-800 text-zinc-500",
};

function StrategyRow({ name, detail }: { name: string; detail: StrategyCallDetail }) {
  return (
    <li className="flex items-start gap-2">
      <span
        className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${CALL_STYLES[detail.call]}`}
      >
        {STRATEGY_LABEL[name] ?? name}: {detail.call}
      </span>
      <span className="text-xs text-zinc-500">{detail.why}</span>
    </li>
  );
}

function ZScoreRow({ label, status }: { label: string; status: ZScoreQuartileStatus }) {
  if (status.in_bottom_quartile === null) {
    return (
      <li className="text-zinc-500">
        {label} z-score: insufficient price history ({status.sample} of the needed sample)
      </li>
    );
  }
  return (
    <li className={status.in_bottom_quartile ? "text-emerald-400" : "text-zinc-400"}>
      {label} z-score: {status.value?.toFixed(2)} —{" "}
      {status.in_bottom_quartile ? "in its bottom quartile" : "not in its bottom quartile"}
      <span className="text-zinc-600"> (25th pct: {status.p25?.toFixed(2)})</span>
    </li>
  );
}

export default function ConvictionRationale({ detail }: { detail?: ConvictionDetail | null }) {
  if (!detail) {
    return (
      <p className="text-sm text-zinc-500">
        Rating not yet recomputed under the current rules — re-run analysis to see the
        breakdown.
      </p>
    );
  }

  const { conditions, blockers, caveats, missing_inputs: missingInputs } = detail;

  return (
    <div className="space-y-3 text-sm">
      {detail.level === "high" ? (
        <p className="text-emerald-400">
          High conviction: every entry strategy calls buy, both z-score timeframes sit in
          their own bottom quartile, and revenue is growing YoY with no sequential decline.
        </p>
      ) : (
        blockers.length > 0 && (
          <ul className="space-y-1 text-amber-400">
            {blockers.map((b) => (
              <li key={b}>⚑ {b}</li>
            ))}
          </ul>
        )
      )}

      <ul className="space-y-1.5">
        <StrategyRow name="the_strat" detail={conditions.strategies.calls.the_strat} />
        <StrategyRow name="accumulation" detail={conditions.strategies.calls.accumulation} />
        <StrategyRow name="gap_analysis" detail={conditions.strategies.calls.gap_analysis} />
      </ul>

      <ul className="space-y-1 text-xs">
        <ZScoreRow label="Daily" status={conditions.zscore.daily} />
        <ZScoreRow label="Weekly" status={conditions.zscore.weekly} />
      </ul>

      <p className="text-xs text-zinc-400">
        Revenue: {conditions.revenue.yoy_growing ? "growing" : "not growing"} YoY
        {conditions.revenue.growth_yoy != null &&
          ` (${(conditions.revenue.growth_yoy * 100).toFixed(1)}%)`}
        {", "}
        {conditions.revenue.qoq_declining ? "declined" : "did not decline"} QoQ
        {conditions.revenue.change_qoq != null &&
          ` (${(conditions.revenue.change_qoq * 100).toFixed(1)}%)`}
        .
      </p>

      {missingInputs.length > 0 && (
        <p className="text-xs text-zinc-600">
          Not enough data for: {missingInputs.join(", ")}.
        </p>
      )}

      {caveats.length > 0 && (
        <p className="text-xs text-zinc-500">
          {caveats.join(" ")}
        </p>
      )}
    </div>
  );
}
