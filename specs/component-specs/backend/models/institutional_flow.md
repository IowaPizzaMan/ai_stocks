# api/models/institutional_flow.py

## Purpose
Pydantic models for market-wide institutional flow events — the output of `InstitutionalFlowScannerAgent` (`institutional_flow_scanner.md`), stored in the `institutional_flow` collection. Distinct from `models/analysis.md`'s `SubReports.institutional`, which is a per-ticker sub-report embedded in a full stock analysis.

## Models

### `InstitutionalFlowEvent` (one document per move)
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Literal

class InstitutionalFlowEvent(BaseModel):
    ticker: str
    fund: str
    action: Literal["new_position", "add", "trim", "exit"]
    shares: int | None = None
    value_usd: float | None = None
    pct_of_portfolio: float | None = None
    headline: str
    notability_score: int  # 0-100, higher = more likely a high-conviction signal
    source: Literal["13F", "dataroma"]
    filed_at: datetime
    scanned_at: datetime
```

### `InstitutionalFlowResponse`
```python
class InstitutionalFlowResponse(BaseModel):
    items: list[InstitutionalFlowEvent]
    total: int
    page: int
    page_size: int
```

### `InstitutionalScanResult`
Returned by `POST /institutional/scan` (manual trigger, mirrors the `/queue/all` "Pull All" pattern).
```python
class InstitutionalScanResult(BaseModel):
    status: Literal["queued"]
    message: str
```
