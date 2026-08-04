# Ideas

Rough notes for future spec work. Not yet integrated into `specs/`.

## Data Sources

- **Switch price data to FMP.** Yahoo doesn't cover all the tickers I want. Need to research what else the $20/mo FMP subscription includes beyond price data.
- **Company logos.** Investigate whether company images/logos can be pulled from an API.
- **Company website scraping.** Get each company's website URL from an API, then scan the site with Playwright.

## Feed Filters & Search

- **Ticker search.** Add a search box for a specific ticker; results should filter as I type (no submit needed).
- **Trading-strategy filters**, e.g.:
  - Institutions buying / institutions selling
  - Positive on year / negative on year
  - "Earning Money" (quality company)
  - "Stonk" (high beta)
- **Additional feed flags:**
  - Recent institutional buying/selling activity
  - Recent insider transactions, summarized over the last month (e.g. "10 buys, 2 sells")
  - Flags for my other strategies (TBD which)
  - Sector

## Sectors Tab

- Add sector data so the feed can be filtered by sector and the sectors tab can group by it.
- Show a single chart summarizing all sectors, with strategy analysis per sector.
- Clicking a sector should jump to the feed screen pre-filtered to that sector.

## Bugs to Investigate

- The 1M chart looks wrong — the weekly-change and monthly-change values appear swapped.
