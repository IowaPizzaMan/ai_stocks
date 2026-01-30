import { useState, useEffect, useMemo } from 'react'
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  Cell,
} from 'recharts'
import { format, parseISO, subDays, subMonths, subYears } from 'date-fns'
import { dataApi, PriceHistory } from '../services/api'
import {
  processChartData,
  findSupportResistance,
  calculateTrendLines,
  ChartDataPoint,
} from '../utils/technicalIndicators'

interface Props {
  ticker: string
}

const periods = [
  { label: '1W', value: '1w', days: 7 },
  { label: '1M', value: '1m', days: 30 },
  { label: '3M', value: '3m', days: 90 },
  { label: '1Y', value: '1y', days: 365 },
  { label: '5Y', value: '5y', days: 1825 },
  { label: 'Max', value: 'max', days: 9999 },
]

interface OverlayState {
  sma20: boolean
  sma50: boolean
  sma200: boolean
  bollingerBands: boolean
  volume: boolean
}

interface PeriodPerformance {
  [key: string]: number | null
}

export default function TechnicalChart({ ticker }: Props) {
  const [allPrices, setAllPrices] = useState<PriceHistory[]>([])
  const [period, setPeriod] = useState('1y')
  const [loading, setLoading] = useState(true)
  const [chartType, setChartType] = useState<'line' | 'candle'>('line')
  const [overlays, setOverlays] = useState<OverlayState>({
    sma20: true,
    sma50: true,
    sma200: false,
    bollingerBands: false,
    volume: true,
  })
  const [showRSI, setShowRSI] = useState(true)
  const [showMACD, setShowMACD] = useState(true)
  const [periodPerformance, setPeriodPerformance] = useState<PeriodPerformance>({})

  // Always fetch max data to have enough for indicators on any timeframe
  useEffect(() => {
    const fetchPrices = async () => {
      setLoading(true)
      try {
        // Always fetch max data so we have enough history for MAs and Bollinger
        const response = await dataApi.getPrices(ticker, 'max')
        setAllPrices(response.data)

        // Calculate performance for each period
        calculatePeriodPerformance(response.data)
      } catch (error) {
        console.error('Failed to fetch prices:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchPrices()
  }, [ticker])

  // Calculate performance for each period button
  const calculatePeriodPerformance = (prices: PriceHistory[]) => {
    if (!prices || prices.length === 0) return

    const performance: PeriodPerformance = {}
    const latestPrice = prices[prices.length - 1]?.close
    if (latestPrice === null) return

    const latestDate = parseISO(prices[prices.length - 1].date)

    periods.forEach((p) => {
      let targetDate: Date
      switch (p.value) {
        case '1w':
          targetDate = subDays(latestDate, 7)
          break
        case '1m':
          targetDate = subMonths(latestDate, 1)
          break
        case '3m':
          targetDate = subMonths(latestDate, 3)
          break
        case '1y':
          targetDate = subYears(latestDate, 1)
          break
        case '5y':
          targetDate = subYears(latestDate, 5)
          break
        case 'max':
          targetDate = parseISO(prices[0].date)
          break
        default:
          targetDate = latestDate
      }

      // Find the closest price to target date
      const targetTime = targetDate.getTime()
      let closestPrice: PriceHistory | null = null
      let closestDiff = Infinity

      for (const price of prices) {
        const priceDate = parseISO(price.date)
        const diff = Math.abs(priceDate.getTime() - targetTime)
        if (diff < closestDiff && price.close !== null) {
          closestDiff = diff
          closestPrice = price
        }
      }

      if (closestPrice && closestPrice.close !== null) {
        const startPrice = Number(closestPrice.close)
        const endPrice = Number(latestPrice)
        performance[p.value] = ((endPrice - startPrice) / startPrice) * 100
      } else {
        performance[p.value] = null
      }
    })

    setPeriodPerformance(performance)
  }

  // Process all data with indicators, then slice for display
  const { chartData, displayData } = useMemo(() => {
    if (!allPrices || allPrices.length === 0) {
      return { chartData: [], displayData: [] }
    }

    try {
      // Process ALL data to calculate indicators correctly
      const fullChartData = processChartData(allPrices)

      // Now slice to the display period
      const periodConfig = periods.find((p) => p.value === period)
      const daysToShow = periodConfig?.days || 365

      // For 'max', show everything; otherwise slice
      let slicedData: ChartDataPoint[]
      if (period === 'max' || daysToShow >= fullChartData.length) {
        slicedData = fullChartData
      } else {
        slicedData = fullChartData.slice(-daysToShow)
      }

      return { chartData: fullChartData, displayData: slicedData }
    } catch (e) {
      console.error('Error processing chart data:', e)
      return { chartData: [], displayData: [] }
    }
  }, [allPrices, period])

  const { support, resistance } = useMemo(() => {
    try {
      return findSupportResistance(displayData)
    } catch (e) {
      console.error('Error finding support/resistance:', e)
      return { support: [], resistance: [] }
    }
  }, [displayData])

  const trendLines = useMemo(() => {
    try {
      return calculateTrendLines(displayData)
    } catch (e) {
      console.error('Error calculating trend lines:', e)
      return []
    }
  }, [displayData])

  const formatDate = (dateStr: string) => {
    try {
      return format(parseISO(dateStr), 'MMM d')
    } catch {
      return dateStr
    }
  }

  const formatPrice = (value: number) => `$${value.toFixed(2)}`

  // Calculate price domain with padding
  const priceDomain = useMemo(() => {
    const validPrices = displayData
      .flatMap((d) => [d.close, d.high, d.low, d.upperBand, d.lowerBand])
      .filter((v): v is number => v !== null)
    if (validPrices.length === 0) return ['auto', 'auto']
    const min = Math.min(...validPrices)
    const max = Math.max(...validPrices)
    const padding = (max - min) * 0.05
    return [min - padding, max + padding]
  }, [displayData])

  const toggleOverlay = (key: keyof OverlayState) => {
    setOverlays((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  // Custom candlestick rendering
  const renderCandlestick = (props: {
    x: number
    y: number
    width: number
    height: number
    payload: ChartDataPoint
  }) => {
    const { x, width, payload } = props
    if (!payload.open || !payload.close || !payload.high || !payload.low) {
      return null
    }

    const open = Number(payload.open)
    const close = Number(payload.close)
    const high = Number(payload.high)
    const low = Number(payload.low)

    const isUp = close >= open
    const color = isUp ? '#22c55e' : '#ef4444'

    // Calculate y positions using domain
    const [minDomain, maxDomain] = priceDomain as [number, number]
    const chartHeight = 288 // h-72 = 18rem = 288px
    const priceToY = (price: number) => {
      return chartHeight - ((price - minDomain) / (maxDomain - minDomain)) * chartHeight
    }

    const bodyTop = priceToY(Math.max(open, close))
    const bodyBottom = priceToY(Math.min(open, close))
    const bodyHeight = Math.max(bodyBottom - bodyTop, 1)

    const wickX = x + width / 2
    const highY = priceToY(high)
    const lowY = priceToY(low)

    return (
      <g key={`candle-${x}`}>
        {/* Wick */}
        <line
          x1={wickX}
          y1={highY}
          x2={wickX}
          y2={lowY}
          stroke={color}
          strokeWidth={1}
        />
        {/* Body */}
        <rect
          x={x + 1}
          y={bodyTop}
          width={Math.max(width - 2, 2)}
          height={bodyHeight}
          fill={color}
          stroke={color}
        />
      </g>
    )
  }

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-96 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  const latestPrice = displayData.length > 0 ? displayData[displayData.length - 1] : null
  const firstPrice = displayData.length > 0 ? displayData[0] : null
  const latestClose = latestPrice?.close != null ? Number(latestPrice.close) : null
  const firstClose = firstPrice?.close != null ? Number(firstPrice.close) : null
  const priceChange = latestClose && firstClose
    ? ((latestClose - firstClose) / firstClose) * 100
    : null

  // Get button color based on performance
  const getPeriodButtonClass = (periodValue: string, isSelected: boolean) => {
    const perf = periodPerformance[periodValue]

    if (isSelected) {
      if (perf === null || perf === undefined) return 'bg-blue-600 text-white'
      return perf >= 0 ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
    }

    if (perf === null || perf === undefined) return 'bg-gray-100 text-gray-600 hover:bg-gray-200'
    return perf >= 0
      ? 'bg-green-100 text-green-700 hover:bg-green-200'
      : 'bg-red-100 text-red-700 hover:bg-red-200'
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      {/* Header with price info */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-medium text-gray-900">Price Chart</h3>
          {latestClose && (
            <div className="flex items-center gap-3 mt-1">
              <span className="text-2xl font-bold">${latestClose.toFixed(2)}</span>
              {priceChange !== null && (
                <span className={`text-sm font-medium ${priceChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex gap-1">
          {periods.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`px-3 py-1 text-sm rounded transition-colors ${getPeriodButtonClass(p.value, period === p.value)}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart type toggle and Overlay toggles */}
      <div className="flex flex-wrap gap-2 mb-4">
        <span className="text-xs text-gray-500 self-center mr-2">Chart:</span>
        <button
          onClick={() => setChartType('line')}
          className={`px-2 py-1 text-xs rounded-full border transition-all ${
            chartType === 'line'
              ? 'bg-blue-100 text-blue-700 border-current'
              : 'bg-white text-gray-400 border-gray-200'
          }`}
        >
          Line
        </button>
        <button
          onClick={() => setChartType('candle')}
          className={`px-2 py-1 text-xs rounded-full border transition-all ${
            chartType === 'candle'
              ? 'bg-blue-100 text-blue-700 border-current'
              : 'bg-white text-gray-400 border-gray-200'
          }`}
        >
          Candlestick
        </button>

        <span className="text-xs text-gray-500 self-center mx-2">Overlays:</span>
        {[
          { key: 'sma20' as const, label: 'SMA 20', color: 'bg-orange-100 text-orange-700' },
          { key: 'sma50' as const, label: 'SMA 50', color: 'bg-purple-100 text-purple-700' },
          { key: 'sma200' as const, label: 'SMA 200', color: 'bg-red-100 text-red-700' },
          { key: 'bollingerBands' as const, label: 'Bollinger', color: 'bg-blue-100 text-blue-700' },
          { key: 'volume' as const, label: 'Volume', color: 'bg-gray-100 text-gray-700' },
        ].map(({ key, label, color }) => (
          <button
            key={key}
            onClick={() => toggleOverlay(key)}
            className={`px-2 py-1 text-xs rounded-full border transition-all ${
              overlays[key]
                ? `${color} border-current`
                : 'bg-white text-gray-400 border-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
        <span className="text-xs text-gray-500 self-center mx-2">Indicators:</span>
        <button
          onClick={() => setShowRSI(!showRSI)}
          className={`px-2 py-1 text-xs rounded-full border transition-all ${
            showRSI
              ? 'bg-emerald-100 text-emerald-700 border-current'
              : 'bg-white text-gray-400 border-gray-200'
          }`}
        >
          RSI
        </button>
        <button
          onClick={() => setShowMACD(!showMACD)}
          className={`px-2 py-1 text-xs rounded-full border transition-all ${
            showMACD
              ? 'bg-cyan-100 text-cyan-700 border-current'
              : 'bg-white text-gray-400 border-gray-200'
          }`}
        >
          MACD
        </button>
      </div>

      {displayData.length > 0 ? (
        <>
          {/* Main Price Chart */}
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={displayData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDate}
                  tick={{ fontSize: 11 }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  yAxisId="price"
                  tickFormatter={formatPrice}
                  tick={{ fontSize: 11 }}
                  domain={priceDomain}
                  orientation="right"
                />
                {overlays.volume && (
                  <YAxis
                    yAxisId="volume"
                    orientation="left"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v) => `${(v / 1000000).toFixed(0)}M`}
                    domain={[0, 'auto']}
                  />
                )}
                <Tooltip
                  formatter={(value: number, name: string) => {
                    if (name === 'volume') return [`${(value / 1000000).toFixed(2)}M`, 'Volume']
                    return [formatPrice(value), name.toUpperCase()]
                  }}
                  labelFormatter={(label) => format(parseISO(label as string), 'MMM d, yyyy')}
                  contentStyle={{ fontSize: 12 }}
                />

                {/* Volume bars */}
                {overlays.volume && (
                  <Bar yAxisId="volume" dataKey="volume" fill="#e5e7eb" opacity={0.5} />
                )}

                {/* Bollinger Bands */}
                {overlays.bollingerBands && (
                  <>
                    <Area
                      yAxisId="price"
                      dataKey="upperBand"
                      stroke="none"
                      fill="#3b82f6"
                      fillOpacity={0.1}
                      connectNulls={false}
                    />
                    <Line
                      yAxisId="price"
                      type="monotone"
                      dataKey="upperBand"
                      stroke="#3b82f6"
                      strokeWidth={1}
                      dot={false}
                      strokeDasharray="3 3"
                      connectNulls={false}
                    />
                    <Line
                      yAxisId="price"
                      type="monotone"
                      dataKey="lowerBand"
                      stroke="#3b82f6"
                      strokeWidth={1}
                      dot={false}
                      strokeDasharray="3 3"
                      connectNulls={false}
                    />
                  </>
                )}

                {/* Support lines */}
                {support.map((level, i) => (
                  <ReferenceLine
                    key={`support-${i}`}
                    yAxisId="price"
                    y={Number(level)}
                    stroke="#22c55e"
                    strokeDasharray="5 5"
                    strokeWidth={1}
                    label={{
                      value: `S: $${Number(level).toFixed(2)}`,
                      position: 'left',
                      fontSize: 10,
                      fill: '#22c55e',
                    }}
                  />
                ))}

                {/* Resistance lines */}
                {resistance.map((level, i) => (
                  <ReferenceLine
                    key={`resistance-${i}`}
                    yAxisId="price"
                    y={Number(level)}
                    stroke="#ef4444"
                    strokeDasharray="5 5"
                    strokeWidth={1}
                    label={{
                      value: `R: $${Number(level).toFixed(2)}`,
                      position: 'left',
                      fontSize: 10,
                      fill: '#ef4444',
                    }}
                  />
                ))}

                {/* Moving Averages */}
                {overlays.sma200 && (
                  <Line
                    yAxisId="price"
                    type="monotone"
                    dataKey="sma200"
                    stroke="#dc2626"
                    strokeWidth={1.5}
                    dot={false}
                    name="SMA 200"
                    connectNulls={false}
                  />
                )}
                {overlays.sma50 && (
                  <Line
                    yAxisId="price"
                    type="monotone"
                    dataKey="sma50"
                    stroke="#9333ea"
                    strokeWidth={1.5}
                    dot={false}
                    name="SMA 50"
                    connectNulls={false}
                  />
                )}
                {overlays.sma20 && (
                  <Line
                    yAxisId="price"
                    type="monotone"
                    dataKey="sma20"
                    stroke="#f97316"
                    strokeWidth={1.5}
                    dot={false}
                    name="SMA 20"
                    connectNulls={false}
                  />
                )}

                {/* Price - Line or Candlestick */}
                {chartType === 'line' ? (
                  <Line
                    yAxisId="price"
                    type="monotone"
                    dataKey="close"
                    stroke="#2563eb"
                    strokeWidth={2}
                    dot={false}
                    name="Price"
                  />
                ) : (
                  <Bar
                    yAxisId="price"
                    dataKey="high"
                    shape={(props: unknown) => {
                      const typedProps = props as {
                        x: number
                        y: number
                        width: number
                        height: number
                        payload: ChartDataPoint
                      }
                      return renderCandlestick(typedProps)
                    }}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* RSI Chart */}
          {showRSI && (
            <div className="mt-4">
              <div className="flex items-center gap-2 mb-2">
                <h4 className="text-sm font-medium text-gray-700">RSI (14)</h4>
                <span className="text-xs text-gray-500">
                  {latestPrice?.rsi != null
                    ? `Current: ${Number(latestPrice.rsi).toFixed(1)}`
                    : ''}
                </span>
              </div>
              <div className="h-24">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={displayData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" tick={false} />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 10 }}
                      ticks={[30, 50, 70]}
                    />
                    <Tooltip
                      formatter={(value: number) => [value.toFixed(1), 'RSI']}
                      labelFormatter={(label) => format(parseISO(label as string), 'MMM d, yyyy')}
                    />
                    <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" />
                    <ReferenceLine y={30} stroke="#22c55e" strokeDasharray="3 3" />
                    <Area
                      type="monotone"
                      dataKey="rsi"
                      stroke="#10b981"
                      fill="#10b981"
                      fillOpacity={0.2}
                      connectNulls={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* MACD Chart */}
          {showMACD && (
            <div className="mt-4">
              <div className="flex items-center gap-2 mb-2">
                <h4 className="text-sm font-medium text-gray-700">MACD (12, 26, 9)</h4>
              </div>
              <div className="h-24">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={displayData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" tick={false} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      formatter={(value: number, name: string) => [
                        value.toFixed(3),
                        name === 'macdHistogram' ? 'Histogram' : name === 'macdSignal' ? 'Signal' : 'MACD',
                      ]}
                      labelFormatter={(label) => format(parseISO(label as string), 'MMM d, yyyy')}
                    />
                    <ReferenceLine y={0} stroke="#9ca3af" />
                    <Bar dataKey="macdHistogram">
                      {displayData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={
                            entry.macdHistogram !== null && entry.macdHistogram >= 0
                              ? '#22c55e'
                              : '#ef4444'
                          }
                          opacity={0.7}
                        />
                      ))}
                    </Bar>
                    <Line
                      type="monotone"
                      dataKey="macd"
                      stroke="#0ea5e9"
                      strokeWidth={1.5}
                      dot={false}
                      connectNulls={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="macdSignal"
                      stroke="#f97316"
                      strokeWidth={1.5}
                      dot={false}
                      connectNulls={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Trend Lines Legend */}
          {trendLines.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-100">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Detected Trend Lines</h4>
              <div className="flex flex-wrap gap-2">
                {trendLines.map((line, i) => (
                  <div
                    key={i}
                    className={`text-xs px-2 py-1 rounded ${
                      line.type === 'support'
                        ? 'bg-green-50 text-green-700'
                        : 'bg-red-50 text-red-700'
                    }`}
                  >
                    {line.type === 'support' ? 'Support' : 'Resistance'}:{' '}
                    ${Number(line.startPrice).toFixed(2)} → ${Number(line.endPrice).toFixed(2)}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="h-64 flex items-center justify-center text-gray-500">
          No price data available. Click "Sync Data" to fetch data.
        </div>
      )}
    </div>
  )
}
