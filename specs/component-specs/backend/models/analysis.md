# api/models/analysis.py

## Purpose
Pydantic models for analysis data — what comes out of MongoDB (from the agent pipeline) and what the API returns to the frontend.

## Models

### `SubReports`
```python
from pydantic import BaseModel
from typing import Any

class SubReports(BaseModel):
    technical: dict[str, Any] | None = None
    fundamental: dict[str, Any] | None = None
    macro: dict[str, Any] | None = None
    insider: dict[str, Any] | None = None
    institutional: dict[str, Any] | None = None
    sentiment: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None
```

### `PositionManagement`
```python
class PositionManagement(BaseModel):
    stair_step_stops: list[float]
    trailing_stop_recommendation: str
    position_sizing: str
```

### `Analysis` (full document)
```python
from datetime import datetime
from typing import Literal

class Analysis(BaseModel):
    ticker: str
    timestamp: datetime
    signal: Literal["bullish", "bearish", "neutral"]
    conviction: Literal["high", "medium", "low"]
    summary: str
    key_trends: list[str]
    flags: list[str]
    position_management: PositionManagement | None = None
    sub_reports: SubReports | None = None
```

### `AnalysisFeedItem` (lightweight, for the feed list)
```python
class AnalysisFeedItem(BaseModel):
    ticker: str
    timestamp: datetime
    signal: Literal["bullish", "bearish", "neutral"]
    conviction: Literal["high", "medium", "low"]
    summary: str  # one paragraph
    sector: str | None = None
    # sub_reports intentionally excluded — too large for feed
```

### `AnalysisFeedResponse`
```python
class AnalysisFeedResponse(BaseModel):
    items: list[AnalysisFeedItem]
    total: int
    page: int
    page_size: int
```
