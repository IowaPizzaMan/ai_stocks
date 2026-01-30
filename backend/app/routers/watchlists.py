from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Watchlist, WatchedStock, watchlist_stocks
from ..schemas import (
    WatchlistCreate,
    WatchlistUpdate,
    WatchlistResponse,
    WatchlistDetailResponse,
    WatchlistListResponse,
    AddStockToWatchlistRequest,
    StockResponse,
)
from ..services import YahooFinanceService

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])


@router.get("", response_model=WatchlistListResponse)
def list_watchlists(db: Session = Depends(get_db)):
    """List all active watchlists with stock counts."""
    watchlists = db.query(Watchlist).filter(Watchlist.is_active == True).all()

    result = []
    for wl in watchlists:
        stock_count = len([s for s in wl.stocks if s.is_active])
        result.append(WatchlistResponse(
            id=wl.id,
            name=wl.name,
            description=wl.description,
            is_default=wl.is_default,
            is_active=wl.is_active,
            created_at=wl.created_at,
            updated_at=wl.updated_at,
            stock_count=stock_count,
        ))

    return WatchlistListResponse(watchlists=result, total=len(result))


@router.post("", response_model=WatchlistResponse)
def create_watchlist(watchlist_data: WatchlistCreate, db: Session = Depends(get_db)):
    """Create a new watchlist."""
    watchlist = Watchlist(
        name=watchlist_data.name,
        description=watchlist_data.description,
        is_default=False,
    )
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)

    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        description=watchlist.description,
        is_default=watchlist.is_default,
        is_active=watchlist.is_active,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        stock_count=0,
    )


@router.get("/{watchlist_id}", response_model=WatchlistDetailResponse)
def get_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    """Get a specific watchlist with its stocks."""
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.is_active == True
    ).first()

    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    active_stocks = [s for s in watchlist.stocks if s.is_active]

    return WatchlistDetailResponse(
        id=watchlist.id,
        name=watchlist.name,
        description=watchlist.description,
        is_default=watchlist.is_default,
        is_active=watchlist.is_active,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        stocks=[StockResponse.model_validate(s) for s in active_stocks],
    )


@router.put("/{watchlist_id}", response_model=WatchlistResponse)
def update_watchlist(watchlist_id: int, update_data: WatchlistUpdate, db: Session = Depends(get_db)):
    """Update a watchlist's name or description."""
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.is_active == True
    ).first()

    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    if update_data.name is not None:
        watchlist.name = update_data.name
    if update_data.description is not None:
        watchlist.description = update_data.description

    db.commit()
    db.refresh(watchlist)

    stock_count = len([s for s in watchlist.stocks if s.is_active])

    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        description=watchlist.description,
        is_default=watchlist.is_default,
        is_active=watchlist.is_active,
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
        stock_count=stock_count,
    )


@router.delete("/{watchlist_id}")
def delete_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    """Soft-delete a watchlist (cannot delete the default watchlist)."""
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.is_active == True
    ).first()

    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    if watchlist.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default watchlist")

    watchlist.is_active = False
    db.commit()

    return {"message": f"Watchlist '{watchlist.name}' deleted"}


@router.post("/{watchlist_id}/stocks", response_model=StockResponse)
def add_stock_to_watchlist(
    watchlist_id: int,
    request: AddStockToWatchlistRequest,
    db: Session = Depends(get_db)
):
    """Add a stock to a watchlist. Creates the stock if it doesn't exist."""
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.is_active == True
    ).first()

    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    ticker = request.ticker.upper()

    # Check if stock exists
    stock = db.query(WatchedStock).filter(WatchedStock.ticker == ticker).first()

    if not stock:
        # Create new stock
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
        db.commit()
        db.refresh(stock)
    elif not stock.is_active:
        # Reactivate inactive stock
        stock.is_active = True
        db.commit()
        db.refresh(stock)

    # Check if stock is already in this watchlist
    if stock in watchlist.stocks:
        raise HTTPException(status_code=400, detail=f"Stock {ticker} is already in this watchlist")

    # Add stock to watchlist
    watchlist.stocks.append(stock)
    db.commit()

    return stock


@router.delete("/{watchlist_id}/stocks/{ticker}")
def remove_stock_from_watchlist(watchlist_id: int, ticker: str, db: Session = Depends(get_db)):
    """Remove a stock from a watchlist."""
    watchlist = db.query(Watchlist).filter(
        Watchlist.id == watchlist_id,
        Watchlist.is_active == True
    ).first()

    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    stock = db.query(WatchedStock).filter(WatchedStock.ticker == ticker.upper()).first()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

    if stock not in watchlist.stocks:
        raise HTTPException(status_code=400, detail=f"Stock {ticker} is not in this watchlist")

    watchlist.stocks.remove(stock)
    db.commit()

    return {"message": f"Stock {ticker} removed from watchlist"}
