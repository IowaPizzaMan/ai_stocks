import { useState, useEffect } from 'react'
import { format, parseISO } from 'date-fns'
import { analysisApi, StockAnalysis } from '../services/api'

interface Props {
  ticker: string
}

export default function AnalysisPanel({ ticker }: Props) {
  const [analysis, setAnalysis] = useState<StockAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [activeTab, setActiveTab] = useState<'bull' | 'bear' | 'outlook'>('bull')

  useEffect(() => {
    fetchAnalysis()
  }, [ticker])

  const fetchAnalysis = async () => {
    setLoading(true)
    try {
      const response = await analysisApi.get(ticker)
      setAnalysis(response.data)
    } catch (error) {
      console.error('Failed to fetch analysis:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const response = await analysisApi.trigger(ticker)
      setAnalysis(response.data)
    } catch (error) {
      console.error('Failed to generate analysis:', error)
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-medium text-gray-900">Stock Analysis</h3>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {generating ? 'Generating...' : 'Generate Analysis'}
        </button>
      </div>

      {analysis ? (
        <>
          <div className="mb-4 flex items-center gap-4 text-sm text-gray-500">
            <span>
              Generated: {format(parseISO(analysis.analysis_date), 'MMM d, yyyy')}
            </span>
            {analysis.confidence_score && (
              <span>
                Confidence: {(Number(analysis.confidence_score) * 100).toFixed(0)}%
              </span>
            )}
          </div>

          {analysis.news_summary && (
            <div className="mb-4 p-3 bg-gray-50 rounded-lg">
              <div className="text-sm font-medium text-gray-700 mb-1">News Summary</div>
              <p className="text-sm text-gray-600">{analysis.news_summary}</p>
            </div>
          )}

          <div className="flex gap-1 mb-4">
            <button
              onClick={() => setActiveTab('bull')}
              className={`px-3 py-1 text-sm rounded ${
                activeTab === 'bull'
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              Bull Case
            </button>
            <button
              onClick={() => setActiveTab('bear')}
              className={`px-3 py-1 text-sm rounded ${
                activeTab === 'bear'
                  ? 'bg-red-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              Bear Case
            </button>
            <button
              onClick={() => setActiveTab('outlook')}
              className={`px-3 py-1 text-sm rounded ${
                activeTab === 'outlook'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              Outlook
            </button>
          </div>

          <div className="prose prose-sm max-w-none">
            {activeTab === 'bull' && (
              <div className="p-4 bg-green-50 rounded-lg border-l-4 border-green-500">
                <h4 className="text-green-800 font-medium mb-2">Bull Case</h4>
                <p className="text-gray-700 whitespace-pre-wrap">
                  {analysis.bull_case || 'No bull case available.'}
                </p>
              </div>
            )}

            {activeTab === 'bear' && (
              <div className="p-4 bg-red-50 rounded-lg border-l-4 border-red-500">
                <h4 className="text-red-800 font-medium mb-2">Bear Case</h4>
                <p className="text-gray-700 whitespace-pre-wrap">
                  {analysis.bear_case || 'No bear case available.'}
                </p>
              </div>
            )}

            {activeTab === 'outlook' && (
              <div className="space-y-4">
                <div className="p-4 bg-blue-50 rounded-lg">
                  <h4 className="text-blue-800 font-medium mb-2">Short-Term Outlook</h4>
                  <p className="text-gray-700">
                    {analysis.short_term_outlook || 'No short-term outlook available.'}
                  </p>
                </div>
                <div className="p-4 bg-purple-50 rounded-lg">
                  <h4 className="text-purple-800 font-medium mb-2">Long-Term Outlook</h4>
                  <p className="text-gray-700">
                    {analysis.long_term_outlook || 'No long-term outlook available.'}
                  </p>
                </div>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <p className="mb-4">No analysis available for this stock.</p>
          <p className="text-sm">
            Click "Generate Analysis" to create bull/bear cases based on financial data and news.
          </p>
          <p className="text-sm text-gray-400 mt-2">
            Analysis uses synced financial data. For AI-powered insights, enable Ollama.
          </p>
        </div>
      )}
    </div>
  )
}
