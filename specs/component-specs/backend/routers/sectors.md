# api/routers/sectors.md

## Purpose
Sector-level summary data — aggregates analysis results across all tickers in a sector. Powers the sector heatmap view.

## Endpoints

### `GET /sectors`
List all sectors with a signal summary.

```python
@router.get("/sectors")
def get_sectors(db = Depends(db_dependency)):
    pipeline = [
        # Get most recent analysis per ticker
        { "$sort": { "timestamp": -1 } },
        { "$group": { "_id": "$ticker", "doc": { "$first": "$$ROOT" } } },
        { "$replaceRoot": { "newRoot": "$doc" } },
        # Group by sector
        { "$group": {
            "_id": "$sector",
            "bullish_count": { "$sum": { "$cond": [{ "$eq": ["$signal", "bullish"] }, 1, 0] } },
            "bearish_count": { "$sum": { "$cond": [{ "$eq": ["$signal", "bearish"] }, 1, 0] } },
            "neutral_count": { "$sum": { "$cond": [{ "$eq": ["$signal", "neutral"] }, 1, 0] } },
            "ticker_count": { "$sum": 1 }
        }},
        { "$project": {
            "sector": "$_id", "_id": 0,
            "bullish_count": 1, "bearish_count": 1, "neutral_count": 1, "ticker_count": 1
        }}
    ]
    return list(db.analyses.aggregate(pipeline))
```

### `GET /sectors/{sector}`
All tickers in a sector with their latest signal — used for the sector detail heatmap.

Delegates to `GET /analysis/sector/{sector}` (see analysis.py router). This endpoint is an alias kept here for semantic clarity in the URL structure.
