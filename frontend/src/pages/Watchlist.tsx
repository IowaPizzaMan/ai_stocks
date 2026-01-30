import { useState, useEffect } from 'react'
import { watchlistsApi, Stock, Watchlist } from '../services/api'
import StockWatchlist from '../components/StockWatchlist'
import WatchlistSelector from '../components/WatchlistSelector'

export default function WatchlistPage() {
  const [watchlists, setWatchlists] = useState<Watchlist[]>([])
  const [selectedWatchlistId, setSelectedWatchlistId] = useState<number | null>(null)
  const [stocks, setStocks] = useState<Stock[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchWatchlists()
  }, [])

  useEffect(() => {
    if (selectedWatchlistId) {
      fetchStocks()
    }
  }, [selectedWatchlistId])

  const fetchWatchlists = async () => {
    try {
      const response = await watchlistsApi.list()
      setWatchlists(response.data.watchlists)

      // Select default watchlist if none selected
      if (!selectedWatchlistId && response.data.watchlists.length > 0) {
        const defaultWatchlist = response.data.watchlists.find((w) => w.is_default)
        setSelectedWatchlistId(defaultWatchlist?.id || response.data.watchlists[0].id)
      }
    } catch (error) {
      console.error('Failed to fetch watchlists:', error)
    }
  }

  const fetchStocks = async () => {
    if (!selectedWatchlistId) return

    setLoading(true)
    try {
      const response = await watchlistsApi.get(selectedWatchlistId)
      setStocks(response.data.stocks)
    } catch (error) {
      console.error('Failed to fetch stocks:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = () => {
    fetchWatchlists()
    fetchStocks()
  }

  if (loading && watchlists.length === 0) {
    return (
      <div className="px-4">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="px-4">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Watchlist</h1>

      <WatchlistSelector
        watchlists={watchlists}
        selectedWatchlistId={selectedWatchlistId}
        onSelect={setSelectedWatchlistId}
        onWatchlistsChanged={fetchWatchlists}
      />

      <StockWatchlist
        stocks={stocks}
        watchlistId={selectedWatchlistId}
        onStockAdded={handleRefresh}
        onStockRemoved={handleRefresh}
      />
    </div>
  )
}
