"""FastAPI entry point. Spec: specs/SPEC.md 'Backend: FastAPI'."""
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import llm
from db import ensure_indexes, get_db
from logging_config import get_logger
from routers import (
    analysis,
    chat,
    congress,
    earnings,
    events,
    institutional_flow,
    logs,
    macro,
    market,
    news,
    price,
    queue,
    sectors,
    stocks,
    watchlist,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_indexes(get_db())
    # Fire-and-forget: a slow/unreachable Ollama must never delay backend
    # startup (research.md R2 — pre-warm is an optimization, not a
    # dependency; the model loads lazily on the first real question if this
    # doesn't complete in time).
    threading.Thread(target=llm.prewarm, daemon=True).start()
    yield


app = FastAPI(title="StockAI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def log_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Spec: specs/SPEC.md 'Exception Handling & Logging'. Without this,
    Starlette's default handler surfaces a bare 500 with nothing recorded."""
    logger.exception("unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


app.include_router(analysis.router)
app.include_router(chat.router)
app.include_router(price.router)
app.include_router(stocks.router)
app.include_router(macro.router)
app.include_router(market.router)
app.include_router(watchlist.router)
app.include_router(sectors.router)
app.include_router(queue.router)
app.include_router(earnings.router)
app.include_router(institutional_flow.router)
app.include_router(logs.router)
app.include_router(congress.router)
app.include_router(news.router)
app.include_router(events.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
