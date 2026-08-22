# frontend/src/pages/StockDetail.tsx

## Purpose
Full analysis view for a single ticker. URL: `/stock/:ticker`. Hero price chart at top, tabbed sub-views below. The deepest data view in the app.

## Layout
```
[← Back]  AAPL  Apple Inc.   [Bullish ●●●]   [Pull ▶]  [+ Watchlist]
──────────────────────────────────────────────────────────────────────
[TFC chart grid — 4 panels: 1D / 1W / 1M / 1Y, each with auto-drawn
 broadening formation levels, plus a Full TFC banner]
──────────────────────────────────────────────────────────────────────
[Deep dive — single full PriceChart w/ its own timeframe toggle, MAs,
 BF zones, volume pane, price + volume ROC panes]
[StrategyInsightsPanel — narrative read of Strat/gap/accumulation/
 market-flow signals for whichever timeframe the deep-dive chart is on]
──────────────────────────────────────────────────────────────────────
[Overview] [Technicals] [Fundamentals] [Insider] [Institutional] [Sentiment] [AI Summary]
──────────────────────────────────────────────────────────────────────
[Tab content]
```

## Implementation

```tsx
import { useParams } from 'react-router-dom'
import { useTickerAnalysis, useStockSignals, useStockFinancials, useTickerRecord } from '@/hooks/useAnalysis'
import { useEnqueueTicker } from '@/hooks/useQueue'
import { useStockPriceHistory } from '@/hooks/usePriceHistory'

export function StockDetail() {
  const { ticker } = useParams<{ ticker: string }>()
  const [activeTab, setActiveTab] = useState('ai-summary')
  const [deepDiveTimeframe, setDeepDiveTimeframe] = useState<Timeframe>('1D')
  
  const { data: analyses, isLoading } = useTickerAnalysis(ticker!)
  const { data: tickerRecord } = useTickerRecord(ticker!)
  const { data: signals } = useStockSignals(ticker!)
  const { data: financials } = useStockFinancials(ticker!)
  const { data: marketFlow } = useMarketFlow()
  const { data: priceData } = useStockPriceHistory(ticker!, ['1D', '1W', '1M', '1Y'])  // fetches each at its matching bar resolution, see PriceChart.md
  const enqueue = useEnqueueTicker()
  
  const latest = analyses?.[0]
  
  if (isLoading) return <StockDetailSkeleton />
  if (!latest) return <NoDataState ticker={ticker!} onPull={() => enqueue.mutate(ticker!)} />
  
  return (
    <div>
      {/* Hero header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <BackButton />
          <h1 className="text-3xl font-bold text-white">{ticker}</h1>
          <SignalBadge signal={latest.signal} />
          <ConvictionMeter conviction={latest.conviction} />
          {tickerRecord && <TickerStatusBadge status={tickerRecord.status} size="md" />}
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => enqueue.mutate(ticker!)}
            title={tickerRecord?.status === 'removed_from_market' ? 'Flagged as removed from market — pulling will re-check and reactivate it if it now resolves' : undefined}
            className={tickerRecord?.status === 'removed_from_market' ? 'opacity-70 ...' : '...'}
          >
            Pull ▶
          </button>
          <AddToWatchlistButton ticker={ticker!} />
        </div>
      </div>
      
      {/* TFC chart grid — 1D / 1W / 1M / 1Y with auto-drawn broadening formations */}
      <div className="mb-6">
        <TFCChartGrid ticker={ticker!} priceData={priceData ?? {}} signals={signals?.technical?.signal_markers} />
      </div>

      {/* Deep dive — one full chart (with volume + ROC panes) the user can flip through
          timeframes on, paired with the narrative strategy read for whatever it's set to */}
      <div className="mb-6 space-y-4">
        <PriceChart
          ticker={ticker!}
          priceData={priceData?.[deepDiveTimeframe] ?? []}
          defaultTimeframe={deepDiveTimeframe}
          onTimeframeChange={setDeepDiveTimeframe}
          signals={signals?.technical?.signal_markers}
        />
        <StrategyInsightsPanel
          ticker={ticker!}
          timeframe={deepDiveTimeframe}
          priceDataByTimeframe={priceData ?? {}}
          technical={signals?.technical}
          marketFlow={marketFlow}
        />
      </div>
      
      {/* Tab nav */}
      <TabNav activeTab={activeTab} onChange={setActiveTab} tabs={TABS} />
      
      {/* Tab content */}
      <div className="mt-6">
        {activeTab === 'ai-summary' && <AISummaryTab analysis={latest} signals={signals} />}
        {activeTab === 'technicals' && <TechnicalsTab signals={signals?.technical} />}
        {activeTab === 'fundamentals' && <FundamentalsTab financials={financials} signals={signals?.fundamental} />}
        {activeTab === 'insider' && <InsiderTab signals={signals?.insider} />}
        {activeTab === 'institutional' && <InstitutionalTab signals={signals?.institutional} />}
        {activeTab === 'sentiment' && <SentimentTab signals={signals?.sentiment} />}
      </div>
    </div>
  )
}
```

## `NoDataState`
If no analysis exists yet for this ticker, render a centered message with a "Pull Analysis" button that enqueues it.

## Tab List
```typescript
const TABS = [
  { id: 'ai-summary', label: 'AI Summary' },
  { id: 'technicals', label: 'Technicals' },
  { id: 'fundamentals', label: 'Fundamentals' },
  { id: 'insider', label: 'Insider' },
  { id: 'institutional', label: 'Institutional' },
  { id: 'sentiment', label: 'Sentiment' },
]
```

## Active Tab Persistence
Store active tab in URL hash (`#ai-summary`) so it survives refresh.

## Dependencies
- All stock tab components
- `TFCChartGrid` (renders 4 `PriceChart` panels — 1D/1W/1M/1Y with broadening formation overlays)
- `PriceChart` (deep-dive instance — full mode, so it also renders its `VolumeChart` and `RateOfChangeChart` panes by default)
- `StrategyInsightsPanel` (narrative Strat/gap/accumulation/market-flow read for the deep-dive timeframe)
- `useStockPriceHistory` (fetches OHLCV at the bar resolution matching each requested timeframe, per `PriceChart.md`)
- `useMarketFlow` (new hook — NYMO/NAMO breadth, feeds `StrategyInsightsPanel`)
- `useTickerRecord` (registry status, feeds `TickerStatusBadge`)
- `TickerStatusBadge`
- All analysis hooks

## Amendments

- **specs/024-delta-data-pulls**: the header gained a `PullCostPanel` diagnostics
  section (per-stage pull timing/byte breakdown), later removed — see below.
- **specs/028-dashboard-tweaks-batch US3**: `SentimentButtons` (thumbs up/down) render
  immediately after the ticker `<h1>`, before the signal/conviction badges — only when
  the ticker is tracked (hidden entirely, not disabled, for an untracked ticker; FR-006a).
- **specs/028-dashboard-tweaks-batch US7**: `PullCostPanel` and `usePullMetrics` removed
  entirely — the header no longer shows a "Pull cost" section, and the underlying
  `pull_metrics` collection/writer/endpoint are gone. Pulls themselves are unaffected
  (FR-026b); this was diagnostic-only instrumentation with no downstream consumer.
