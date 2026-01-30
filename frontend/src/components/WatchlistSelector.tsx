import { useState } from 'react'
import { Watchlist, watchlistsApi } from '../services/api'

interface Props {
  watchlists: Watchlist[]
  selectedWatchlistId: number | null
  onSelect: (id: number) => void
  onWatchlistsChanged: () => void
}

export default function WatchlistSelector({
  watchlists,
  selectedWatchlistId,
  onSelect,
  onWatchlistsChanged,
}: Props) {
  const [isCreating, setIsCreating] = useState(false)
  const [isRenaming, setIsRenaming] = useState(false)
  const [newName, setNewName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const selectedWatchlist = watchlists.find((w) => w.id === selectedWatchlistId)

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim()) return

    setLoading(true)
    setError(null)

    try {
      const response = await watchlistsApi.create(newName.trim())
      setNewName('')
      setIsCreating(false)
      onWatchlistsChanged()
      onSelect(response.data.id)
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Failed to create watchlist')
    } finally {
      setLoading(false)
    }
  }

  const handleRename = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim() || !selectedWatchlistId) return

    setLoading(true)
    setError(null)

    try {
      await watchlistsApi.update(selectedWatchlistId, { name: newName.trim() })
      setNewName('')
      setIsRenaming(false)
      onWatchlistsChanged()
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Failed to rename watchlist')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!selectedWatchlistId || !selectedWatchlist) return
    if (selectedWatchlist.is_default) return

    if (!confirm(`Delete watchlist "${selectedWatchlist.name}"?`)) return

    setLoading(true)
    setError(null)

    try {
      await watchlistsApi.delete(selectedWatchlistId)
      onWatchlistsChanged()
      // Select the default watchlist
      const defaultWatchlist = watchlists.find((w) => w.is_default)
      if (defaultWatchlist) {
        onSelect(defaultWatchlist.id)
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } }
      setError(error.response?.data?.detail || 'Failed to delete watchlist')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mb-4">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label htmlFor="watchlist-select" className="text-sm font-medium text-gray-700">
            Watchlist:
          </label>
          <select
            id="watchlist-select"
            value={selectedWatchlistId || ''}
            onChange={(e) => onSelect(Number(e.target.value))}
            className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-2 border"
          >
            {watchlists.map((wl) => (
              <option key={wl.id} value={wl.id}>
                {wl.name} ({wl.stock_count})
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          {!isCreating && !isRenaming && (
            <>
              <button
                onClick={() => {
                  setIsCreating(true)
                  setNewName('')
                }}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                New
              </button>
              <button
                onClick={() => {
                  setIsRenaming(true)
                  setNewName(selectedWatchlist?.name || '')
                }}
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                Rename
              </button>
              {selectedWatchlist && !selectedWatchlist.is_default && (
                <button
                  onClick={handleDelete}
                  disabled={loading}
                  className="text-sm text-red-600 hover:text-red-800 disabled:opacity-50"
                >
                  Delete
                </button>
              )}
            </>
          )}

          {isCreating && (
            <form onSubmit={handleCreate} className="flex items-center gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="New watchlist name"
                autoFocus
                className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-2 py-1 border"
              />
              <button
                type="submit"
                disabled={loading || !newName.trim()}
                className="text-sm text-blue-600 hover:text-blue-800 disabled:opacity-50"
              >
                {loading ? 'Creating...' : 'Create'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsCreating(false)
                  setNewName('')
                  setError(null)
                }}
                className="text-sm text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
            </form>
          )}

          {isRenaming && (
            <form onSubmit={handleRename} className="flex items-center gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Rename watchlist"
                autoFocus
                className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-2 py-1 border"
              />
              <button
                type="submit"
                disabled={loading || !newName.trim()}
                className="text-sm text-blue-600 hover:text-blue-800 disabled:opacity-50"
              >
                {loading ? 'Saving...' : 'Save'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsRenaming(false)
                  setNewName('')
                  setError(null)
                }}
                className="text-sm text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
            </form>
          )}
        </div>
      </div>

      {error && <div className="mt-2 text-red-600 text-sm">{error}</div>}
    </div>
  )
}
