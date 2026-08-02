# frontend/src/components/stock/StrategyInsightsPanel.tsx

## Purpose
Narrative synthesis panel that sits beneath the "Deep dive" chart on `StockDetail`. Where `TechnicalsTab` shows the Strat/accumulation/gap data as raw tables and gauges, this panel reads across *all* the strategy specs at once and writes out what they mean in plain sentences for whatever timeframe the deep-dive chart is currently showing — the "go deeper" companion to the chart itself, not a duplicate of the Technicals tab.

## Props
```typescript
interface StrategyInsightsPanelProps {
  ticker: string
  timeframe: Timeframe                    // whatever the deep-dive PriceChart is currently set to
  priceDataByTimeframe: Record<Timeframe, OHLCVBar[]>   // needed for the Full TFC read, which spans 1D/1W/1M/1Y regardless of the single selected timeframe
  technical: AgentSignals['technical']    // existing Strat/accumulation/gap sub-report, same data TechnicalsTab already renders
  marketFlow?: MarketFlowSignals          // NYMO/NAMO breadth context, optional
}
```

## Layout
Grouped list, one row per insight, left border + icon colored by tone (`bullish` green / `bearish` red / `warning` amber / `neutral` slate). Where an insight has a concrete trigger bar, its row also carries a 5-candle `MiniCandlestickStrip` (see `shared/MiniCandlestickStrip.md`) showing the actual price action around it, so the sentence isn't just an assertion — you can see the down gap, the outside bar, the spike day, or the cross candle itself. Grouped under headers matching the source specs:

```
Time frame continuity (the-strat-spec.md)
 ● Full TFC Bullish — 1D, 1W, 1M, and 1Y all confirming above their opens.
   [no strip — this reads across all 4 panels at once, not one bar]

Broadening formation
 ● Active BF on the Daily panel: $172.40 (low) to $181.20 (high), opened on an          [🕯️🕯️🕯️🕯️🕯️]
   outside bar. Price is testing the high side.                                     5 candles centered on
                                                                                       the outside bar that
                                                                                       opened the zone

Volume & accumulation (accumulation_volume_rules.md)
 ● Accumulation score 4/5 — 65% of up days in the last 20 closed with volume         [🕯️🕯️🕯️🕯️🕯️]
   ≥ 1.5x the 20-day average (rule needs 60%+).                                   5 candles around the
                                                                                     most recent spike day

Gap analysis (gap_analysis_rules.md)
 ● Last gap (Jul 22): down gap that closed back above the 30-day SMA —              [🕯️🕯️🕯️🕯️🕯️]
   the rulebook's strongest LONG signal (Section 6).                             5 candles around the gap day

Moving averages
 ● Price is above EMA 50 and EMA 200, with EMA 50 above EMA 200 (golden              [🕯️🕯️🕯️🕯️🕯️]
   cross intact) — long-term trend is up.                                       5 candles around the day
                                                                                    EMA 50 crossed EMA 200

Market flow (market_flow_rules.md)
 ● NYMO at -18 — normal range, no oversold add signal in force.
   [no strip — NYMO is a breadth index, not this ticker's own price action]
```

Each group only renders if it has at least one insight — sections silently drop out for tickers/timeframes where a rule doesn't apply (e.g. no gap in the lookback window). Not every insight gets a strip: TFC and market-flow insights are aggregate reads (across 4 panels, or across the whole market) rather than a single bar's event, so they render as text only.

## Implementation
```tsx
import { generateInsights, type Insight } from '@/lib/strat/insights'
import { MiniCandlestickStrip } from '@/components/shared/MiniCandlestickStrip'

const TONE_STYLES = {
  bullish: { border: 'border-green-500/40', dot: 'bg-green-400' },
  bearish: { border: 'border-red-500/40', dot: 'bg-red-400' },
  warning: { border: 'border-amber-500/40', dot: 'bg-amber-400' },
  neutral: { border: 'border-slate-700', dot: 'bg-slate-500' },
} as const

export function StrategyInsightsPanel({ ticker, timeframe, priceDataByTimeframe, technical, marketFlow }: StrategyInsightsPanelProps) {
  const insights = generateInsights({ ticker, timeframe, priceDataByTimeframe, technical, marketFlow })
  const grouped = groupBy(insights, i => i.category)

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-5">
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category}>
          <div className="text-xs font-medium text-slate-500 mb-2">{category}</div>
          <div className="space-y-2">
            {items.map(insight => (
              <div key={insight.id} className={`flex items-center gap-3 pl-3 border-l-2 ${TONE_STYLES[insight.tone].border}`}>
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 self-start mt-1.5 ${TONE_STYLES[insight.tone].dot}`} />
                <p className="text-sm text-slate-300 flex-1">{insight.text}</p>
                {insight.signalWindow && (
                  <MiniCandlestickStrip
                    bars={insight.signalWindow.bars}
                    highlightDate={insight.signalWindow.triggerDate}
                    tone={insight.tone}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
```

## Insight Generation
`lib/strat/insights.ts` — pulls from the same computed values the charts already use (`getFullTfcState`, `detectBroadeningFormations`, `MOVING_AVERAGES`) plus the existing `technical` sub-report fields, and turns them into sentences. Written as small, independent generator functions so each strategy spec's logic stays isolated and easy to extend:

```typescript
// lib/strat/insights.ts
import { getSignalWindow } from '@/lib/strat/signalWindow'

export type Insight = {
  id: string
  category: string
  tone: 'bullish' | 'bearish' | 'warning' | 'neutral'
  text: string
  signalWindow?: { bars: OHLCVBar[]; triggerDate: string }   // 5-candle context around the trigger bar, when there is one — see MiniCandlestickStrip.md
}

function tfcInsights(priceDataByTimeframe: Record<Timeframe, OHLCVBar[]>): Insight[] {
  const panels: Timeframe[] = ['1D', '1W', '1M', '1Y']
  const colors = panels.map(tf => ({ tf, color: getTfcColor(priceDataByTimeframe[tf]) }))
  const state = getFullTfcState(colors.map(c => c.color))
  if (state !== 'conflict') {
    return [{
      id: 'tfc-full', category: 'Time frame continuity (the-strat-spec.md)',
      tone: state === 'bullish' ? 'bullish' : 'bearish',
      text: `Full TFC ${state === 'bullish' ? 'Bullish' : 'Bearish'} — 1D, 1W, 1M, and 1Y all confirming ${state === 'bullish' ? 'above' : 'below'} their opens.`,
    }]
  }
  const dissenting = colors.filter((c, _, arr) => c.color !== arr[0].color).map(c => c.tf)
  return [{
    id: 'tfc-conflict', category: 'Time frame continuity (the-strat-spec.md)', tone: 'warning',
    text: `In Conflict — ${dissenting.join(', ')} not confirming the others. Expect chop per the Strat's TFC rules.`,
  }]
}

function broadeningFormationInsights(bars: OHLCVBar[], timeframe: Timeframe): Insight[] {
  const zones = detectBroadeningFormations(bars)
  const active = zones.find(z => z.active)
  if (!active) return []
  const last = bars[bars.length - 1]
  const positionPct = ((last.close - active.low) / (active.high - active.low)) * 100
  const zonePosition = positionPct > 66 ? 'testing the high side' : positionPct < 33 ? 'testing the low side' : 'mid-range'
  return [{
    id: 'bf-active', category: 'Broadening formation', tone: 'neutral',
    text: `Active BF on the ${timeframe} panel: $${active.low.toFixed(2)} (low) to $${active.high.toFixed(2)} (high). Price is ${zonePosition} of the range.`,
    signalWindow: getSignalWindow(bars, active.start) ?? undefined,   // the outside bar that opened this zone
  }]
}

// Same spike definition VolumeChart.md uses: up day, volume ≥ 1.5x the trailing 20-day average
function findLatestAccumulationSpike(bars: OHLCVBar[]): OHLCVBar | null {
  for (let i = bars.length - 1; i >= 20; i--) {
    const avg20 = bars.slice(i - 20, i).reduce((a, b) => a + b.volume, 0) / 20
    if (bars[i].close >= bars[i].open && bars[i].volume >= 1.5 * avg20) return bars[i]
  }
  return null
}

function accumulationInsights(technical: AgentSignals['technical'], bars: OHLCVBar[]): Insight[] {
  const acc = technical?.accumulation
  if (!acc) return []
  const spike = findLatestAccumulationSpike(bars)
  const out: Insight[] = [{
    id: 'accumulation-score', category: 'Volume & accumulation (accumulation_volume_rules.md)',
    tone: acc.score >= 3 ? 'bullish' : 'neutral',
    text: `Accumulation score ${acc.score}/5 — ${acc.up_day_pct}% of up days in the last 20 closed with volume ≥ 1.5x the 20-day average (rule needs 60%+).`,
    signalWindow: spike ? getSignalWindow(bars, spike.date) ?? undefined : undefined,   // most recent qualifying spike day
  }]
  if (acc.peg_amplifier) {
    out.push({ id: 'peg-amp', category: 'Volume & accumulation (accumulation_volume_rules.md)', tone: 'bullish', text: 'PEG amplifier detected in the last 60 days — sustained multi-week accumulation after a post-earnings gap.' })
  }
  return out
}

function gapInsights(technical: AgentSignals['technical'], bars: OHLCVBar[]): Insight[] {
  const gap = technical?.latest_gap
  if (!gap) return []
  const RULE_TEXT: Record<string, { tone: Insight['tone']; text: string }> = {
    down_gap_above_30sma: { tone: 'bullish', text: `Down gap that closed back above the 30-day SMA — the rulebook's strongest LONG signal (gap_analysis_rules.md, Section 6).` },
    down_gap_below_all_sma: { tone: 'bearish', text: `Down gap below all 3 SMAs — momentum looks real; rulebook favors waiting before buying.` },
    up_gap_below_ma: { tone: 'bearish', text: `Up gap below its moving average — best SHORT setup per the rulebook.` },
    up_gap_extreme: { tone: 'bearish', text: `Up gap > 175% of SMA — extreme price, rulebook flags a strong SHORT.` },
  }
  const rule = RULE_TEXT[gap.classification]
  if (!rule) return []
  return [{
    id: 'gap-latest', category: 'Gap analysis (gap_analysis_rules.md)', tone: rule.tone, text: `Last gap (${gap.date}): ${rule.text}`,
    signalWindow: getSignalWindow(bars, gap.date) ?? undefined,   // the actual gap day, centered
  }]
}

// Finds the most recent bar where EMA 50 crossed EMA 200 (either direction) — the actual cross candle, not just today's relative position
function findLatestMaCross(bars: (OHLCVBar & Record<string, number | null>)[]): (OHLCVBar & Record<string, number | null>) | null {
  for (let i = bars.length - 1; i > 0; i--) {
    const prev = bars[i - 1], curr = bars[i]
    if (prev.ema50 == null || prev.ema200 == null || curr.ema50 == null || curr.ema200 == null) continue
    const prevAbove = prev.ema50 >= prev.ema200
    const currAbove = curr.ema50 >= curr.ema200
    if (prevAbove !== currAbove) return curr
  }
  return null
}

function movingAverageInsights(bars: (OHLCVBar & Record<string, number | null>)[]): Insight[] {
  const last = bars[bars.length - 1]
  if (!last?.ema50 || !last?.ema200) return []
  const out: Insight[] = []
  const golden = last.ema50 >= last.ema200
  const crossBar = findLatestMaCross(bars)
  out.push({
    id: 'ma-cross', category: 'Moving averages', tone: golden ? 'bullish' : 'bearish',
    text: `Price is ${last.close >= last.ema200 ? 'above' : 'below'} EMA 200, with EMA 50 ${golden ? 'above' : 'below'} EMA 200 (${golden ? 'golden' : 'death'} cross) — long-term trend is ${golden ? 'up' : 'down'}.`,
    signalWindow: crossBar ? getSignalWindow(bars, crossBar.date) ?? undefined : undefined,   // the actual crossover candle, if one occurred within the fetched history
  })
  if (last.sma30) {
    const pctFromSma30 = ((last.close - last.sma30) / last.sma30) * 100
    out.push({
      id: 'ma-sma30', category: 'Moving averages', tone: Math.abs(pctFromSma30) > 75 ? 'warning' : 'neutral',
      text: `Price is ${pctFromSma30 >= 0 ? '+' : ''}${pctFromSma30.toFixed(0)}% from SMA 30${Math.abs(pctFromSma30) > 75 ? ' — approaching the gap rulebook\\'s "175% of SMA" extreme-price zone' : ''}.`,
      signalWindow: getSignalWindow(bars, last.date) ?? undefined,   // last 5 bars — "here's today relative to the line"
    })
  }
  return out
}

function marketFlowInsights(marketFlow?: MarketFlowSignals): Insight[] {
  if (!marketFlow) return []
  const { nymo } = marketFlow
  if (nymo <= -60) return [{ id: 'nymo-oversold', category: 'Market flow (market_flow_rules.md)', tone: 'bullish', text: `NYMO at ${nymo} — oversold zone, strong bounce candidate per the rulebook.` }]
  if (nymo >= 40) return [{ id: 'nymo-overbought', category: 'Market flow (market_flow_rules.md)', tone: 'warning', text: `NYMO at ${nymo} — already overbought, rulebook says don't chase adds here.` }]
  return [{ id: 'nymo-normal', category: 'Market flow (market_flow_rules.md)', tone: 'neutral', text: `NYMO at ${nymo} — normal range, no breadth-driven add/trim signal in force.` }]
}

export function generateInsights(input: {
  ticker: string; timeframe: Timeframe; priceDataByTimeframe: Record<Timeframe, OHLCVBar[]>;
  technical: AgentSignals['technical']; marketFlow?: MarketFlowSignals
}): Insight[] {
  const bars = input.priceDataByTimeframe[input.timeframe]
  const withMAs = computeMovingAverages(bars)
  return [
    ...tfcInsights(input.priceDataByTimeframe),
    ...broadeningFormationInsights(bars, input.timeframe),
    ...accumulationInsights(input.technical, bars),
    ...gapInsights(input.technical, bars),
    ...movingAverageInsights(withMAs),
    ...marketFlowInsights(input.marketFlow),
  ]
}
```

## Relationship to TechnicalsTab
`TechnicalsTab` (see `TechnicalsTab.md`) stays as the raw-data view — bar classification table, accumulation gauge, gap score, NYMO chart. This panel is the narrative layer on top, reusing the same underlying `technical` sub-report and the same `lib/strat/*` helpers the charts use, so the two never disagree — they're reading the same computed values, just presented differently (structured data vs. plain-English sentences).

## Dependencies
- `lib/strat/insights.ts`
- `lib/strat/tfc.ts`, `lib/strat/broadeningFormations.ts`, `lib/strat/movingAverages.ts` (reused, not reimplemented)
- `lib/strat/signalWindow.ts` (`getSignalWindow`)
- `MiniCandlestickStrip` (`shared/MiniCandlestickStrip.md`)
- `AgentSignals['technical']` (existing sub-report shape)
