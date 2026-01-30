from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import WatchedStock, Watchlist
from ..schemas import StockCreate, StockResponse, StockListResponse
from ..services import YahooFinanceService

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("", response_model=StockListResponse)
def list_stocks(
    watchlist_id: Optional[int] = Query(None, description="Filter by watchlist ID"),
    db: Session = Depends(get_db)
):
    """List all watched stocks, optionally filtered by watchlist."""
    if watchlist_id is not None:
        watchlist = db.query(Watchlist).filter(
            Watchlist.id == watchlist_id,
            Watchlist.is_active == True
        ).first()
        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        stocks = [s for s in watchlist.stocks if s.is_active]
    else:
        stocks = db.query(WatchedStock).filter(WatchedStock.is_active == True).all()
    return StockListResponse(stocks=stocks, total=len(stocks))


@router.post("", response_model=StockResponse)
def add_stock(
    stock_data: StockCreate,
    watchlist_id: Optional[int] = Query(None, description="Add stock to this watchlist (defaults to default watchlist)"),
    db: Session = Depends(get_db)
):
    """Add a stock to a watchlist. Defaults to the default watchlist."""
    ticker = stock_data.ticker.upper()

    # Determine which watchlist to add to
    if watchlist_id is not None:
        watchlist = db.query(Watchlist).filter(
            Watchlist.id == watchlist_id,
            Watchlist.is_active == True
        ).first()
        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")
    else:
        # Use default watchlist
        watchlist = db.query(Watchlist).filter(Watchlist.is_default == True).first()
        if not watchlist:
            raise HTTPException(status_code=500, detail="No default watchlist found")

    existing = db.query(WatchedStock).filter(WatchedStock.ticker == ticker).first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
            db.refresh(existing)

        # Check if already in this watchlist
        if existing in watchlist.stocks:
            raise HTTPException(status_code=400, detail=f"Stock {ticker} is already in this watchlist")

        # Add to watchlist
        watchlist.stocks.append(existing)
        db.commit()
        return existing

    yf_service = YahooFinanceService(db)
    try:
        info = yf_service.get_stock_info(ticker)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Could not find stock {ticker}")

    stock = WatchedStock(
        ticker=ticker,
        company_name=info.get("company_name"),
        sector=info.get("sector"),
        industry=info.get("industry"),
    )
    db.add(stock)
    db.flush()  # Get the ID without committing

    # Add to watchlist
    watchlist.stocks.append(stock)
    db.commit()
    db.refresh(stock)
    return stock


@router.get("/{ticker}", response_model=StockResponse)
def get_stock(ticker: str, db: Session = Depends(get_db)):
    """Get a specific stock's details."""
    stock = db.query(WatchedStock).filter(
        WatchedStock.ticker == ticker.upper(),
        WatchedStock.is_active == True
    ).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")
    return stock


@router.delete("/{ticker}")
def remove_stock(ticker: str, db: Session = Depends(get_db)):
    """Remove a stock from the watchlist (soft delete)."""
    stock = db.query(WatchedStock).filter(
        WatchedStock.ticker == ticker.upper()
    ).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

    stock.is_active = False
    db.commit()
    return {"message": f"Stock {ticker} removed from watchlist"}
