# frontend/src/components/stock/InsiderTab.tsx

## Purpose
Displays insider trading activity — Form 4 transactions, cluster signals, and MSPR trend.

## Sections

### 1. Cluster Signal Banner
If a cluster was detected: prominent green banner with details ("3 insiders bought $2.1M in January")
If no cluster: subtle neutral note

### 2. Insider Transaction Timeline
- Recharts `ScatterChart` overlaid on a simple price line
- Green dots = purchases, red dots = sales
- Dot size proportional to transaction value
- Tooltip shows: name, title, shares, value, date, type

### 3. Buy/Sell Ratio Donut
`PieChart` (Recharts) — last 90 days:
- Green slice: $ value of open-market purchases
- Red slice: $ value of sales
- Center label: "Net Buyer" or "Net Seller"

### 4. MSPR Trend Chart
Line chart of monthly MSPR (-100 to +100) over last 12 months
- Reference line at 0
- Above 0 = net positive insider sentiment, below = net negative

### 5. Transaction Table
Scrollable table: Date | Name | Title | Type | Shares | Value
- Type column: colored badge (Purchase = green, Sale = red, Option Exercise = slate)
- Sorted by date descending

## Dependencies
- `recharts`
- Insider sub-report from `useStockSignals`
