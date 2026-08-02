import type { Conviction } from "../../api/types";

const LEVELS: Record<Conviction, number> = { high: 3, medium: 2, low: 1 };

export default function ConvictionMeter({
  conviction,
  label = false,
}: {
  conviction: Conviction;
  label?: boolean;
}) {
  const level = LEVELS[conviction] ?? 1;
  return (
    <span className="flex items-center gap-1.5">
      <span className="flex gap-0.5">
        {[1, 2, 3].map((i) => (
          <span
            key={i}
            className={`h-2 w-2 rounded-full ${i <= level ? "bg-sky-400" : "bg-zinc-700"}`}
          />
        ))}
      </span>
      {label && (
        <span className="text-xs capitalize text-zinc-400">{conviction} conviction</span>
      )}
    </span>
  );
}
