import { useState, useEffect } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import { dataApi, Metrics } from '../services/api'

interface Props {
  ticker: string
}

export default function FinancialsChart({ ticker }: Props) {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'revenue' | 'margins' | 'eps' | 'cashflow'>('revenue')

  useEffect(() => {
    const fetchMetrics = async () => {
      setLoading(true)
      try {
        const response = await dataApi.getMetrics(ticker)
        setMetrics(response.data)
      } catch (error) {
        console.error('Failed to fetch metrics:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchMetrics()
  }, [ticker])

  const formatDate = (dateStr: string) => {
    try {
      return format(parseISO(dateStr), 'MMM yy')
    } catch {
      return dateStr
    }
  }

  const formatLargeNumber = (value: number) => {
    if (Math.abs(value) >= 1e9) return `$${(value / 1e9).toFixed(1)}B`
    if (Math.abs(value) >= 1e6) return `$${(value / 1e6).toFixed(1)}M`
    return `$${value.toFixed(0)}`
  }

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

  if (!metrics || metrics.revenue.length === 0) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Financial Metrics</h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          No financial data available. Click "Sync" to fetch data.
        </div>
      </div>
    )
  }

  const tabs = [
    { key: 'revenue', label: 'Revenue' },
    { key: 'margins', label: 'Margins' },
    { key: 'eps', label: 'EPS' },
    { key: 'cashflow', label: 'Cash Flow' },
  ] as const

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-medium text-gray-900">Financial Metrics</h3>
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 py-1 text-sm rounded ${
                activeTab === tab.key
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="h-64">
        {activeTab === 'revenue' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={metrics.revenue}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" tickFormatter={formatDate} tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={formatLargeNumber} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value: number) => [formatLargeNumber(value), 'Revenue']}
                labelFormatter={(label) => `Q: ${formatDate(label as string)}`}
              />
              <Bar dataKey="value" fill="#2563eb" />
            </BarChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'margins' && (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={metrics.gross_margin.map((g, i) => ({
                period: g.period,
                gross: g.value,
                operating: metrics.operating_margin[i]?.value,
                net: metrics.net_margin[i]?.value,
              }))}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" tickFormatter={formatDate} tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value: number) => [`${value?.toFixed(1)}%`, '']} />
              <Legend />
              <Line type="monotone" dataKey="gross" stroke="#22c55e" name="Gross" />
              <Line type="monotone" dataKey="operating" stroke="#3b82f6" name="Operating" />
              <Line type="monotone" dataKey="net" stroke="#ef4444" name="Net" />
            </LineChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'eps' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={metrics.eps}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" tickFormatter={formatDate} tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={(v) => `$${v}`} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value: number) => [`$${value?.toFixed(2)}`, 'EPS']}
                labelFormatter={(label) => `Q: ${formatDate(label as string)}`}
              />
              <Bar dataKey="value" fill="#8b5cf6" />
            </BarChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'cashflow' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={metrics.free_cash_flow}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" tickFormatter={formatDate} tick={{ fontSize: 12 }} />
              <YAxis tickFormatter={formatLargeNumber} tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value: number) => [formatLargeNumber(value), 'FCF']}
                labelFormatter={(label) => `Q: ${formatDate(label as string)}`}
              />
              <Bar dataKey="value" fill="#14b8a6" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-50 rounded p-3">
          <div className="text-sm text-gray-500">P/E Ratio</div>
          <div className="text-lg font-semibold">{metrics.pe_ratio?.toFixed(2) || '-'}</div>
        </div>
        <div className="bg-gray-50 rounded p-3">
          <div className="text-sm text-gray-500">P/S Ratio</div>
          <div className="text-lg font-semibold">{metrics.ps_ratio?.toFixed(2) || '-'}</div>
        </div>
        <div className="bg-gray-50 rounded p-3">
          <div className="text-sm text-gray-500">Debt/Equity</div>
          <div className="text-lg font-semibold">{metrics.debt_to_equity?.toFixed(2) || '-'}</div>
        </div>
        <div className="bg-gray-50 rounded p-3">
          <div className="text-sm text-gray-500">ROE</div>
          <div className="text-lg font-semibold">
            {metrics.roe ? `${(metrics.roe * 100).toFixed(1)}%` : '-'}
          </div>
        </div>
      </div>
    </div>
  )
}
