import { useState, useEffect } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts'
import { format, parseISO, differenceInDays, isFuture } from 'date-fns'
import { dataApi, EarningsData } from '../services/api'

interface Props {
  ticker: string
}

interface EarningsSurprise {
  date: string
  epsEstimate: number | null
  epsActual: number | null
  surprisePercent: number | null
}

export default function EarningsPanel({ ticker }: Props) {
  const [earnings, setEarnings] = useState<EarningsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'calendar' | 'estimates' | 'growth'>('calendar')

  useEffect(() => {
    const fetchEarnings = async () => {
      setLoading(true)
      try {
        const response = await dataApi.getEarnings(ticker)
        setEarnings(response.data)
      } catch (error) {
        console.error('Failed to fetch earnings:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchEarnings()
  }, [ticker])

  const formatDate = (dateStr: string) => {
    try {
      // Handle datetime strings like "2025-10-30 16:00:00-04:00"
      const cleanDate = dateStr.split(' ')[0]
      return format(parseISO(cleanDate), 'MMM d, yyyy')
    } catch {
      return dateStr
    }
  }

  const formatShortDate = (dateStr: string) => {
    try {
      const cleanDate = dateStr.split(' ')[0]
      return format(parseISO(cleanDate), 'MMM yy')
    } catch {
      return dateStr
    }
  }

  // Parse earnings dates for calendar view
  // Data structure: { 'Earnings Date': [dates], 'EPS Estimate': [values], 'Reported EPS': [values], 'Surprise(%)': [values] }
  const parseEarningsDates = (): { upcoming: { date: string; daysAway: number; estimate: number | null } | null; history: EarningsSurprise[] } => {
    if (!earnings?.earnings_dates) return { upcoming: null, history: [] }

    const dates = earnings.earnings_dates
    // Handle both possible key names for the date index
    const indexCol = dates['Earnings Date'] || dates['index'] || []
    const epsEstimate = dates['EPS Estimate'] || []
    const epsActual = dates['Reported EPS'] || []
    const surprisePercent = dates['Surprise(%)'] || []

    const history: EarningsSurprise[] = []
    let upcoming: { date: string; daysAway: number; estimate: number | null } | null = null

    indexCol.forEach((dateStr, i) => {
      if (!dateStr) return

      // Parse date - handle "2025-10-30 16:00:00-04:00" format
      const cleanDateStr = String(dateStr).split(' ')[0]
      let date: Date
      try {
        date = parseISO(cleanDateStr)
      } catch {
        return
      }

      const estimate = epsEstimate[i] as number | null
      const actual = epsActual[i] as number | null
      const surprise = surprisePercent[i] as number | null

      // Check if this is a future date (upcoming earnings)
      if (isFuture(date) && !upcoming) {
        upcoming = {
          date: String(dateStr),
          daysAway: differenceInDays(date, new Date()),
          estimate: estimate,
        }
      }

      // Historical earnings (has actual EPS)
      if (actual !== null) {
        history.push({
          date: String(dateStr),
          epsEstimate: estimate,
          epsActual: actual,
          surprisePercent: surprise,
        })
      }
    })

    return { upcoming, history: history.slice(0, 8) }
  }

  // Parse estimates - Data structure: { period: ['0q', '+1q', '0y', '+1y'], avg: [...], low: [...], high: [...], ... }
  const parseEstimates = () => {
    const epsEst = earnings?.earnings_estimate || {}
    const revEst = earnings?.revenue_estimate || {}
    const revisions = earnings?.eps_revisions || {}

    const periods = epsEst['period'] || epsEst['index'] || []
    const epsAvg = epsEst['avg'] || []
    const epsLow = epsEst['low'] || []
    const epsHigh = epsEst['high'] || []
    const epsGrowth = epsEst['growth'] || []
    const numAnalysts = epsEst['numberOfAnalysts'] || []

    const revAvg = revEst['avg'] || []
    const revGrowth = revEst['growth'] || []

    const periodLabels: Record<string, string> = {
      '0q': 'Current Qtr',
      '+1q': 'Next Qtr',
      '0y': 'Current Year',
      '+1y': 'Next Year',
    }

    const estimates = periods.map((period, i) => ({
      period: periodLabels[String(period)] || String(period),
      periodKey: String(period),
      epsAvg: epsAvg[i] as number | null,
      epsLow: epsLow[i] as number | null,
      epsHigh: epsHigh[i] as number | null,
      epsGrowth: epsGrowth[i] as number | null,
      numAnalysts: numAnalysts[i] as number | null,
      revAvg: revAvg[i] as number | null,
      revGrowth: revGrowth[i] as number | null,
    }))

    // Parse revisions - { period: ['0q', '+1q', ...], upLast7days: [...], upLast30days: [...], ... }
    const revPeriods = revisions['period'] || revisions['index'] || []
    const upLast7 = revisions['upLast7days'] || []
    const upLast30 = revisions['upLast30days'] || []
    const downLast7 = revisions['downLast7Days'] || revisions['downLast7days'] || []
    const downLast30 = revisions['downLast30days'] || []

    const revisionData = revPeriods.map((period, i) => ({
      period: periodLabels[String(period)] || String(period),
      upLast7: upLast7[i] as number | null,
      upLast30: upLast30[i] as number | null,
      downLast7: downLast7[i] as number | null,
      downLast30: downLast30[i] as number | null,
      netRevisions: ((upLast30[i] as number) || 0) - ((downLast30[i] as number) || 0),
    }))

    return { estimates, revisionData }
  }

  // Parse growth estimates - { period: ['0q', '+1q', ...], stockTrend: [...], indexTrend: [...] }
  const parseGrowthEstimates = () => {
    if (!earnings?.growth_estimates) return []

    const data = earnings.growth_estimates
    const periods = data['period'] || data['index'] || []
    const stockTrend = data['stockTrend'] || []
    const indexTrend = data['indexTrend'] || []

    const periodLabels: Record<string, string> = {
      '0q': 'Current Quarter',
      '+1q': 'Next Quarter',
      '0y': 'Current Year',
      '+1y': 'Next Year',
      'LTG': 'Long Term Growth',
    }

    return periods.map((period, i) => ({
      period: periodLabels[String(period)] || String(period),
      stock: stockTrend[i] as number | null,
      index: indexTrend[i] as number | null,
    }))
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

  const hasData = earnings && (
    earnings.earnings_dates ||
    earnings.earnings_estimate ||
    earnings.growth_estimates
  )

  if (!hasData) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Earnings Intelligence</h3>
        <div className="h-64 flex items-center justify-center text-gray-500">
          No earnings data available. Click "Sync" to fetch data.
        </div>
      </div>
    )
  }

  const { upcoming, history } = parseEarningsDates()
  const { estimates, revisionData } = parseEstimates()
  const growthComparison = parseGrowthEstimates()

  const tabs = [
    { key: 'calendar', label: 'Calendar' },
    { key: 'estimates', label: 'Estimates' },
    { key: 'growth', label: 'Growth' },
  ] as const

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-medium text-gray-900">Earnings Intelligence</h3>
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-3 py-1 text-sm rounded ${
                activeTab === tab.key
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Earnings Calendar Tab */}
      {activeTab === 'calendar' && (
        <div>
          {/* Next Earnings Countdown */}
          {upcoming && (
            <div className="mb-6 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg p-4 border border-purple-100">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm text-purple-600 font-medium">Next Earnings Report</div>
                  <div className="text-2xl font-bold text-gray-900">{formatDate(upcoming.date)}</div>
                  {upcoming.estimate !== null && (
                    <div className="text-sm text-gray-500 mt-1">
                      EPS Estimate: <span className="font-medium text-gray-700">${upcoming.estimate.toFixed(2)}</span>
                    </div>
                  )}
                </div>
                <div className="text-right">
                  <div className={`text-3xl font-bold ${upcoming.daysAway <= 7 ? 'text-red-600' : upcoming.daysAway <= 14 ? 'text-amber-600' : 'text-purple-600'}`}>
                    {upcoming.daysAway}
                  </div>
                  <div className="text-sm text-gray-500">days away</div>
                </div>
              </div>
            </div>
          )}

          {/* Earnings Surprise History */}
          <div className="mb-4">
            <div className="text-sm font-medium text-gray-700 mb-2">Earnings Surprise History</div>
            {history.length > 0 ? (
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={history.slice().reverse()} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" tickFormatter={(v) => `${v > 0 ? '+' : ''}${v.toFixed(0)}%`} domain={['auto', 'auto']} />
                    <YAxis type="category" dataKey="date" tickFormatter={formatShortDate} width={55} tick={{ fontSize: 11 }} />
                    <Tooltip
                      formatter={(value: number) => [`${value > 0 ? '+' : ''}${value.toFixed(2)}%`, 'Surprise']}
                      labelFormatter={(label) => formatDate(label as string)}
                    />
                    <ReferenceLine x={0} stroke="#666" />
                    <Bar dataKey="surprisePercent" name="Surprise %">
                      {history.slice().reverse().map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.surprisePercent && entry.surprisePercent > 0 ? '#22c55e' : '#ef4444'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
                No surprise history available
              </div>
            )}
          </div>

          {/* Recent Earnings Table */}
          {history.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 text-gray-500 font-medium">Date</th>
                    <th className="text-right py-2 text-gray-500 font-medium">Estimate</th>
                    <th className="text-right py-2 text-gray-500 font-medium">Actual</th>
                    <th className="text-right py-2 text-gray-500 font-medium">Surprise</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 5).map((item, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="py-2 text-gray-900">{formatDate(item.date)}</td>
                      <td className="text-right py-2 text-gray-600">
                        {item.epsEstimate !== null ? `$${item.epsEstimate.toFixed(2)}` : '-'}
                      </td>
                      <td className="text-right py-2 font-medium text-gray-900">
                        {item.epsActual !== null ? `$${item.epsActual.toFixed(2)}` : '-'}
                      </td>
                      <td className={`text-right py-2 font-medium ${item.surprisePercent && item.surprisePercent > 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {item.surprisePercent !== null ? `${item.surprisePercent > 0 ? '+' : ''}${item.surprisePercent.toFixed(2)}%` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Estimates Tab */}
      {activeTab === 'estimates' && (
        <div>
          {/* EPS Estimates */}
          {estimates.length > 0 && (
            <div className="mb-6">
              <div className="text-sm font-medium text-gray-700 mb-3">EPS Estimates</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {estimates.map((est, i) => (
                  <div key={i} className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xs text-gray-500 mb-1">{est.period}</div>
                    <div className="text-lg font-bold text-gray-900">
                      {est.epsAvg !== null ? `$${est.epsAvg.toFixed(2)}` : '-'}
                    </div>
                    {est.epsLow !== null && est.epsHigh !== null && (
                      <div className="text-xs text-gray-400">
                        ${est.epsLow.toFixed(2)} - ${est.epsHigh.toFixed(2)}
                      </div>
                    )}
                    {est.epsGrowth !== null && (
                      <div className={`text-xs mt-1 font-medium ${est.epsGrowth > 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {est.epsGrowth > 0 ? '+' : ''}{(est.epsGrowth * 100).toFixed(1)}% YoY
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Analyst Revisions */}
          {revisionData.length > 0 && (
            <div>
              <div className="text-sm font-medium text-gray-700 mb-3">Analyst Revisions (30 Days)</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {revisionData.map((rev, i) => (
                  <div key={i} className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xs text-gray-500 mb-1">{rev.period}</div>
                    <div className="flex items-center gap-2">
                      <span className="text-green-600 text-sm font-medium">+{rev.upLast30 || 0}</span>
                      <span className="text-gray-300">/</span>
                      <span className="text-red-600 text-sm font-medium">-{rev.downLast30 || 0}</span>
                    </div>
                    <div className={`text-xs mt-1 font-medium ${rev.netRevisions > 0 ? 'text-green-600' : rev.netRevisions < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                      Net: {rev.netRevisions > 0 ? '+' : ''}{rev.netRevisions}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {estimates.length === 0 && revisionData.length === 0 && (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
              No estimate data available
            </div>
          )}
        </div>
      )}

      {/* Growth Tab */}
      {activeTab === 'growth' && (
        <div>
          {growthComparison.length > 0 ? (
            <div className="space-y-4">
              <div className="text-sm font-medium text-gray-700">Growth Estimates: {ticker} vs S&P 500</div>
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-2 text-gray-500 font-medium">Period</th>
                      <th className="text-right py-2 text-purple-600 font-medium">{ticker}</th>
                      <th className="text-right py-2 text-gray-500 font-medium">S&P 500</th>
                      <th className="text-right py-2 text-gray-500 font-medium">Diff</th>
                    </tr>
                  </thead>
                  <tbody>
                    {growthComparison.map((item, i) => {
                      const diff = item.stock !== null && item.index !== null
                        ? (item.stock - item.index) * 100
                        : null
                      return (
                        <tr key={i} className="border-b border-gray-100">
                          <td className="py-3 text-gray-900">{item.period}</td>
                          <td className={`text-right py-3 font-medium ${
                            item.stock !== null && item.index !== null && item.stock > item.index
                              ? 'text-green-600'
                              : 'text-gray-900'
                          }`}>
                            {item.stock !== null ? `${(item.stock * 100).toFixed(1)}%` : '-'}
                          </td>
                          <td className="text-right py-3 text-gray-600">
                            {item.index !== null ? `${(item.index * 100).toFixed(1)}%` : '-'}
                          </td>
                          <td className={`text-right py-3 font-medium ${
                            diff !== null && diff > 0 ? 'text-green-600' : diff !== null && diff < 0 ? 'text-red-600' : 'text-gray-500'
                          }`}>
                            {diff !== null ? `${diff > 0 ? '+' : ''}${diff.toFixed(1)}%` : '-'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* Visual comparison chart */}
              <div className="h-48 mt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={growthComparison.filter(g => g.stock !== null || g.index !== null)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="period" tick={{ fontSize: 10 }} />
                    <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fontSize: 11 }} />
                    <Tooltip
                      formatter={(value: number, name: string) => [
                        `${(value * 100).toFixed(1)}%`,
                        name === 'stock' ? ticker : 'S&P 500'
                      ]}
                    />
                    <Bar dataKey="stock" fill="#8b5cf6" name="stock" />
                    <Bar dataKey="index" fill="#94a3b8" name="index" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
              No growth comparison data available
            </div>
          )}
        </div>
      )}
    </div>
  )
}
