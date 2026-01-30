import { useState, useEffect } from 'react'
import { dataApi, PriceHistory, Metrics, EarningsData } from '../services/api'
import { calculateSMA } from '../utils/technicalIndicators'

interface Props {
  ticker: string
}

interface TrendSignal {
  timeframe: string
  label: string
  signal: 'bullish' | 'bearish' | 'neutral'
  price: number | null
  ma: number | null
  description: string
}

interface FundamentalMetric {
  category: string
  name: string
  value: number | null
  target: string
  pass: boolean | null
  description: string
  helpText: string
}

interface ScoreCategory {
  name: string
  score: number
  maxScore: number
  items: { name: string; pass: boolean | null }[]
  helpText: string
}

// Help icon with tooltip component
function HelpIcon({ text }: { text: string }) {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <div className="relative inline-block">
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={() => setShowTooltip(!showTooltip)}
        className="ml-1 text-gray-400 hover:text-gray-600 focus:outline-none"
        aria-label="Help"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </button>
      {showTooltip && (
        <div className="absolute z-50 w-64 p-3 text-sm text-gray-700 bg-white border border-gray-200 rounded-lg shadow-lg -left-28 top-6">
          <div className="absolute -top-2 left-1/2 transform -translate-x-1/2 w-3 h-3 bg-white border-l border-t border-gray-200 rotate-45"></div>
          {text}
        </div>
      )}
    </div>
  )
}

// Section help definitions
const sectionHelp = {
  trend: `Trend signals show the stock's momentum across different timeframes by comparing the current price to key moving averages:

• Daily: Price vs 20-day SMA (short-term trend)
• Weekly: Price vs 50-day SMA (medium-term trend)
• Monthly: Price vs 200-day SMA (long-term trend)

Green = Price above the moving average (bullish)
Red = Price below the moving average (bearish)

All green signals indicate strong upward momentum across all timeframes.`,

  profitability: `Profitability metrics measure how efficiently a company generates profits:

• Gross Margin: (Revenue - Cost of Goods) / Revenue. Shows pricing power and production efficiency. Target: >40%

• Operating Margin: Operating Income / Revenue. Shows core business efficiency before interest and taxes. Target: >15%

• Net Margin: Net Income / Revenue. The bottom-line profit percentage. Target: >10%

• ROE (Return on Equity): Net Income / Shareholder Equity. Shows how well management uses invested capital. Target: >15%`,

  growth: `Growth metrics show the company's expansion rate:

• Revenue Growth: Year-over-year increase in total sales. Target: >10%

• EPS Growth: Year-over-year increase in earnings per share. Target: >15%

• Free Cash Flow: Cash from operations minus capital expenditures. Must be positive - indicates the company generates real cash, not just accounting profits.`,

  valuation: `Valuation metrics indicate if the stock is fairly priced:

• P/E Ratio: Stock Price / Earnings Per Share. Lower is cheaper. Target: <25

• PEG Ratio: P/E / Earnings Growth Rate. Adjusts P/E for growth. Target: <1.5 (1.0 = fairly valued)

• EV/EBITDA: Enterprise Value / EBITDA. Useful for comparing companies with different debt levels. Target: <15`,

  health: `Financial health metrics assess the company's stability:

• Debt-to-Equity: Total Debt / Shareholder Equity. Lower means less leverage risk. Target: <1.0

• Current Ratio: Current Assets / Current Liabilities. Measures short-term liquidity. Target: >1.5 (can pay short-term debts)`,

  quality: `Earnings quality shows execution consistency:

• Earnings Beat Rate: Percentage of quarters where actual EPS exceeded analyst estimates. Target: >75%

High beat rate indicates management consistently delivers or exceeds expectations.`,

  overallScore: `The overall score (0-100) aggregates all metrics:

• Each green checkmark adds points
• Each red X subtracts points
• Score is weighted across all categories

Recommendation thresholds:
• 80-100: Strong Buy
• 65-79: Buy
• 40-64: Hold
• 25-39: Sell
• 0-24: Strong Sell`,
}

export default function StockScorecard({ ticker }: Props) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [trendSignals, setTrendSignals] = useState<TrendSignal[]>([])
  const [fundamentals, setFundamentals] = useState<FundamentalMetric[]>([])
  const [overallScore, setOverallScore] = useState<number>(0)
  const [recommendation, setRecommendation] = useState<string>('Hold')
  const [categories, setCategories] = useState<ScoreCategory[]>([])

  useEffect(() => {
    fetchData()
  }, [ticker])

  const fetchData = async () => {
    setLoading(true)
    setError(null)

    try {
      const [pricesRes, metricsRes, earningsRes] = await Promise.all([
        dataApi.getPrices(ticker, '1y'),
        dataApi.getMetrics(ticker),
        dataApi.getEarnings(ticker),
      ])

      const prices = pricesRes.data
      const metrics = metricsRes.data
      const earnings = earningsRes.data

      // Calculate trend signals
      const trends = calculateTrendSignals(prices)
      setTrendSignals(trends)

      // Evaluate fundamental metrics
      const fundMetrics = evaluateFundamentals(metrics, earnings)
      setFundamentals(fundMetrics)

      // Calculate overall score
      const { score, rec, cats } = calculateOverallScore(trends, fundMetrics)
      setOverallScore(score)
      setRecommendation(rec)
      setCategories(cats)
    } catch (err) {
      console.error('Failed to fetch scorecard data:', err)
      setError('Failed to load scorecard data')
    } finally {
      setLoading(false)
    }
  }

  const calculateTrendSignals = (prices: PriceHistory[]): TrendSignal[] => {
    if (!prices || prices.length === 0) return []

    const closes = prices.map((p) => (p.close ? Number(p.close) : null))
    const currentPrice = closes[closes.length - 1]

    const sma20 = calculateSMA(closes, 20)
    const sma50 = calculateSMA(closes, 50)
    const sma200 = calculateSMA(closes, 200)

    const currentSma20 = sma20[sma20.length - 1]
    const currentSma50 = sma50[sma50.length - 1]
    const currentSma200 = sma200[sma200.length - 1]

    const signals: TrendSignal[] = []

    // Daily (Short-term) - Price vs SMA 20
    if (currentPrice !== null && currentSma20 !== null) {
      const isBullish = currentPrice > currentSma20
      signals.push({
        timeframe: 'daily',
        label: 'Daily',
        signal: isBullish ? 'bullish' : 'bearish',
        price: currentPrice,
        ma: currentSma20,
        description: `Price ${isBullish ? 'above' : 'below'} 20-day MA`,
      })
    } else {
      signals.push({
        timeframe: 'daily',
        label: 'Daily',
        signal: 'neutral',
        price: currentPrice,
        ma: null,
        description: 'Insufficient data',
      })
    }

    // Weekly (Medium-term) - Price vs SMA 50
    if (currentPrice !== null && currentSma50 !== null) {
      const isBullish = currentPrice > currentSma50
      signals.push({
        timeframe: 'weekly',
        label: 'Weekly',
        signal: isBullish ? 'bullish' : 'bearish',
        price: currentPrice,
        ma: currentSma50,
        description: `Price ${isBullish ? 'above' : 'below'} 50-day MA`,
      })
    } else {
      signals.push({
        timeframe: 'weekly',
        label: 'Weekly',
        signal: 'neutral',
        price: currentPrice,
        ma: null,
        description: 'Insufficient data',
      })
    }

    // Monthly (Long-term) - Price vs SMA 200
    if (currentPrice !== null && currentSma200 !== null) {
      const isBullish = currentPrice > currentSma200
      signals.push({
        timeframe: 'monthly',
        label: 'Monthly',
        signal: isBullish ? 'bullish' : 'bearish',
        price: currentPrice,
        ma: currentSma200,
        description: `Price ${isBullish ? 'above' : 'below'} 200-day MA`,
      })
    } else {
      signals.push({
        timeframe: 'monthly',
        label: 'Monthly',
        signal: 'neutral',
        price: currentPrice,
        ma: null,
        description: 'Insufficient data',
      })
    }

    return signals
  }

  const evaluateFundamentals = (
    metrics: Metrics,
    earnings: EarningsData
  ): FundamentalMetric[] => {
    const results: FundamentalMetric[] = []

    // Profitability Metrics
    const grossMargin = getLatestMetricValue(metrics.gross_margin)
    results.push({
      category: 'Profitability',
      name: 'Gross Margin',
      value: grossMargin,
      target: '> 40%',
      pass: grossMargin !== null ? grossMargin > 40 : null,
      description: 'Pricing power & cost control',
      helpText: 'Gross Margin = (Revenue - Cost of Goods Sold) / Revenue. Shows how much profit remains after direct production costs.',
    })

    const operatingMargin = getLatestMetricValue(metrics.operating_margin)
    results.push({
      category: 'Profitability',
      name: 'Operating Margin',
      value: operatingMargin,
      target: '> 15%',
      pass: operatingMargin !== null ? operatingMargin > 15 : null,
      description: 'Core business efficiency',
      helpText: 'Operating Margin = Operating Income / Revenue. Measures efficiency of core business operations before interest and taxes.',
    })

    const netMargin = getLatestMetricValue(metrics.net_margin)
    results.push({
      category: 'Profitability',
      name: 'Net Margin',
      value: netMargin,
      target: '> 10%',
      pass: netMargin !== null ? netMargin > 10 : null,
      description: 'Bottom-line profitability',
      helpText: 'Net Margin = Net Income / Revenue. The percentage of revenue that becomes profit after all expenses.',
    })

    results.push({
      category: 'Profitability',
      name: 'ROE',
      value: metrics.roe,
      target: '> 15%',
      pass: metrics.roe !== null ? metrics.roe > 15 : null,
      description: 'Return on shareholder equity',
      helpText: 'Return on Equity = Net Income / Shareholder Equity. Shows how effectively management uses invested capital to generate profits.',
    })

    // Growth Metrics
    const revenueGrowth = getGrowthRate(metrics.revenue)
    results.push({
      category: 'Growth',
      name: 'Revenue Growth',
      value: revenueGrowth,
      target: '> 10%',
      pass: revenueGrowth !== null ? revenueGrowth > 10 : null,
      description: 'Year-over-year revenue growth',
      helpText: 'Compares current quarter revenue to the same quarter last year. Positive growth indicates expanding business.',
    })

    const epsGrowth = getGrowthRate(metrics.eps)
    results.push({
      category: 'Growth',
      name: 'EPS Growth',
      value: epsGrowth,
      target: '> 15%',
      pass: epsGrowth !== null ? epsGrowth > 15 : null,
      description: 'Earnings per share growth',
      helpText: 'Year-over-year change in Earnings Per Share. Growing EPS means more profit per share for investors.',
    })

    const fcf = getLatestMetricValue(metrics.free_cash_flow)
    results.push({
      category: 'Growth',
      name: 'Free Cash Flow',
      value: fcf,
      target: '> 0',
      pass: fcf !== null ? fcf > 0 : null,
      description: 'Positive cash generation',
      helpText: 'Free Cash Flow = Operating Cash Flow - Capital Expenditures. Positive FCF means the company generates real cash after investments.',
    })

    // Valuation Metrics
    results.push({
      category: 'Valuation',
      name: 'P/E Ratio',
      value: metrics.pe_ratio,
      target: '< 25',
      pass: metrics.pe_ratio !== null ? metrics.pe_ratio > 0 && metrics.pe_ratio < 25 : null,
      description: 'Price to earnings ratio',
      helpText: 'Price-to-Earnings = Stock Price / EPS. Lower P/E suggests cheaper valuation. Compare to industry average for context.',
    })

    results.push({
      category: 'Valuation',
      name: 'PEG Ratio',
      value: metrics.peg_ratio,
      target: '< 1.5',
      pass: metrics.peg_ratio !== null ? metrics.peg_ratio > 0 && metrics.peg_ratio < 1.5 : null,
      description: 'P/E adjusted for growth',
      helpText: 'PEG = P/E Ratio / Earnings Growth Rate. Adjusts valuation for growth. PEG of 1.0 = fairly valued, <1 = undervalued.',
    })

    results.push({
      category: 'Valuation',
      name: 'EV/EBITDA',
      value: metrics.ev_ebitda,
      target: '< 15',
      pass: metrics.ev_ebitda !== null ? metrics.ev_ebitda > 0 && metrics.ev_ebitda < 15 : null,
      description: 'Enterprise value metric',
      helpText: 'Enterprise Value / EBITDA. Compares total company value to operating earnings. Useful for comparing companies with different debt levels.',
    })

    // Financial Health
    results.push({
      category: 'Health',
      name: 'Debt-to-Equity',
      value: metrics.debt_to_equity,
      target: '< 1.0',
      pass: metrics.debt_to_equity !== null ? metrics.debt_to_equity < 1.0 : null,
      description: 'Leverage risk',
      helpText: 'Total Debt / Shareholder Equity. Lower ratio means less reliance on debt. High debt increases risk during downturns.',
    })

    results.push({
      category: 'Health',
      name: 'Current Ratio',
      value: metrics.current_ratio,
      target: '> 1.5',
      pass: metrics.current_ratio !== null ? metrics.current_ratio > 1.5 : null,
      description: 'Short-term liquidity',
      helpText: 'Current Assets / Current Liabilities. Ratio >1.5 means the company can easily pay short-term debts.',
    })

    // Earnings Quality
    const beatRate = calculateBeatRate(earnings)
    results.push({
      category: 'Quality',
      name: 'Earnings Beat Rate',
      value: beatRate,
      target: '> 75%',
      pass: beatRate !== null ? beatRate > 75 : null,
      description: 'Consistency of execution',
      helpText: 'Percentage of quarters where actual EPS exceeded analyst estimates. High beat rate shows reliable management execution.',
    })

    return results
  }

  const getLatestMetricValue = (
    metricValues: { value: number | null }[] | undefined
  ): number | null => {
    if (!metricValues || metricValues.length === 0) return null
    const latest = metricValues[metricValues.length - 1]
    return latest?.value ?? null
  }

  const getGrowthRate = (
    metricValues: { value: number | null; change_percent: number | null }[] | undefined
  ): number | null => {
    if (!metricValues || metricValues.length < 2) return null
    // Calculate YoY growth if we have 4+ quarters
    if (metricValues.length >= 4) {
      const current = metricValues[metricValues.length - 1]?.value
      const yearAgo = metricValues[metricValues.length - 4]?.value
      if (current !== null && yearAgo !== null && yearAgo !== 0) {
        return ((current - yearAgo) / Math.abs(yearAgo)) * 100
      }
    }
    // Fall back to latest change_percent
    const latest = metricValues[metricValues.length - 1]
    return latest?.change_percent ?? null
  }

  const calculateBeatRate = (earnings: EarningsData): number | null => {
    if (!earnings?.quarterly_earnings) return null

    const surpriseData = earnings.quarterly_earnings['Surprise(%)']
    if (!surpriseData || surpriseData.length === 0) return null

    const validSurprises = surpriseData.filter(
      (s) => s !== null && typeof s === 'number'
    ) as number[]
    if (validSurprises.length === 0) return null

    const beats = validSurprises.filter((s) => s > 0).length
    return (beats / validSurprises.length) * 100
  }

  const calculateOverallScore = (
    trends: TrendSignal[],
    fundMetrics: FundamentalMetric[]
  ): { score: number; rec: string; cats: ScoreCategory[] } => {
    const categories: ScoreCategory[] = []

    // Trend Score (3 points max)
    const trendItems = trends.map((t) => ({
      name: t.label,
      pass: t.signal === 'bullish' ? true : t.signal === 'bearish' ? false : null,
    }))
    const trendScore = trends.filter((t) => t.signal === 'bullish').length
    categories.push({
      name: 'Trend',
      score: trendScore,
      maxScore: 3,
      items: trendItems,
      helpText: sectionHelp.trend,
    })

    // Group fundamentals by category
    const profitMetrics = fundMetrics.filter((m) => m.category === 'Profitability')
    const growthMetrics = fundMetrics.filter((m) => m.category === 'Growth')
    const valuationMetrics = fundMetrics.filter((m) => m.category === 'Valuation')
    const healthMetrics = fundMetrics.filter((m) => m.category === 'Health')
    const qualityMetrics = fundMetrics.filter((m) => m.category === 'Quality')

    // Profitability Score (4 points max)
    const profitScore = profitMetrics.filter((m) => m.pass === true).length
    categories.push({
      name: 'Profitability',
      score: profitScore,
      maxScore: profitMetrics.length,
      items: profitMetrics.map((m) => ({ name: m.name, pass: m.pass })),
      helpText: sectionHelp.profitability,
    })

    // Growth Score (3 points max)
    const growthScore = growthMetrics.filter((m) => m.pass === true).length
    categories.push({
      name: 'Growth',
      score: growthScore,
      maxScore: growthMetrics.length,
      items: growthMetrics.map((m) => ({ name: m.name, pass: m.pass })),
      helpText: sectionHelp.growth,
    })

    // Valuation Score (3 points max)
    const valuationScore = valuationMetrics.filter((m) => m.pass === true).length
    categories.push({
      name: 'Valuation',
      score: valuationScore,
      maxScore: valuationMetrics.length,
      items: valuationMetrics.map((m) => ({ name: m.name, pass: m.pass })),
      helpText: sectionHelp.valuation,
    })

    // Health Score (2 points max)
    const healthScore = healthMetrics.filter((m) => m.pass === true).length
    categories.push({
      name: 'Health',
      score: healthScore,
      maxScore: healthMetrics.length,
      items: healthMetrics.map((m) => ({ name: m.name, pass: m.pass })),
      helpText: sectionHelp.health,
    })

    // Quality Score (1 point max)
    const qualityScore = qualityMetrics.filter((m) => m.pass === true).length
    categories.push({
      name: 'Quality',
      score: qualityScore,
      maxScore: qualityMetrics.length,
      items: qualityMetrics.map((m) => ({ name: m.name, pass: m.pass })),
      helpText: sectionHelp.quality,
    })

    // Calculate total score
    const totalScore = categories.reduce((sum, c) => sum + c.score, 0)
    const maxTotal = categories.reduce((sum, c) => sum + c.maxScore, 0)
    const percentage = maxTotal > 0 ? (totalScore / maxTotal) * 100 : 0

    // Determine recommendation
    let rec = 'Hold'
    if (percentage >= 80) {
      rec = 'Strong Buy'
    } else if (percentage >= 65) {
      rec = 'Buy'
    } else if (percentage >= 40) {
      rec = 'Hold'
    } else if (percentage >= 25) {
      rec = 'Sell'
    } else {
      rec = 'Strong Sell'
    }

    return { score: Math.round(percentage), rec, cats: categories }
  }

  const getSignalColor = (signal: 'bullish' | 'bearish' | 'neutral') => {
    switch (signal) {
      case 'bullish':
        return 'bg-green-500'
      case 'bearish':
        return 'bg-red-500'
      default:
        return 'bg-gray-400'
    }
  }

  const getPassColor = (pass: boolean | null) => {
    if (pass === null) return 'text-gray-400'
    return pass ? 'text-green-600' : 'text-red-600'
  }

  const getPassIcon = (pass: boolean | null) => {
    if (pass === null) return '—'
    return pass ? '✓' : '✗'
  }

  const getRecommendationColor = (rec: string) => {
    switch (rec) {
      case 'Strong Buy':
        return 'bg-green-600 text-white'
      case 'Buy':
        return 'bg-green-500 text-white'
      case 'Hold':
        return 'bg-yellow-500 text-white'
      case 'Sell':
        return 'bg-red-500 text-white'
      case 'Strong Sell':
        return 'bg-red-600 text-white'
      default:
        return 'bg-gray-500 text-white'
    }
  }

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600'
    if (score >= 65) return 'text-green-500'
    if (score >= 40) return 'text-yellow-600'
    if (score >= 25) return 'text-red-500'
    return 'text-red-600'
  }

  const formatValue = (value: number | null, isPercent = false): string => {
    if (value === null) return 'N/A'
    if (isPercent) return `${value.toFixed(1)}%`
    if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`
    if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`
    if (Math.abs(value) >= 1000) return value.toFixed(0)
    return value.toFixed(2)
  }

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-3">
            <div className="h-4 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded"></div>
            <div className="h-4 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <p className="text-red-600">{error}</p>
      </div>
    )
  }

  const allTrendsGreen = trendSignals.every((t) => t.signal === 'bullish')

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden">
      {/* Header with Overall Score */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <div className="flex justify-between items-center">
          <div className="flex items-center">
            <h3 className="text-lg font-semibold text-gray-900">Stock Scorecard</h3>
            <HelpIcon text={sectionHelp.overallScore} />
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className={`text-3xl font-bold ${getScoreColor(overallScore)}`}>
                {overallScore}
                <span className="text-lg text-gray-400">/100</span>
              </div>
            </div>
            <span
              className={`px-4 py-2 rounded-lg font-semibold ${getRecommendationColor(
                recommendation
              )}`}
            >
              {recommendation}
            </span>
          </div>
        </div>
      </div>

      <div className="p-6">
        {/* Trend Signals Section */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center">
              <h4 className="font-semibold text-gray-900">Trend Signals</h4>
              <HelpIcon text={sectionHelp.trend} />
            </div>
            {allTrendsGreen && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                All Bullish
              </span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-4">
            {trendSignals.map((trend) => (
              <div
                key={trend.timeframe}
                className="border rounded-lg p-4 text-center"
              >
                <div className="flex items-center justify-center mb-2">
                  <div
                    className={`w-4 h-4 rounded-full ${getSignalColor(
                      trend.signal
                    )}`}
                  ></div>
                </div>
                <div className="font-medium text-gray-900">{trend.label}</div>
                <div className="text-xs text-gray-500 mt-1">
                  {trend.description}
                </div>
                {trend.price !== null && trend.ma !== null && (
                  <div className="text-xs text-gray-400 mt-1">
                    ${trend.price.toFixed(2)} vs ${trend.ma.toFixed(2)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Category Scores */}
        <div className="mb-6">
          <h4 className="font-semibold text-gray-900 mb-3">Score Breakdown</h4>
          <div className="space-y-2">
            {categories.map((cat) => (
              <div key={cat.name} className="flex items-center gap-3">
                <div className="w-28 text-sm font-medium text-gray-700 flex items-center">
                  {cat.name}
                  <HelpIcon text={cat.helpText} />
                </div>
                <div className="flex-1">
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        cat.score / cat.maxScore >= 0.7
                          ? 'bg-green-500'
                          : cat.score / cat.maxScore >= 0.4
                          ? 'bg-yellow-500'
                          : 'bg-red-500'
                      }`}
                      style={{
                        width: `${(cat.score / cat.maxScore) * 100}%`,
                      }}
                    ></div>
                  </div>
                </div>
                <div className="w-12 text-sm text-gray-600 text-right">
                  {cat.score}/{cat.maxScore}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Fundamental Metrics Details */}
        <div>
          <h4 className="font-semibold text-gray-900 mb-3">Fundamental Metrics</h4>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2 font-medium text-gray-500">
                    Metric
                  </th>
                  <th className="text-right py-2 font-medium text-gray-500">
                    Value
                  </th>
                  <th className="text-right py-2 font-medium text-gray-500">
                    Target
                  </th>
                  <th className="text-center py-2 font-medium text-gray-500">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody>
                {fundamentals.map((metric, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-gray-100 last:border-0"
                  >
                    <td className="py-2">
                      <div className="flex items-center">
                        <span className="font-medium text-gray-900">
                          {metric.name}
                        </span>
                        <HelpIcon text={metric.helpText} />
                      </div>
                      <div className="text-xs text-gray-500">
                        {metric.description}
                      </div>
                    </td>
                    <td className="text-right py-2 text-gray-900">
                      {metric.name.includes('Margin') ||
                      metric.name.includes('ROE') ||
                      metric.name.includes('Growth') ||
                      metric.name.includes('Beat Rate')
                        ? formatValue(metric.value, true)
                        : formatValue(metric.value)}
                    </td>
                    <td className="text-right py-2 text-gray-500">
                      {metric.target}
                    </td>
                    <td
                      className={`text-center py-2 text-lg font-bold ${getPassColor(
                        metric.pass
                      )}`}
                    >
                      {getPassIcon(metric.pass)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
