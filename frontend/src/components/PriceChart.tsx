import { useState, useEffect } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import { dataApi, PriceHistory } from '../services/api'

interface Props {
  ticker: string
}

const periods = [
  { label: '1W', value: '1w' },
  { label: '1M', value: '1m' },
  { label: '3M', value: '3m' },
  { label: '1Y', value: '1y' },
  { label: '5Y', value: '5y' },
  { label: 'Max', value: 'max' },
]

export default function PriceChart({ ticker }: Props) {
  const [prices, setPrices] = useState<PriceHistory[]>([])
  const [period, setPeriod] = useState('1y')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchPrices = async () => {
      setLoading(true)
      try {
        const response = await dataApi.getPrices(ticker, period)
        setPrices(response.data)
      } catch (error) {
        console.error('Failed to fetch prices:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchPrices()
  }, [ticker, period])

  const chartData = prices.map((p) => ({
    date: p.date,
    close: p.close ? Number(p.close) : null,
    volume: p.volume,
  }))

  const formatDate = (dateStr: string) => {
    try {
      return format(parseISO(dateStr), 'MMM d')
    } catch {
      return dateStr
    }
  }

  const formatPrice = (value: number) => `$${value.toFixed(2)}`

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-medium text-gray-900">Price History</h3>
        <div className="flex gap-1">
          {periods.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`px-3 py-1 text-sm rounded ${
                period === p.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {chartData.length > 0 ? (
        <>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatDate}
                  tick={{ fontSize: 12 }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tickFormatter={formatPrice}
                  tick={{ fontSize: 12 }}
                  domain={['auto', 'auto']}
                />
                <Tooltip
                  formatter={(value: number) => [formatPrice(value), 'Close']}
                  labelFormatter={(label) => format(parseISO(label as string), 'MMM d, yyyy')}
                />
                <Line
                  type="monotone"
                  dataKey="close"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="h-24 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <XAxis dataKey="date" tick={false} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1000000).toFixed(0)}M`} />
                <Tooltip
                  formatter={(value: number) => [`${(value / 1000000).toFixed(2)}M`, 'Volume']}
                  labelFormatter={(label) => format(parseISO(label as string), 'MMM d, yyyy')}
                />
                <Bar dataKey="volume" fill="#94a3b8" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : (
        <div className="h-64 flex items-center justify-center text-gray-500">
          No price data available. Click "Sync" to fetch data.
        </div>
      )}
    </div>
  )
}
