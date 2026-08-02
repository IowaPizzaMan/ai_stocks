# frontend/src/components/stock/InstitutionalTab.tsx

## Purpose
Shows institutional 13F ownership changes and superinvestor activity.

## Sections

### 1. Ownership % Over Time
- Line chart: total institutional ownership % by quarter (last 8 quarters)
- Reference annotation for any notable changes

### 2. Superinvestor Overlap
- Count badge: "7 superinvestors hold this stock"
- Card list of superinvestors holding it — fund name, approximate % of portfolio, last action (add/hold/trim)

### 3. New Positions / Exits
Two columns:
- **New Positions**: funds that entered this quarter (green highlight)
- **Exits**: funds that fully exited this quarter (red highlight)

### 4. Top Institutional Holders Table
| Fund | Shares | Value | % Outstanding | QoQ Change |
With QoQ change colored green (increase) / red (decrease) / neutral

### 5. Link to Full Market Flow
Footer link: "See all institutional activity for AAPL →" navigates to `/institutional-flow?ticker=AAPL`, landing on the market-wide Institutional Flow page pre-filtered to this ticker (see `pages/InstitutionalFlow.md`). Lets the user cross from a per-stock snapshot into the live feed of raw filing events behind it.

## Dependencies
- `recharts`
- Institutional sub-report from `useStockSignals`
- `react-router-dom` (Link to `/institutional-flow`)
