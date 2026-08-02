// Spec: specs/component-specs/frontend/components/earnings/ScanControls.md
// The cap floor is applied client-side: the backend screens at $500M and the
// dropdown narrows the displayed results further.
import { useState } from "react";

export interface ScanConfig {
  days_ahead: number;
  min_market_cap_bn: number;
}

interface ScanControlsProps {
  onScan: (config: ScanConfig) => void;
  onMinCapChange: (minCapBn: number) => void;
  onDaysChange: (days: number) => void;
  isScanning: boolean;
}

const DAY_CHOICES = [3, 5, 7, 14];

export default function ScanControls({ onScan, onMinCapChange, onDaysChange, isScanning }: ScanControlsProps) {
  const [daysAhead, setDaysAhead] = useState(7);
  const [minCapBn, setMinCapBn] = useState(0.5);

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900 p-4">
      <div className="flex gap-1" role="group" aria-label="Days ahead">
        {DAY_CHOICES.map((d) => (
          <button
            key={d}
            onClick={() => {
              setDaysAhead(d);
              onDaysChange(d);
            }}
            className={`rounded px-3 py-1 text-sm ${
              daysAhead === d
                ? "bg-indigo-600 text-white"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            {d}d
          </button>
        ))}
      </div>

      <select
        value={minCapBn}
        aria-label="Minimum market cap"
        onChange={(e) => {
          const v = Number(e.target.value);
          setMinCapBn(v);
          onMinCapChange(v);
        }}
        className="rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-300"
      >
        <option value={0.5}>≥ $500M</option>
        <option value={1}>≥ $1B</option>
        <option value={5}>≥ $5B</option>
        <option value={10}>≥ $10B</option>
      </select>

      <button
        onClick={() => onScan({ days_ahead: daysAhead, min_market_cap_bn: minCapBn })}
        disabled={isScanning}
        className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
      >
        {isScanning ? (
          <>
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            Scanning…
          </>
        ) : (
          <>Scan Earnings</>
        )}
      </button>
    </div>
  );
}
