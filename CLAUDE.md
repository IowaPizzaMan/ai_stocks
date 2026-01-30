# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Stock Analysis is a full-stack application for tracking stocks, fetching financial data via yfinance, running AI analysis (sentiment via HuggingFace, bull/bear cases via Ollama), and displaying insights through a React web UI.

## Common Commands

### Backend (Python/FastAPI)
```bash
cd backend
source venv/bin/activate       # Linux/Mac
venv\Scripts\activate          # Windows

# Run server
uvicorn app.main:app --reload

# Database migrations
alembic upgrade head                              # Apply migrations
alembic revision --autogenerate -m "description"  # Create new migration

# Tests
pytest
```

### Frontend (React/TypeScript/Vite)
```bash
cd frontend
npm install
npm run dev      # Development server
npm run build    # Production build (runs tsc then vite build)
npm run lint     # ESLint check
```

### Docker (Full Stack)
```bash
docker-compose up -d           # Start all services
docker-compose logs -f         # View logs
docker-compose down            # Stop services

# Or use the helper script:
./start.sh docker              # Docker mode (default)
./start.sh dev                 # Local development mode
```

### AI Models Service (Optional)
```bash
cd ai_models
uvicorn main:app --port 8001 --reload
```

## Architecture

### Three-Service Architecture
1. **Backend (FastAPI, port 8000)**: REST API, PostgreSQL via SQLAlchemy, data sync with yfinance
2. **Frontend (React/Vite, port 5173)**: SPA with Recharts for visualization, proxies `/api` to backend
3. **AI Models (FastAPI, port 8001, optional)**: Sentiment analysis (FinancialBERT) and case generation (Ollama/Mistral)

### Backend Structure (`backend/app/`)
- `main.py` - FastAPI app entry point with CORS and router registration
- `config.py` - Pydantic settings loading from `.env`
- `database.py` - SQLAlchemy engine and session management
- `models/` - SQLAlchemy ORM models: `WatchedStock`, `PriceHistory`, `FinancialStatement`, `NewsArticle`, `StockAnalysis`, `SyncMetadata`, `EarningsData`
- `schemas/` - Pydantic request/response schemas
- `routers/` - API endpoints split by domain: `stocks.py` (CRUD), `data.py` (sync/prices/financials), `analysis.py` (AI analysis)
- `services/yahoo_finance.py` - yfinance data fetching with delta tracking (only fetches new data since last sync)
- `utils/delta_tracker.py` - Tracks last sync timestamps to avoid re-fetching unchanged data

### Frontend Structure (`frontend/src/`)
- `App.tsx` - React Router setup with nav (Dashboard, Watchlist, StockDetail routes)
- `services/api.ts` - Axios client with typed API wrappers for stocks, data, and analysis endpoints
- `pages/` - Dashboard, Watchlist, StockDetail page components
- `components/` - PriceChart, FinancialsChart, NewsPanel, AnalysisPanel, EarningsPanel, StockWatchlist

### Data Flow
1. User adds stock to watchlist -> `POST /api/stocks`
2. Sync fetches data from yfinance -> `POST /api/stocks/{ticker}/sync`
3. Delta tracker ensures only new data is fetched
4. Optional AI analysis via ai_models service -> `POST /api/stocks/{ticker}/analyze`

## Key Configuration

Environment variables (`.env`):
- `DATABASE_URL` - PostgreSQL connection string (uses psycopg3: `postgresql+psycopg://...`)
- `AI_MODELS_ENABLED` - Set `true` to enable AI analysis features
- `AI_MODELS_URL` / `OLLAMA_URL` - Service endpoints for AI features

## Database

PostgreSQL 15+ required. Uses Alembic for migrations.

Connection URL format: `postgresql+psycopg://user:pass@host:5432/dbname`

Tables: `watched_stocks`, `price_history`, `financial_statements`, `news_articles`, `stock_analyses`, `sync_metadata`, `earnings_data`
