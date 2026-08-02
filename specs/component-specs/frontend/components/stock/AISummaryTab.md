# frontend/src/components/stock/AISummaryTab.tsx

## Purpose
Displays the PortfolioStrategist synthesis — the final AI verdict with collapsible per-agent breakdowns. The "big picture" tab.

## Sections

### 1. Verdict Banner
Full-width banner at the top:
```
┌──────────────────────────────────────────────────────┐
│  BULLISH  ●●●  High Conviction   Analyzed 2h ago     │
│  "AAPL presents a high-conviction long setup..."     │
└──────────────────────────────────────────────────────┘
```
Background color: `bg-green-500/10` for bullish, `bg-red-500/10` for bearish, `bg-slate-800` for neutral.

### 2. Key Trends
- Bulleted list from `analysis.key_trends`
- Each bullet: small checkmark icon + trend text

### 3. Flags / Alerts
- Only shown if `analysis.flags.length > 0`
- Amber warning-style cards: `bg-amber-500/10 border border-amber-500/30`
- Each flag with a ⚠ icon

### 4. Position Management
Card showing:
- Stair-step stop levels (ordered list of price levels)
- Trailing stop recommendation (text)
- Position sizing guidance (text)

### 5. Per-Agent Breakdown (collapsible)
Accordion with one section per sub-report:
- Technical | Fundamental | Macro | Insider | Institutional | Sentiment | Recommendation
- Collapsed by default — expand to see raw sub-report data
- Each section shows the sub-report's overall signal + key bullet points
- For power users who want to dig into the details

```tsx
function AgentBreakdown({ name, report }: { name: string, report: any }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-slate-800 rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/50"
        onClick={() => setOpen(!open)}
      >
        <span className="font-medium text-slate-200">{name}</span>
        <ChevronIcon className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="p-4 border-t border-slate-800 text-slate-400 text-sm">
          <pre className="whitespace-pre-wrap font-sans">{JSON.stringify(report, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
```

### 6. Analysis History Timeline
Compact list of previous analyses for this ticker — date, signal badge, one-line summary.
Shows how the AI's verdict has evolved over time.

## Dependencies
- `useTickerAnalysis` (for history)
- `useStockSignals` (for sub-reports)
- `SignalBadge`, `ConvictionMeter`
