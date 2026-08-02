"""FastAPI entry point. Spec: specs/SPEC.md 'Backend: FastAPI'."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import ensure_indexes, get_db
from routers import (
    analysis,
    earnings,
    institutional_flow,
    macro,
    queue,
    sectors,
    stocks,
    watchlist,
)


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

app.include_router(analysis.router)
app.include_router(stocks.router)
app.include_router(macro.router)
app.include_router(watchlist.router)
app.include_router(sectors.router)
app.include_router(queue.router)
app.include_router(earnings.router)
app.include_router(institutional_flow.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
