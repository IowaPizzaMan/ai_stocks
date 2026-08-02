# api/models/watchlist.md

## Purpose
Pydantic models for the user's watchlist.

## Models

### `WatchlistItem`
```python
class WatchlistItem(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    added_at: datetime
    status: Literal["active", "removed_from_market"] = "active"
    delisted_at: datetime | None = None
    last_signal: Literal["bullish", "bearish", "neutral"] | None = None
    last_conviction: Literal["high", "medium", "low"] | None = None
    last_analyzed: datetime | None = None
```

### `WatchlistResponse`
```python
class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]
    count: int
```

### `AddToWatchlistRequest`
```python
class AddToWatchlistRequest(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
```
