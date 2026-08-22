"""FastAPI entry point. Spec: specs/SPEC.md 'Backend: FastAPI'."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import ensure_indexes, get_db
from logging_config import get_logger
from routers import (
    analysis,
    earnings,
    institutional_flow,
    logs,
    macro,
    market,
    portfolio,
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
app.include_router(portfolio.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
