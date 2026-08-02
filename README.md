# StockAI

Local-first, single-user stock research app. CrewAI agents + a local Ollama LLM analyze tickers from a work queue and write results to MongoDB; FastAPI serves them to a React UI.

- **Specs:** [specs/SPEC.md](specs/SPEC.md) (product + architecture), [specs/component-specs/](specs/component-specs/) (per-file specs)
- **Stack & build plan:** [project-proposal.md](project-proposal.md)

## Layout

```
backend/       FastAPI service (REST layer over MongoDB)          :8000
agent-runner/  CrewAI queue worker + tools + skills + chunker
frontend/      React + Vite + TypeScript + Tailwind UI            :5173
scripts/       One-off utilities (run outside Docker)
specs/         Source-of-truth specifications
```

## Running

```sh
cp .env.example .env       # fill in API keys (FMP, Finnhub, FRED)

# Dev machine (no GPU):
docker compose up -d --build

# GPU server:
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build

# First run: pull the model into the ollama container
docker compose exec ollama ollama pull qwen2.5:14b
```

- UI: http://localhost:5173
- API docs: http://localhost:8000/docs
- Mongo: mongodb://localhost:27017 (db `stockai`)

## Dev outside Docker

```sh
# backend
cd backend && pip install -r requirements.txt && uvicorn main:app --reload

# agent-runner
cd agent-runner && pip install -r requirements.txt && python main.py

# frontend
cd frontend && npm install && npm run dev
```

`.env` defaults point at localhost; docker-compose overrides hostnames in-network.
