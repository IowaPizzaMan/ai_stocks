import { useState, useEffect } from 'react'
import { format, parseISO } from 'date-fns'
import { dataApi, NewsArticle } from '../services/api'

interface Props {
  ticker: string
}

export default function NewsPanel({ ticker }: Props) {
  const [news, setNews] = useState<NewsArticle[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchNews = async () => {
      setLoading(true)
      try {
        const response = await dataApi.getNews(ticker, 20)
        setNews(response.data)
      } catch (error) {
        console.error('Failed to fetch news:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchNews()
  }, [ticker])

  const getSentimentBadge = (sentiment: string | null) => {
    if (!sentiment) return null

    const colors = {
      positive: 'bg-green-100 text-green-800',
      negative: 'bg-red-100 text-red-800',
      neutral: 'bg-gray-100 text-gray-800',
    }

    return (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
          colors[sentiment as keyof typeof colors] || colors.neutral
        }`}
      >
        {sentiment}
      </span>
    )
  }

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return ''
    try {
      return format(parseISO(dateStr), 'MMM d, yyyy')
    } catch {
      return dateStr
    }
  }

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">Recent News</h3>

      {news.length > 0 ? (
        <div className="space-y-4 max-h-96 overflow-y-auto">
          {news.map((article) => (
            <div key={article.id} className="border-b border-gray-100 pb-4 last:border-0">
              <div className="flex items-start justify-between gap-2">
                <a
                  href={article.link || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium text-gray-900 hover:text-blue-600 line-clamp-2"
                >
                  {article.title}
                </a>
                {getSentimentBadge(article.sentiment)}
              </div>
              <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
                {article.publisher && <span>{article.publisher}</span>}
                {article.publisher && article.published_at && <span>|</span>}
                {article.published_at && <span>{formatDate(article.published_at)}</span>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-gray-500 text-center py-8">
          No news available. Click "Sync" to fetch latest news.
        </div>
      )}
    </div>
  )
}
