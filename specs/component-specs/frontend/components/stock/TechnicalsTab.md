# frontend/src/components/stock/TechnicalsTab.tsx

## Purpose
Renders the Technicals tab in StockDetail. Shows The Strat results, accumulation score gauge, gap analysis, and market breadth (NYMO/NAMO) chart.

## Props
```typescript
interface TechnicalsTabProps {
  signals: AgentSignals['technical']
}
```

## Sections

### 1. The Strat Summary
- Bar type classification table (daily/weekly/monthly)
- Active patterns list (e.g., "2-1-2 Long", "Reversal Strat")
- TFC (Time Frame Continuity) state — color-coded row per timeframe

### 2. Accumulation Score Gauge
- Visual gauge (0–5) showing the accumulation score
- Up/Down volume ratio displayed below
- Pattern duration in days
- PEG amplifier flag (if true, highlight in yellow)

```tsx
function AccumulationGauge({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-3">
      {[1,2,3,4,5].map(i => (
        <div
          key={i}
          className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold
            ${i <= score ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-600'}`}
        >
          {i}
        </div>
      ))}
    </div>
  )
}
```

### 3. Gap Analysis
- Gap type label (Breakaway / Continuation / Exhaustion / Common)
- Gap score (0–5) with color coding
- Fill probability: Low / Medium / High
- Follow-through signal

### 4. NYMO/NAMO Mini Chart
- Small Recharts LineChart showing last 60 days of NYMO and NAMO
- Reference lines at +60 and -60 (overbought/oversold thresholds)
- Current values displayed as large numbers with zone label

## Layout
Stacked sections with `gap-6` between them. Each section in a `bg-slate-900 border border-slate-800 rounded-xl p-5` card.
