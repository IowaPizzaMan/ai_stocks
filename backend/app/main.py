from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import stocks_router, data_router, analysis_router, watchlists_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Stock Analysis API",
    description="Backend API for stock analysis with yfinance data and AI insights",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stocks_router)
app.include_router(data_router)
app.include_router(analysis_router)
app.include_router(watchlists_router)


@app.get("/")
def root():
    return {"message": "AI Stock Analysis API", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
