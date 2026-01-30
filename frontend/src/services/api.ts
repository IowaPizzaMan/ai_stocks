import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

export interface Stock {
  id: number
  ticker: string
  company_name: string | null
  sector: string | null
  industry: string | null
  added_at: string
  is_active: boolean
}

export interface PriceHistory {
  id: number
  stock_id: number
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  adj_close: number | null
  volume: number | null
}

export interface FinancialStatement {
  id: number
  stock_id: number
  period_end: string
  period_type: string
  statement_type: string
  data: Record<string, number | string>
  fetched_at: string
}

export interface NewsArticle {
  id: number
  stock_id: number
  article_id: string
  title: string
  link: string | null
  publisher: string | null
  published_at: string | null
  sentiment: string | null
  sentiment_score: number | null
  fetched_at: string
}

export interface StockAnalysis {
  id: number
  stock_id: number
  analysis_date: string
  bull_case: string | null
  bear_case: string | null
  short_term_outlook: string | null
  long_term_outlook: string | null
  confidence_score: number | null
  news_summary: string | null
  created_at: string
}

export interface MetricValue {
  period: string
  value: number | null
  change_percent: number | null
}

export interface Metrics {
  ticker: string
  revenue: MetricValue[]
  gross_margin: MetricValue[]
  operating_margin: MetricValue[]
  net_margin: MetricValue[]
  eps: MetricValue[]
  free_cash_flow: MetricValue[]
  pe_ratio: number | null
  ps_ratio: number | null
  pb_ratio: number | null
  peg_ratio: number | null
  ev_ebitda: number | null
  current_ratio: number | null
  debt_to_equity: number | null
  roe: number | null
  roa: number | null
}

export interface SyncResponse {
  ticker: string
  prices_synced: number
  financials_synced: number
  news_synced: number
  earnings_synced: number
  status: string
  message: string
}

export interface EarningsData {
  ticker: string
  annual_earnings: Record<string, (number | string | null)[]> | null
  quarterly_earnings: Record<string, (number | string | null)[]> | null
  earnings_dates: Record<string, (number | string | null)[]> | null
  earnings_estimate: Record<string, (number | string | null)[]> | null
  revenue_estimate: Record<string, (number | string | null)[]> | null
  earnings_trend: Record<string, (number | string | null)[]> | null
  growth_estimates: Record<string, (number | string | null)[]> | null
  eps_revisions: Record<string, (number | string | null)[]> | null
}

export interface Watchlist {
  id: number
  name: string
  description: string | null
  is_default: boolean
  is_active: boolean
  created_at: string
  updated_at: string
  stock_count: number
}

export interface WatchlistDetail {
  id: number
  name: string
  description: string | null
  is_default: boolean
  is_active: boolean
  created_at: string
  updated_at: string
  stocks: Stock[]
}

export const stocksApi = {
  list: () => api.get<{ stocks: Stock[]; total: number }>('/stocks'),
  get: (ticker: string) => api.get<Stock>(`/stocks/${ticker}`),
  add: (ticker: string) => api.post<Stock>('/stocks', { ticker }),
  remove: (ticker: string) => api.delete(`/stocks/${ticker}`),
}

export const dataApi = {
  getPrices: (ticker: string, period = '1y') =>
    api.get<PriceHistory[]>(`/stocks/${ticker}/prices`, { params: { period } }),
  getFinancials: (ticker: string, statementType = 'income', periodType = 'quarterly') =>
    api.get<FinancialStatement[]>(`/stocks/${ticker}/financials`, {
      params: { statement_type: statementType, period_type: periodType },
    }),
  getNews: (ticker: string, limit = 50) =>
    api.get<NewsArticle[]>(`/stocks/${ticker}/news`, { params: { limit } }),
  getEarnings: (ticker: string) => api.get<EarningsData>(`/stocks/${ticker}/earnings`),
  sync: (ticker: string) => api.post<SyncResponse>(`/stocks/${ticker}/sync`),
  syncAll: () => api.post('/stocks/sync/all'),
  getMetrics: (ticker: string) => api.get<Metrics>(`/stocks/${ticker}/metrics`),
}

export const analysisApi = {
  get: (ticker: string) => api.get<StockAnalysis | null>(`/stocks/${ticker}/analysis`),
  trigger: (ticker: string) => api.post<StockAnalysis>(`/stocks/${ticker}/analyze`),
  triggerAll: () => api.post('/stocks/analyze/all'),
}

export const watchlistsApi = {
  list: () => api.get<{ watchlists: Watchlist[]; total: number }>('/watchlists'),
  get: (id: number) => api.get<WatchlistDetail>(`/watchlists/${id}`),
  create: (name: string, description?: string) =>
    api.post<Watchlist>('/watchlists', { name, description }),
  update: (id: number, data: { name?: string; description?: string }) =>
    api.put<Watchlist>(`/watchlists/${id}`, data),
  delete: (id: number) => api.delete(`/watchlists/${id}`),
  addStock: (id: number, ticker: string) =>
    api.post<Stock>(`/watchlists/${id}/stocks`, { ticker }),
  removeStock: (id: number, ticker: string) =>
    api.delete(`/watchlists/${id}/stocks/${ticker}`),
}

export default api
