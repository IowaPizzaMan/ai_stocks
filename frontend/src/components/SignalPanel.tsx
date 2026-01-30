import { useState, useEffect, useMemo } from 'react'
import { dataApi, PriceHistory } from '../services/api'
import {
  processChartData,
  generateSignals,
  getOverallRecommendation,
  findSupportResistance,
  Signal,
} from '../utils/technicalIndicators'

interface Props {
  ticker: string
}

export default function SignalPanel({ ticker }: Props) {
  const [prices, setPrices] = useState<PriceHistory[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchPrices = async () => {
      setLoading(true)
      try {
        const response = await dataApi.getPrices(ticker, '1y')
        setPrices(response.data)
      } catch (error) {
        console.error('Failed to fetch prices:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchPrices()
  }, [ticker])

  const chartData = useMemo(() => {
    try {
      return processChartData(prices)
    } catch (e) {
      console.error('Error processing chart data:', e)
      return []
    }
  }, [prices])

  const signals = useMemo(() => {
    try {
      return generateSignals(chartData)
    } catch (e) {
      console.error('Error generating signals:', e)
      return []
    }
  }, [chartData])

  const { recommendation, score, summary } = useMemo(
    () => getOverallRecommendation(signals),
    [signals]
  )

  const { support, resistance } = useMemo(() => {
    try {
      return findSupportResistance(chartData)
    } catch (e) {
      console.error('Error finding support/resistance:', e)
      return { support: [], resistance: [] }
    }
  }, [chartData])

  const latestData = chartData.length > 0 ? chartData[chartData.length - 1] : null

  const getRecommendationColor = (rec: string) => {
    switch (rec) {
      case 'Strong Buy':
        return 'bg-green-600'
      case 'Buy':
        return 'bg-green-500'
      case 'Hold':
        return 'bg-yellow-500'
      case 'Sell':
        return 'bg-red-500'
      case 'Strong Sell':
        return 'bg-red-600'
      default:
        return 'bg-gray-500'
    }
  }

  const getSignalIcon = (signal: Signal['signal']) => {
    switch (signal) {
      case 'buy':
        return (
          <svg className="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
          </svg>
        )
      case 'sell':
        return (
          <svg className="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L9 12.586V5a1 1 0 012 0v7.586l2.293-2.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
        )
      default:
        return (
          <svg className="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
        )
    }
  }

  const getStrengthBadge = (strength: Signal['strength']) => {
    switch (strength) {
      case 'strong':
        return <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">Strong</span>
      case 'moderate':
        return <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">Moderate</span>
      default:
        return <span className="text-xs px-1.5 py-0.5 rounded bg-gray-50 text-gray-400">Weak</span>
    }
  }

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="h-20 bg-gray-200 rounded mb-4"></div>
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (!latestData) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Trading Signals</h3>
        <p className="text-gray-500 text-sm">No data available. Sync the stock data first.</p>
      </div>
    )
  }

  // Calculate key levels info
  const supportBelowPrice = support.filter(s => s < (latestData.close ?? 0))
  const resistanceAbovePrice = resistance.filter(r => r > (latestData.close ?? 0))

  const nearestSupport = supportBelowPrice.length > 0 ? Math.max(...supportBelowPrice) : null
  const nearestResistance = resistanceAbovePrice.length > 0 ? Math.min(...resistanceAbovePrice) : null

  const distanceToSupport = nearestSupport && latestData.close
    ? ((latestData.close - nearestSupport) / latestData.close) * 100
    : null
  const distanceToResistance = nearestResistance && latestData.close
    ? ((nearestResistance - latestData.close) / latestData.close) * 100
    : null

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">Trading Signals</h3>

      {/* Overall Recommendation */}
      <div className="mb-6">
        <div className={`${getRecommendationColor(recommendation)} text-white rounded-lg p-4`}>
          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm opacity-90">Overall Signal</p>
              <p className="text-2xl font-bold">{recommendation}</p>
            </div>
            <div className="text-right">
              <p className="text-sm opacity-90">Score</p>
              <p className="text-xl font-semibold">{score.toFixed(1)}/10</p>
            </div>
          </div>
          <p className="text-sm mt-2 opacity-90">{summary}</p>
        </div>
      </div>

      {/* Key Levels */}
      <div className="mb-6">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Key Price Levels</h4>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500">Current Price</p>
            <p className="text-lg font-semibold">${latestData.close != null ? Number(latestData.close).toFixed(2) : '-'}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500">RSI (14)</p>
            <p className={`text-lg font-semibold ${
              Number(latestData.rsi ?? 50) > 70 ? 'text-red-600' :
              Number(latestData.rsi ?? 50) < 30 ? 'text-green-600' : 'text-gray-900'
            }`}>
              {latestData.rsi != null ? Number(latestData.rsi).toFixed(1) : '-'}
            </p>
          </div>
          {nearestSupport && (
            <div className="bg-green-50 rounded-lg p-3">
              <p className="text-xs text-green-600">Nearest Support</p>
              <p className="text-lg font-semibold text-green-700">${Number(nearestSupport).toFixed(2)}</p>
              {distanceToSupport !== null && (
                <p className="text-xs text-green-600">{Number(distanceToSupport).toFixed(1)}% below</p>
              )}
            </div>
          )}
          {nearestResistance && (
            <div className="bg-red-50 rounded-lg p-3">
              <p className="text-xs text-red-600">Nearest Resistance</p>
              <p className="text-lg font-semibold text-red-700">${Number(nearestResistance).toFixed(2)}</p>
              {distanceToResistance !== null && (
                <p className="text-xs text-red-600">{Number(distanceToResistance).toFixed(1)}% above</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Moving Average Summary */}
      <div className="mb-6">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Moving Averages</h4>
        <div className="space-y-2">
          {[
            { label: 'SMA 20', value: latestData.sma20, color: 'orange' },
            { label: 'SMA 50', value: latestData.sma50, color: 'purple' },
            { label: 'SMA 200', value: latestData.sma200, color: 'red' },
          ].map(({ label, value, color }) => {
            const numValue = value != null ? Number(value) : null
            const numClose = latestData.close != null ? Number(latestData.close) : null
            const aboveMA = numValue && numClose ? numClose > numValue : null
            return (
              <div key={label} className="flex items-center justify-between text-sm">
                <span className="text-gray-600">{label}</span>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{numValue ? `$${numValue.toFixed(2)}` : '-'}</span>
                  {aboveMA !== null && (
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      aboveMA ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {aboveMA ? 'Above' : 'Below'}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Individual Signals */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-3">Indicator Signals</h4>
        <div className="space-y-2">
          {signals.map((signal, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
            >
              <div className="mt-0.5">{getSignalIcon(signal.signal)}</div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">{signal.indicator}</span>
                  {getStrengthBadge(signal.strength)}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{signal.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="mt-6 pt-4 border-t border-gray-100">
        <p className="text-xs text-gray-400">
          Technical analysis is for informational purposes only and should not be considered financial advice.
          Past performance does not guarantee future results.
        </p>
      </div>
    </div>
  )
}
