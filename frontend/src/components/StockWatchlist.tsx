import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Stock, watchlistsApi, dataApi } from '../services/api'

interface Props {
  stocks: Stock[]
  watchlistId: number | null
  onStockAdded: () => void
  onStockRemoved: () => void
}

export default function StockWatchlist({ stocks, watchlistId, onStockAdded, onStockRemoved }: Props) {
  const [newTicker, setNewTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [syncingTicker, setSyncingTicker] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleAddStock = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newTicker.trim() || !watchlistId) return

    setLoading(true)
    setError(null)

    try {
      await watchlistsApi.addStock(watchlistId, newTicker.trim().toUpperCase())
      setNewTicker('')
      onStockAdded()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Failed to add stock')
    } finally {
      setLoading(false)
    }
  }

  const handleRemoveStock = async (ticker: string) => {
    if (!watchlistId) return
    if (!confirm(`Remove ${ticker} from this watchlist?`)) return

    try {
      await watchlistsApi.removeStock(watchlistId, ticker)
      onStockRemoved()
    } catch {
      setError('Failed to remove stock')
    }
  }

  const handleSyncStock = async (ticker: string) => {
    setSyncingTicker(ticker)
    try {
      await dataApi.sync(ticker)
      onStockAdded()
    } catch {
      setError(`Failed to sync ${ticker}`)
    } finally {
      setSyncingTicker(null)
    }
  }

  return (
    <div className="bg-white shadow rounded-lg">
      <div className="px-4 py-5 sm:p-6">
        <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">Stocks</h3>

        <form onSubmit={handleAddStock} className="mb-4 flex gap-2">
          <input
            type="text"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            placeholder="Enter ticker (e.g., AAPL)"
            className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-2 border"
          />
          <button
            type="submit"
            disabled={loading || !watchlistId}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {loading ? 'Adding...' : 'Add'}
          </button>
        </form>

        {error && (
          <div className="mb-4 text-red-600 text-sm">{error}</div>
        )}

        <div className="overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Ticker
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Company
                </th>
                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Sector
                </th>
                <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {stocks.map((stock) => (
                <tr key={stock.id}>
                  <td className="px-3 py-4 whitespace-nowrap">
                    <Link
                      to={`/stock/${stock.ticker}`}
                      className="text-blue-600 hover:text-blue-800 font-medium"
                    >
                      {stock.ticker}
                    </Link>
                  </td>
                  <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-500">
                    {stock.company_name || '-'}
                  </td>
                  <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-500">
                    {stock.sector || '-'}
                  </td>
                  <td className="px-3 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => handleSyncStock(stock.ticker)}
                      disabled={syncingTicker === stock.ticker}
                      className="text-blue-600 hover:text-blue-900 mr-3 disabled:opacity-50"
                    >
                      {syncingTicker === stock.ticker ? 'Syncing...' : 'Sync'}
                    </button>
                    <button
                      onClick={() => handleRemoveStock(stock.ticker)}
                      className="text-red-600 hover:text-red-900"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
              {stocks.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-3 py-4 text-center text-gray-500">
                    No stocks in this watchlist. Add one above.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
