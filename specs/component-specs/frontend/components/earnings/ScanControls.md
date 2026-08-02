# frontend/src/components/earnings/ScanControls.tsx

## Purpose
Controls for configuring and triggering the earnings scan. Compact row with a days-ahead selector, market cap floor input, and the Scan button.

## Props
```typescript
interface ScanControlsProps {
  onScan: (config: ScanConfig) => void
  isScanning: boolean
}

interface ScanConfig {
  days_ahead: number
  min_market_cap_bn: number   // in billions
}
```

## Controls
- **Days ahead** — pill group: [3d] [5d] [7d] [14d] — default 7
- **Min market cap** — dropdown: [$500M] [$1B] [$5B] [$10B] — default $500M
- **Scan button** — "Scan Earnings Calendar" with calendar icon; shows spinner + "Scanning..." while running; disabled during scan

```tsx
export function ScanControls({ onScan, isScanning }: ScanControlsProps) {
  const [daysAhead, setDaysAhead] = useState(7)
  const [minMarketCap, setMinMarketCap] = useState(0.5)   // billions

  return (
    <div className="flex items-center gap-3 p-4 bg-slate-900 border border-slate-800 rounded-xl">
      <div className="flex gap-1">
        {[3, 5, 7, 14].map(d => (
          <button key={d}
            onClick={() => setDaysAhead(d)}
            className={`px-3 py-1 rounded text-sm ${daysAhead === d ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
          >
            {d}d
          </button>
        ))}
      </div>
      
      <select
        value={minMarketCap}
        onChange={e => setMinMarketCap(Number(e.target.value))}
        className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-slate-300"
      >
        <option value={0.5}>≥ $500M</option>
        <option value={1}>≥ $1B</option>
        <option value={5}>≥ $5B</option>
        <option value={10}>≥ $10B</option>
      </select>
      
      <button
        onClick={() => onScan({ days_ahead: daysAhead, min_market_cap_bn: minMarketCap })}
        disabled={isScanning}
        className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
      >
        {isScanning ? <><Spinner className="w-4 h-4" /> Scanning...</> : <><CalendarIcon className="w-4 h-4" /> Scan Earnings</>}
      </button>
    </div>
  )
}
```
