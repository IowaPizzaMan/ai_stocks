# api/routers/macro.md

## Purpose
Exposes cached macro economic data (from FRED, stored in MongoDB by the agent pipeline) to the frontend. Powers any macro context displayed in the UI.

## Endpoints

### `GET /macro`
Returns the latest cached macro data for all default indicators.

```python
@router.get("/macro")
def get_macro(db = Depends(db_dependency)):
    cached = db.macro_cache.find_one({}, { "_id": 0 }, sort=[("fetched_at", -1)])
    if not cached:
        raise HTTPException(status_code=404, detail="No macro data cached yet. Run analysis first.")
    return cached
```

### `GET /macro/{series_id}`
Returns history for a specific FRED series.

```python
@router.get("/macro/{series_id}")
def get_macro_series(series_id: str, db = Depends(db_dependency)):
    cached = db.macro_cache.find_one({}, { "_id": 0 }, sort=[("fetched_at", -1)])
    data = cached.get("data", {}) if cached else {}
    if series_id not in data:
        raise HTTPException(status_code=404, detail=f"Series {series_id} not in cache.")
    return { "series_id": series_id, "observations": data[series_id], "fetched_at": cached["fetched_at"] }
```
