# AI Stock Analysis

A comprehensive stock analysis platform that fetches stock data via yfinance, stores it with delta tracking, runs AI analysis via HuggingFace models and Ollama, and displays insights through a web UI.

## Features

- **Stock Watchlist Management**: Add/remove stocks to track
- **Price History**: Interactive charts with multiple time ranges (1W, 1M, 3M, 1Y, 5Y, Max)
- **Financial Metrics**: QoQ revenue, margins, EPS, and cash flow charts
- **News with Sentiment**: Recent news articles with AI-powered sentiment analysis
- **AI Analysis**: Bull/bear cases generated using local LLM (Ollama)
- **Delta Tracking**: Only fetches new data since last sync

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | FastAPI (Python) |
| Database | PostgreSQL + SQLAlchemy |
| Migrations | Alembic |
| Data Source | yfinance |
| Sentiment Model | FinancialBERT (HuggingFace) |
| LLM (for cases) | Ollama (Mistral) |
| Frontend | React + TypeScript + Vite |
| Charts | Recharts |
| Styling | Tailwind CSS |

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+
- Ollama (optional, for AI analysis)

## Quick Start

### 1. Clone and Setup

```bash
cd ai-stock
cp .env.example .env
```

### 2. Start PostgreSQL

Using Docker:
```bash
docker run -d --name aistock-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=aistock \
  -p 5432:5432 \
  postgres:15-alpine
```

### 3. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

Backend runs at http://localhost:8000

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173

### 5. AI Models Service (Optional)

For sentiment analysis with HuggingFace models:

```bash
cd ai_models
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8001 --reload
```

### 6. Ollama Setup (Optional)

For AI-generated bull/bear cases:

```bash
# Install Ollama from https://ollama.ai
ollama pull mistral
ollama serve
```

## Docker Compose

Run everything with Docker:

```bash
docker-compose up -d
```

Services:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- AI Models: http://localhost:8001
- PostgreSQL: localhost:5432

## API Endpoints

### Stock Management
- `GET /api/stocks` - List all watched stocks
- `POST /api/stocks` - Add stock to watchlist
- `DELETE /api/stocks/{ticker}` - Remove stock
- `GET /api/stocks/{ticker}` - Get stock details

### Data Retrieval
- `GET /api/stocks/{ticker}/prices` - Get price history
- `GET /api/stocks/{ticker}/financials` - Get financial statements
- `GET /api/stocks/{ticker}/news` - Get news articles
- `POST /api/stocks/{ticker}/sync` - Sync data (delta fetch)
- `GET /api/stocks/{ticker}/metrics` - Get calculated metrics

### Analysis
- `GET /api/stocks/{ticker}/analysis` - Get latest AI analysis
- `POST /api/stocks/{ticker}/analyze` - Generate new analysis

### Bulk Operations
- `POST /api/sync/all` - Sync all watched stocks
- `POST /api/analyze/all` - Analyze all stocks

## Project Structure

```
ai-stock/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Configuration
│   │   ├── database.py          # Database connection
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API endpoints
│   │   ├── services/            # Business logic
│   │   └── utils/               # Utilities
│   ├── alembic/                 # Database migrations
│   └── requirements.txt
│
├── ai_models/
│   ├── main.py                  # AI service
│   ├── models/                  # ML models
│   ├── services/                # Analysis services
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/          # React components
│   │   ├── pages/               # Page components
│   │   └── services/            # API client
│   └── package.json
│
├── docker-compose.yml
└── README.md
```

## Usage

1. **Add Stocks**: Go to Watchlist page and enter ticker symbols (e.g., AAPL, MSFT)
2. **Sync Data**: Click "Sync" to fetch price history, financials, and news
3. **View Charts**: Click on a stock to see price and financial charts
4. **Generate Analysis**: Click "Generate Analysis" to create AI bull/bear cases

## Development

### Run Tests
```bash
cd backend
pytest
```

### Database Migrations
```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## License

MIT
