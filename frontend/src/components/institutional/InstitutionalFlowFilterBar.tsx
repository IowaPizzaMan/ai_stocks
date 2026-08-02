// Spec: specs/component-specs/frontend/components/institutional/InstitutionalFlowFilterBar.md
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTriggerInstitutionalScan } from "../../hooks/useInstitutionalFlow";

const ACTIONS = [
  { value: "new_position", label: "New Position" },
  { value: "add", label: "Add" },
  { value: "trim", label: "Trim" },
  { value: "exit", label: "Exit" },
];

export default function InstitutionalFlowFilterBar() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [fund, setFund] = useState(searchParams.get("fund") ?? "");
  const [ticker, setTicker] = useState(searchParams.get("ticker") ?? "");
  const [notability, setNotability] = useState(
    Number(searchParams.get("min_notability") ?? 0),
  );
  const scan = useTriggerInstitutionalScan();

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (!value || next.get(key) === value) next.delete(key);
    else next.set(key, value);
    setSearchParams(next, { replace: true });
  };

  // debounce the text inputs into URL params
  useEffect(() => {
    const t = setTimeout(() => {
      const next = new URLSearchParams(searchParams);
      if (fund.trim()) next.set("fund", fund.trim());
      else next.delete("fund");
      const tk = ticker.trim().toUpperCase();
      if (tk) next.set("ticker", tk);
      else next.delete("ticker");
      if (next.toString() !== searchParams.toString())
        setSearchParams(next, { replace: true });
    }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fund, ticker]);

  const hasFilters =
    !!searchParams.get("action") || !!searchParams.get("fund") ||
    !!searchParams.get("ticker") || !!searchParams.get("min_notability");

  const clear = () => {
    setFund("");
    setTicker("");
    setNotability(0);
    setSearchParams(new URLSearchParams(), { replace: true });
  };

  return (
    <div className="sticky top-0 z-10 -mx-6 border-b border-zinc-800 bg-zinc-950/95 px-6 py-3 backdrop-blur">
      <div className="flex flex-wrap items-center gap-2">
        {ACTIONS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setParam("action", value)}
            className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
              searchParams.get("action") === value
                ? "border-sky-500 bg-sky-500/10 text-sky-300"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
            }`}
          >
            {label}
          </button>
        ))}

        <span className="mx-2 hidden h-5 w-px bg-zinc-800 sm:block" />

        <input
          value={fund}
          onChange={(e) => setFund(e.target.value)}
          placeholder="Fund…"
          className="w-36 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm placeholder:text-zinc-600 focus:border-sky-500 focus:outline-none"
        />
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="Ticker…"
          className="w-24 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm uppercase placeholder:normal-case placeholder:text-zinc-600 focus:border-sky-500 focus:outline-none"
        />

        <label className="flex items-center gap-2 text-xs text-zinc-400">
          <span>Min notability</span>
          <input
            type="range"
            min={0}
            max={100}
            step={10}
            value={notability}
            onChange={(e) => setNotability(Number(e.target.value))}
            onMouseUp={() => setParam("min_notability", notability ? String(notability) : "")}
            onTouchEnd={() => setParam("min_notability", notability ? String(notability) : "")}
            className="w-24 accent-sky-500"
          />
          <span className="w-6 tabular-nums text-zinc-300">{notability || "—"}</span>
        </label>

        {hasFilters && (
          <button
            onClick={clear}
            className="text-xs text-zinc-500 transition-colors hover:text-zinc-300"
          >
            Clear filters
          </button>
        )}

        <span className="ml-auto flex items-center gap-2">
          {scan.isSuccess && (
            <span className="text-xs text-zinc-500">
              Scan requested — refresh in a minute to see new activity
            </span>
          )}
          <button
            onClick={() => scan.mutate()}
            disabled={scan.isPending}
            className="rounded-lg bg-sky-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-sky-500 disabled:opacity-40"
          >
            {scan.isPending ? "Requesting…" : "Scan Now"}
          </button>
        </span>
      </div>
    </div>
  );
}
