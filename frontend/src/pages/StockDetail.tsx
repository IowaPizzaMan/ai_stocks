import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { stocksApi, dataApi, Stock } from '../services/api'
import StockScorecard from '../components/StockScorecard'
import TechnicalChart from '../components/TechnicalChart'
import FinancialsChart from '../components/FinancialsChart'
import EarningsPanel from '../components/EarningsPanel'
import NewsPanel from '../components/NewsPanel'
import AnalysisPanel from '../components/AnalysisPanel'

export default function StockDetail() {
  const { ticker } = useParams<{ ticker: string }>()
  const [stock, setStock] = useState<Stock | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    if (ticker) {
      fetchStock()
    }
  }, [ticker])

  const fetchStock = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await stocksApi.get(ticker!)
      setStock(response.data)
    } catch {
      setError('Stock not found')
    } finally {
      setLoading(false)
    }
  }

  const handleSync = async () => {
    if (!ticker) return
    setSyncing(true)
    try {
      await dataApi.sync(ticker)
      setRefreshKey((k) => k + 1)
    } catch (error) {
      console.error('Failed to sync:', error)
    } finally {
      setSyncing(false)
    }
  }

  if (loading) {
    return (
      <div className="px-4">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="space-y-4">
            <div className="h-64 bg-gray-200 rounded"></div>
            <div className="h-64 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !stock) {
    return (
      <div className="px-4">
        <div className="text-center py-12">
          <h2 className="text-xl font-semibold text-gray-900">Stock not found</h2>
          <p className="mt-2 text-gray-500">
            The stock "{ticker}" is not in your watchlist.
          </p>
          <Link
            to="/watchlist"
            className="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"
          >
            Go to Watchlist
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4">
      <div className="flex justify-between items-start mb-6">
        <div>
          <div className="flex items-center gap-2">
            <Link to="/" className="text-gray-400 hover:text-gray-600">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">{stock.ticker}</h1>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              {stock.sector || 'N/A'}
            </span>
          </div>
          <p className="text-gray-500 mt-1">{stock.company_name || 'Unknown Company'}</p>
          {stock.industry && (
            <p className="text-sm text-gray-400">{stock.industry}</p>
          )}
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {syncing ? 'Syncing...' : 'Sync Data'}
        </button>
      </div>

      <div className="space-y-6" key={refreshKey}>
        {/* Technical Chart at the top */}
        <TechnicalChart ticker={stock.ticker} />

        {/* Stock Scorecard - Buy/Sell Assessment */}
        <StockScorecard ticker={stock.ticker} />

        {/* Financials Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <FinancialsChart ticker={stock.ticker} />
          <EarningsPanel ticker={stock.ticker} />
        </div>

        {/* News & AI Analysis Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <NewsPanel ticker={stock.ticker} />
          <AnalysisPanel ticker={stock.ticker} />
        </div>
      </div>
    </div>
  )
}
