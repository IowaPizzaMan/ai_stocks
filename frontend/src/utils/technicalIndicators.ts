import { PriceHistory } from '../services/api'

export interface ChartDataPoint {
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  sma20?: number | null
  sma50?: number | null
  sma200?: number | null
  ema12?: number | null
  ema26?: number | null
  upperBand?: number | null
  lowerBand?: number | null
  middleBand?: number | null
  rsi?: number | null
  macd?: number | null
  macdSignal?: number | null
  macdHistogram?: number | null
}

export interface TrendLine {
  startDate: string
  endDate: string
  startPrice: number
  endPrice: number
  type: 'support' | 'resistance'
}

export interface Signal {
  indicator: string
  signal: 'buy' | 'sell' | 'neutral'
  strength: 'strong' | 'moderate' | 'weak'
  description: string
}

// Simple Moving Average
export function calculateSMA(data: (number | null)[], period: number): (number | null)[] {
  const result: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null)
      continue
    }
    let sum = 0
    let count = 0
    for (let j = 0; j < period; j++) {
      const val = data[i - j]
      if (val !== null) {
        sum += val
        count++
      }
    }
    result.push(count === period ? sum / period : null)
  }
  return result
}

// Exponential Moving Average
export function calculateEMA(data: (number | null)[], period: number): (number | null)[] {
  const result: (number | null)[] = []
  const multiplier = 2 / (period + 1)

  // Find first valid value for initial SMA
  let firstValidIdx = -1
  for (let i = 0; i < data.length; i++) {
    if (data[i] !== null) {
      firstValidIdx = i
      break
    }
  }

  if (firstValidIdx === -1 || firstValidIdx + period > data.length) {
    return data.map(() => null)
  }

  // Fill nulls before we have enough data
  for (let i = 0; i < firstValidIdx + period - 1; i++) {
    result.push(null)
  }

  // Calculate initial SMA
  let sum = 0
  for (let i = firstValidIdx; i < firstValidIdx + period; i++) {
    sum += data[i]!
  }
  let ema = sum / period
  result.push(ema)

  // Calculate EMA for remaining data
  for (let i = firstValidIdx + period; i < data.length; i++) {
    const val = data[i]
    if (val !== null) {
      ema = (val - ema) * multiplier + ema
      result.push(ema)
    } else {
      result.push(null)
    }
  }

  return result
}

// Relative Strength Index
export function calculateRSI(data: (number | null)[], period: number = 14): (number | null)[] {
  const result: (number | null)[] = []
  const gains: number[] = []
  const losses: number[] = []

  for (let i = 0; i < data.length; i++) {
    if (i === 0 || data[i] === null || data[i - 1] === null) {
      result.push(null)
      continue
    }

    const change = data[i]! - data[i - 1]!
    gains.push(change > 0 ? change : 0)
    losses.push(change < 0 ? Math.abs(change) : 0)

    if (gains.length < period) {
      result.push(null)
      continue
    }

    // Calculate average gain and loss
    const recentGains = gains.slice(-period)
    const recentLosses = losses.slice(-period)

    const avgGain = recentGains.reduce((a, b) => a + b, 0) / period
    const avgLoss = recentLosses.reduce((a, b) => a + b, 0) / period

    if (avgLoss === 0) {
      result.push(100)
    } else {
      const rs = avgGain / avgLoss
      result.push(100 - (100 / (1 + rs)))
    }
  }

  return result
}

// MACD (Moving Average Convergence Divergence)
export function calculateMACD(data: (number | null)[]): {
  macd: (number | null)[]
  signal: (number | null)[]
  histogram: (number | null)[]
} {
  const ema12 = calculateEMA(data, 12)
  const ema26 = calculateEMA(data, 26)

  const macdLine: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (ema12[i] !== null && ema26[i] !== null) {
      macdLine.push(ema12[i]! - ema26[i]!)
    } else {
      macdLine.push(null)
    }
  }

  const signalLine = calculateEMA(macdLine, 9)

  const histogram: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (macdLine[i] !== null && signalLine[i] !== null) {
      histogram.push(macdLine[i]! - signalLine[i]!)
    } else {
      histogram.push(null)
    }
  }

  return { macd: macdLine, signal: signalLine, histogram }
}

// Bollinger Bands
export function calculateBollingerBands(data: (number | null)[], period: number = 20, stdDev: number = 2): {
  upper: (number | null)[]
  middle: (number | null)[]
  lower: (number | null)[]
} {
  const middle = calculateSMA(data, period)
  const upper: (number | null)[] = []
  const lower: (number | null)[] = []

  for (let i = 0; i < data.length; i++) {
    if (i < period - 1 || middle[i] === null) {
      upper.push(null)
      lower.push(null)
      continue
    }

    // Calculate standard deviation
    let sumSquares = 0
    let count = 0
    for (let j = 0; j < period; j++) {
      const val = data[i - j]
      if (val !== null && middle[i] !== null) {
        sumSquares += Math.pow(val - middle[i]!, 2)
        count++
      }
    }

    if (count === period) {
      const std = Math.sqrt(sumSquares / period)
      upper.push(middle[i]! + stdDev * std)
      lower.push(middle[i]! - stdDev * std)
    } else {
      upper.push(null)
      lower.push(null)
    }
  }

  return { upper, middle, lower }
}

// Find Support and Resistance Levels
export function findSupportResistance(data: ChartDataPoint[], lookback: number = 20): {
  support: number[]
  resistance: number[]
} {
  if (!data || data.length < lookback * 2) {
    return { support: [], resistance: [] }
  }

  const highs: number[] = []
  const lows: number[] = []

  // Find local highs and lows
  for (let i = lookback; i < data.length - lookback; i++) {
    const current = data[i]
    if (current.high === null || current.low === null) continue

    let isLocalHigh = true
    let isLocalLow = true

    for (let j = i - lookback; j <= i + lookback; j++) {
      if (j === i) continue
      const compare = data[j]
      if (compare.high !== null && compare.high > current.high!) {
        isLocalHigh = false
      }
      if (compare.low !== null && compare.low < current.low!) {
        isLocalLow = false
      }
    }

    if (isLocalHigh) highs.push(current.high!)
    if (isLocalLow) lows.push(current.low!)
  }

  // Cluster nearby levels
  const clusterLevels = (levels: number[], threshold: number): number[] => {
    if (levels.length === 0) return []
    const sorted = [...levels].sort((a, b) => a - b)
    const clusters: number[][] = [[sorted[0]]]

    for (let i = 1; i < sorted.length; i++) {
      const lastCluster = clusters[clusters.length - 1]
      const lastValue = lastCluster[lastCluster.length - 1]
      if ((sorted[i] - lastValue) / lastValue < threshold) {
        lastCluster.push(sorted[i])
      } else {
        clusters.push([sorted[i]])
      }
    }

    return clusters.map(cluster =>
      cluster.reduce((a, b) => a + b, 0) / cluster.length
    )
  }

  return {
    support: clusterLevels(lows, 0.02).slice(-3),
    resistance: clusterLevels(highs, 0.02).slice(-3)
  }
}

// Calculate Trend Lines using linear regression on highs/lows
export function calculateTrendLines(data: ChartDataPoint[], minPoints: number = 10): TrendLine[] {
  if (data.length < minPoints) return []

  const lines: TrendLine[] = []
  const recentData = data.slice(-60) // Use last 60 data points

  // Find trend line for highs (resistance)
  const highs = recentData
    .map((d, i) => ({ idx: i, value: d.high, date: d.date }))
    .filter(d => d.value !== null) as { idx: number; value: number; date: string }[]

  if (highs.length >= 2) {
    // Simple approach: connect recent swing highs
    const sortedHighs = [...highs].sort((a, b) => b.value - a.value)
    const topHighs = sortedHighs.slice(0, Math.min(5, sortedHighs.length))

    if (topHighs.length >= 2) {
      const sorted = topHighs.sort((a, b) => a.idx - b.idx)
      const first = sorted[0]
      const last = sorted[sorted.length - 1]

      if (first.idx !== last.idx) {
        lines.push({
          startDate: first.date,
          endDate: last.date,
          startPrice: first.value,
          endPrice: last.value,
          type: 'resistance'
        })
      }
    }
  }

  // Find trend line for lows (support)
  const lows = recentData
    .map((d, i) => ({ idx: i, value: d.low, date: d.date }))
    .filter(d => d.value !== null) as { idx: number; value: number; date: string }[]

  if (lows.length >= 2) {
    const sortedLows = [...lows].sort((a, b) => a.value - b.value)
    const bottomLows = sortedLows.slice(0, Math.min(5, sortedLows.length))

    if (bottomLows.length >= 2) {
      const sorted = bottomLows.sort((a, b) => a.idx - b.idx)
      const first = sorted[0]
      const last = sorted[sorted.length - 1]

      if (first.idx !== last.idx) {
        lines.push({
          startDate: first.date,
          endDate: last.date,
          startPrice: first.value,
          endPrice: last.value,
          type: 'support'
        })
      }
    }
  }

  return lines
}

// Generate trading signals based on indicators
export function generateSignals(data: ChartDataPoint[]): Signal[] {
  if (data.length < 2) return []

  const signals: Signal[] = []
  const latest = data[data.length - 1]
  const prev = data[data.length - 2]

  // Price vs Moving Averages
  if (latest.close !== null && latest.sma20 !== null) {
    const closeNum = Number(latest.close)
    const sma20Num = Number(latest.sma20)
    if (closeNum > sma20Num) {
      signals.push({
        indicator: 'Price vs SMA20',
        signal: 'buy',
        strength: 'moderate',
        description: `Price ($${closeNum.toFixed(2)}) above 20-day MA ($${sma20Num.toFixed(2)})`
      })
    } else {
      signals.push({
        indicator: 'Price vs SMA20',
        signal: 'sell',
        strength: 'moderate',
        description: `Price ($${closeNum.toFixed(2)}) below 20-day MA ($${sma20Num.toFixed(2)})`
      })
    }
  }

  if (latest.close !== null && latest.sma50 !== null && latest.sma200 !== null) {
    // Golden Cross / Death Cross
    if (latest.sma50 > latest.sma200 && prev.sma50 !== null && prev.sma200 !== null && prev.sma50 <= prev.sma200) {
      signals.push({
        indicator: 'Golden Cross',
        signal: 'buy',
        strength: 'strong',
        description: '50-day MA crossed above 200-day MA - bullish long-term signal'
      })
    } else if (latest.sma50 < latest.sma200 && prev.sma50 !== null && prev.sma200 !== null && prev.sma50 >= prev.sma200) {
      signals.push({
        indicator: 'Death Cross',
        signal: 'sell',
        strength: 'strong',
        description: '50-day MA crossed below 200-day MA - bearish long-term signal'
      })
    } else if (latest.sma50 > latest.sma200) {
      signals.push({
        indicator: 'MA Trend',
        signal: 'buy',
        strength: 'moderate',
        description: '50-day MA above 200-day MA - bullish trend'
      })
    } else {
      signals.push({
        indicator: 'MA Trend',
        signal: 'sell',
        strength: 'moderate',
        description: '50-day MA below 200-day MA - bearish trend'
      })
    }
  }

  // RSI Signals
  if (latest.rsi !== null) {
    const rsiNum = Number(latest.rsi)
    if (rsiNum < 30) {
      signals.push({
        indicator: 'RSI',
        signal: 'buy',
        strength: rsiNum < 20 ? 'strong' : 'moderate',
        description: `RSI at ${rsiNum.toFixed(1)} - oversold territory`
      })
    } else if (rsiNum > 70) {
      signals.push({
        indicator: 'RSI',
        signal: 'sell',
        strength: rsiNum > 80 ? 'strong' : 'moderate',
        description: `RSI at ${rsiNum.toFixed(1)} - overbought territory`
      })
    } else {
      signals.push({
        indicator: 'RSI',
        signal: 'neutral',
        strength: 'weak',
        description: `RSI at ${rsiNum.toFixed(1)} - neutral zone`
      })
    }
  }

  // MACD Signals
  if (latest.macd !== null && latest.macdSignal !== null && prev.macd !== null && prev.macdSignal !== null) {
    if (latest.macd > latest.macdSignal && prev.macd <= prev.macdSignal) {
      signals.push({
        indicator: 'MACD',
        signal: 'buy',
        strength: 'strong',
        description: 'MACD crossed above signal line - bullish momentum'
      })
    } else if (latest.macd < latest.macdSignal && prev.macd >= prev.macdSignal) {
      signals.push({
        indicator: 'MACD',
        signal: 'sell',
        strength: 'strong',
        description: 'MACD crossed below signal line - bearish momentum'
      })
    } else if (latest.macd > latest.macdSignal) {
      signals.push({
        indicator: 'MACD',
        signal: 'buy',
        strength: 'weak',
        description: 'MACD above signal line - positive momentum'
      })
    } else {
      signals.push({
        indicator: 'MACD',
        signal: 'sell',
        strength: 'weak',
        description: 'MACD below signal line - negative momentum'
      })
    }
  }

  // Bollinger Bands
  if (latest.close !== null && latest.upperBand !== null && latest.lowerBand !== null) {
    if (latest.close > latest.upperBand) {
      signals.push({
        indicator: 'Bollinger Bands',
        signal: 'sell',
        strength: 'moderate',
        description: 'Price above upper band - potentially overbought'
      })
    } else if (latest.close < latest.lowerBand) {
      signals.push({
        indicator: 'Bollinger Bands',
        signal: 'buy',
        strength: 'moderate',
        description: 'Price below lower band - potentially oversold'
      })
    } else {
      signals.push({
        indicator: 'Bollinger Bands',
        signal: 'neutral',
        strength: 'weak',
        description: 'Price within bands - normal volatility'
      })
    }
  }

  return signals
}

// Calculate overall recommendation
export function getOverallRecommendation(signals: Signal[]): {
  recommendation: 'Strong Buy' | 'Buy' | 'Hold' | 'Sell' | 'Strong Sell'
  score: number
  summary: string
} {
  let score = 0

  for (const signal of signals) {
    const multiplier = signal.strength === 'strong' ? 2 : signal.strength === 'moderate' ? 1 : 0.5
    if (signal.signal === 'buy') {
      score += multiplier
    } else if (signal.signal === 'sell') {
      score -= multiplier
    }
  }

  // Normalize to -10 to +10 scale
  const maxScore = signals.length * 2
  const normalizedScore = maxScore > 0 ? (score / maxScore) * 10 : 0

  let recommendation: 'Strong Buy' | 'Buy' | 'Hold' | 'Sell' | 'Strong Sell'
  let summary: string

  if (normalizedScore >= 5) {
    recommendation = 'Strong Buy'
    summary = 'Multiple indicators suggest strong bullish momentum'
  } else if (normalizedScore >= 2) {
    recommendation = 'Buy'
    summary = 'Technical indicators lean bullish'
  } else if (normalizedScore >= -2) {
    recommendation = 'Hold'
    summary = 'Mixed signals - wait for clearer direction'
  } else if (normalizedScore >= -5) {
    recommendation = 'Sell'
    summary = 'Technical indicators lean bearish'
  } else {
    recommendation = 'Strong Sell'
    summary = 'Multiple indicators suggest strong bearish momentum'
  }

  return { recommendation, score: normalizedScore, summary }
}

// Helper to safely convert to number
function toNum(val: number | string | null | undefined): number | null {
  if (val === null || val === undefined) return null
  const num = Number(val)
  return isNaN(num) ? null : num
}

// Process price data and calculate all indicators
export function processChartData(prices: PriceHistory[]): ChartDataPoint[] {
  if (!prices || prices.length === 0) {
    return []
  }

  // Convert all price values to numbers upfront
  const closes = prices.map(p => toNum(p.close))

  const sma20 = calculateSMA(closes, 20)
  const sma50 = calculateSMA(closes, 50)
  const sma200 = calculateSMA(closes, 200)
  const rsi = calculateRSI(closes)
  const macd = calculateMACD(closes)
  const bollinger = calculateBollingerBands(closes)

  return prices.map((p, i) => ({
    date: p.date,
    open: toNum(p.open),
    high: toNum(p.high),
    low: toNum(p.low),
    close: toNum(p.close),
    volume: toNum(p.volume),
    sma20: sma20[i],
    sma50: sma50[i],
    sma200: sma200[i],
    rsi: rsi[i],
    macd: macd.macd[i],
    macdSignal: macd.signal[i],
    macdHistogram: macd.histogram[i],
    upperBand: bollinger.upper[i],
    middleBand: bollinger.middle[i],
    lowerBand: bollinger.lower[i],
  }))
}
