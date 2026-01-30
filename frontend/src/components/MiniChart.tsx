import { useState, useEffect } from 'react'
import { LineChart, Line, ResponsiveContainer } from 'recharts'
import { dataApi, PriceHistory } from '../services/api'

interface Props {
  ticker: string
}

export default function MiniChart({ ticker }: Props) {
  const [prices, setPrices] = useState<PriceHistory[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const response = await dataApi.getPrices(ticker, '3m')
        setPrices(response.data)
      } catch (error) {
        console.error('Failed to fetch prices:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchPrices()
  }, [ticker])

  const chartData = prices.map((p) => ({
    close: p.close ? Number(p.close) : null,
  }))

  // Determine if the trend is up or down
  const isPositive = chartData.length >= 2 &&
    chartData[chartData.length - 1]?.close != null &&
    chartData[0]?.close != null &&
    (chartData[chartData.length - 1].close ?? 0) >= (chartData[0].close ?? 0)

  if (loading) {
    return (
      <div className="w-20 h-10 bg-gray-100 rounded animate-pulse"></div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div className="w-20 h-10 flex items-center justify-center text-xs text-gray-400">
        No data
      </div>
    )
  }

  return (
    <div className="w-20 h-10">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Line
            type="monotone"
            dataKey="close"
            stroke={isPositive ? '#22c55e' : '#ef4444'}
            strokeWidth={1.5}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
