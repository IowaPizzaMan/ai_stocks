import type { Signal } from "../../api/types";

const STYLES: Record<Signal, string> = {
  bullish: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  bearish: "bg-red-500/15 text-red-400 border-red-500/30",
  neutral: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
};

export default function SignalBadge({ signal }: { signal: Signal }) {
  return (
    <span
      className={`rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${STYLES[signal] ?? STYLES.neutral}`}
    >
      {signal}
    </span>
  );
}
