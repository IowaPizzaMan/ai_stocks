import { useState, useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { stocksApi, dataApi, Stock } from '../services/api'
import MiniChart from '../components/MiniChart'

export default function Dashboard() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedSector, setSelectedSector] = useState('')

  useEffect(() => {
    fetchStocks()
  }, [])

  const fetchStocks = async () => {
    try {
      const response = await stocksApi.list()
      setStocks(response.data.stocks)
    } catch (error) {
      console.error('Failed to fetch stocks:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSyncAll = async () => {
    setSyncing(true)
    try {
      await dataApi.syncAll()
      fetchStocks()
    } catch (error) {
      console.error('Failed to sync all:', error)
    } finally {
      setSyncing(false)
    }
  }

  const sectors = useMemo(() => {
    const sectorSet = new Set(stocks.map((s) => s.sector).filter(Boolean))
    return Array.from(sectorSet).sort()
  }, [stocks])

  const filteredStocks = useMemo(() => {
    return stocks.filter((stock) => {
      const matchesSearch =
        searchQuery === '' ||
        stock.ticker.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (stock.company_name?.toLowerCase().includes(searchQuery.toLowerCase()) ?? false)
      const matchesSector =
        selectedSector === '' || stock.sector === selectedSector
      return matchesSearch && matchesSector
    })
  }, [stocks, searchQuery, selectedSector])

  if (loading) {
    return (
      <div className="px-4">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-32 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <button
          onClick={handleSyncAll}
          disabled={syncing || stocks.length === 0}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {syncing ? 'Syncing...' : 'Sync All'}
        </button>
      </div>

      {stocks.length > 0 && (
        <div className="flex gap-4 mb-6">
          <input
            type="text"
            placeholder="Search by name or ticker..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 max-w-xs px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          />
          <select
            value={selectedSector}
            onChange={(e) => setSelectedSector(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md shadow-sm text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">All Sectors</option>
            {sectors.map((sector) => (
              <option key={sector} value={sector}>
                {sector}
              </option>
            ))}
          </select>
        </div>
      )}

      {stocks.length === 0 ? (
        <div className="text-center py-12">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No stocks</h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by adding stocks to your watchlist.
          </p>
          <div className="mt-6">
            <Link
              to="/watchlist"
              className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Go to Watchlist
            </Link>
          </div>
        </div>
      ) : filteredStocks.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-sm text-gray-500">No stocks match your filter criteria.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredStocks.map((stock) => (
            <Link
              key={stock.id}
              to={`/stock/${stock.ticker}`}
              className="block bg-white shadow rounded-lg p-6 hover:shadow-lg transition-shadow"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-lg font-semibold text-blue-600">{stock.ticker}</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    {stock.company_name || 'Unknown Company'}
                  </p>
                </div>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                  {stock.sector || 'N/A'}
                </span>
              </div>
              <div className="mt-4 pt-4 border-t border-gray-100 flex justify-between items-end">
                <p className="text-xs text-gray-400">
                  Added: {new Date(stock.added_at).toLocaleDateString()}
                </p>
                <MiniChart ticker={stock.ticker} />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
