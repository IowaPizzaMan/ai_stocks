# yfinance Data Reference

A comprehensive guide to all data available through the yfinance Python package.

---

## Currently Used in This Application

| Property/Method | Description | Used In |
|----------------|-------------|---------|
| `ticker.history()` | Price OHLCV data | `sync_prices()` |
| `ticker.info` | Company info (name, sector, industry, ratios) | `get_stock_info()`, `get_valuation_metrics()` |
| `ticker.news` | News articles | `sync_news()` |
| `ticker.income_stmt` | Annual income statements | `sync_financials()` |
| `ticker.quarterly_income_stmt` | Quarterly income statements | `sync_financials()` |
| `ticker.balance_sheet` | Annual balance sheets | `sync_financials()` |
| `ticker.quarterly_balance_sheet` | Quarterly balance sheets | `sync_financials()` |
| `ticker.cashflow` | Annual cash flow statements | `sync_financials()` |
| `ticker.quarterly_cashflow` | Quarterly cash flow statements | `sync_financials()` |

---

## Available Data (Not Yet Implemented)

### Analyst & Recommendations

| Property/Method | Description | Returns |
|----------------|-------------|---------|
| `ticker.recommendations` | Buy/hold/sell ratings history | DataFrame with dates and ratings |
| `ticker.recommendations_summary` | Aggregated recommendation counts | DataFrame (strongBuy, buy, hold, sell, strongSell) |
| `ticker.upgrades_downgrades` | Recent analyst changes | DataFrame with firm, grade changes |
| `ticker.analyst_price_targets` | Target prices | Dict with low, mean, median, high, current |

### Earnings & Estimates

| Property/Method | Description | Returns |
|----------------|-------------|---------|
| `ticker.earnings` | Annual revenue and earnings | DataFrame by year |
| `ticker.quarterly_earnings` | Quarterly earnings | DataFrame by quarter |
| `ticker.earnings_dates` | Past and upcoming earnings dates | DataFrame with EPS estimates/actuals |
| `ticker.earnings_estimate` | EPS estimates | DataFrame (current qtr, next qtr, current yr, next yr) |
| `ticker.revenue_estimate` | Revenue estimates | DataFrame with avg, low, high, growth |
| `ticker.earnings_trend` | EPS trend analysis | DataFrame |
| `ticker.growth_estimates` | Growth projections | DataFrame (stock vs industry vs sector) |
| `ticker.eps_revisions` | EPS revision history | DataFrame |

### Ownership Data

| Property/Method | Description | Returns |
|----------------|-------------|---------|
| `ticker.major_holders` | % held by insiders/institutions | DataFrame |
| `ticker.institutional_holders` | Top institutional owners | DataFrame with holder, shares, date, % |
| `ticker.mutualfund_holders` | Mutual fund holdings | DataFrame with holder, shares, date, % |
| `ticker.insider_transactions` | Insider buying/selling | DataFrame with name, position, date, shares, value |
| `ticker.insider_purchases` | Insider purchase summary | DataFrame (last 6 months aggregated) |
| `ticker.insider_roster_holders` | List of insiders | DataFrame with names and positions |

### Dividends & Corporate Actions

| Property/Method | Description | Returns |
|----------------|-------------|---------|
| `ticker.dividends` | Dividend payment history | Series with dates and amounts |
| `ticker.splits` | Stock split history | Series with dates and ratios |
| `ticker.actions` | Combined dividends and splits | DataFrame |
| `ticker.capital_gains` | Capital gains distributions | Series |

### Options Data

| Property/Method | Description | Returns |
|----------------|-------------|---------|
| `ticker.options` | Available expiration dates | Tuple of date strings |
| `ticker.option_chain(date)` | Calls and puts for a date | OptionChain object with .calls and .puts DataFrames |

### Other Data

| Property/Method | Description | Returns |
|----------------|-------------|---------|
| `ticker.fast_info` | Quick metrics (faster than .info) | Dict-like with price, market cap, volume, etc. |
| `ticker.calendar` | Upcoming earnings/dividend dates | DataFrame |
| `ticker.sustainability` | ESG scores | DataFrame |
| `ticker.isin` | ISIN identifier | String |

---

## ticker.info Dictionary Keys

The `ticker.info` property returns a dictionary with many fields. Common keys include:


### Price & Trading
- `currentPrice` - Current stock price
- `previousClose` - Previous closing price
- `open` - Today's opening price
- `dayLow`, `dayHigh` - Today's range
- `fiftyTwoWeekLow`, `fiftyTwoWeekHigh` - 52-week range
- `volume` - Trading volume
- `averageVolume` - Average volume
- `averageVolume10days` - 10-day average volume
- `bid`, `ask` - Current bid/ask
- `bidSize`, `askSize` - Bid/ask sizes


### Company Information
- `longName` - Full company name
- `shortName` - Short company name
- `symbol` - Ticker symbol
- `sector` - Business sector
- `industry` - Specific industry
- `longBusinessSummary` - Company description
- `website` - Company website
- `fullTimeEmployees` - Employee count
- `country`, `city`, `state`, `zip` - Location

### Valuation Metrics
- `marketCap` - Market capitalization
- `enterpriseValue` - Enterprise value
- `trailingPE` - Trailing P/E ratio
- `forwardPE` - Forward P/E ratio
- `priceToSalesTrailing12Months` - P/S ratio
- `priceToBook` - P/B ratio
- `pegRatio` - PEG ratio
- `enterpriseToRevenue` - EV/Revenue
- `enterpriseToEbitda` - EV/EBITDA

### Financials
- `totalRevenue` - Total revenue
- `revenuePerShare` - Revenue per share
- `revenueGrowth` - Revenue growth rate
- `grossMargins` - Gross margin %
- `operatingMargins` - Operating margin %
- `profitMargins` - Net profit margin %
- `ebitda` - EBITDA
- `netIncomeToCommon` - Net income
- `earningsGrowth` - Earnings growth rate
- `trailingEps` - Trailing EPS
- `forwardEps` - Forward EPS

### Balance Sheet
- `totalCash` - Cash on hand
- `totalCashPerShare` - Cash per share
- `totalDebt` - Total debt
- `debtToEquity` - Debt/equity ratio
- `currentRatio` - Current ratio
- `quickRatio` - Quick ratio
- `bookValue` - Book value per share

### Returns & Efficiency
- `returnOnAssets` - ROA
- `returnOnEquity` - ROE

### Dividends
- `dividendRate` - Annual dividend rate
- `dividendYield` - Dividend yield
- `exDividendDate` - Ex-dividend date
- `payoutRatio` - Dividend payout ratio
- `fiveYearAvgDividendYield` - 5-year avg yield

### Analyst Data
- `targetHighPrice` - Highest price target
- `targetLowPrice` - Lowest price target
- `targetMeanPrice` - Mean price target
- `targetMedianPrice` - Median price target
- `recommendationMean` - Recommendation score (1-5)
- `recommendationKey` - Recommendation (buy/hold/sell)
- `numberOfAnalystOpinions` - Number of analysts

### Risk Metrics
- `beta` - Beta coefficient
- `52WeekChange` - 52-week price change
- `SandP52WeekChange` - S&P 500 52-week change

---

## ticker.history() Parameters

```python
ticker.history(
    period="1mo",        # Valid: 1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,ytd,max
    interval="1d",       # Valid: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
    start=None,          # Download start date string (YYYY-MM-DD) or datetime
    end=None,            # Download end date string (YYYY-MM-DD) or datetime
    prepost=False,       # Include pre and post market data
    auto_adjust=True,    # Adjust OHLC for splits
    back_adjust=False,   # Back-adjust data for splits
    repair=False,        # Repair bad data
    actions=True,        # Include dividends and splits
    rounding=False,      # Round values
)
```

Returns DataFrame with columns: Open, High, Low, Close, Volume, Dividends, Stock Splits

---

## yf.download() for Multiple Tickers

```python
import yfinance as yf

data = yf.download(
    tickers="AAPL MSFT GOOG",  # Space-separated or list
    period="1mo",
    interval="1d",
    group_by="ticker",         # 'ticker' or 'column'
    threads=True,              # Use threading
    progress=True,             # Show progress bar
)
```

---

## Sources

- [yfinance PyPI](https://pypi.org/project/yfinance/)
- [yfinance API Reference](https://ranaroussi.github.io/yfinance/reference/index.html)
- [yfinance Documentation](https://ranaroussi.github.io/yfinance/)
- [yfinance Python Tutorial - Analyzing Alpha](https://analyzingalpha.com/yfinance-python)
- [GitHub - ranaroussi/yfinance](https://github.com/ranaroussi/yfinance)
