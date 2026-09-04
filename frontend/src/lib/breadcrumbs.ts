// specs/037-stocks-conviction-and-activity US4 (FR-023-FR-026; research R8).
// Pure: trailFor(pathname, hash) -> Crumb[], derived entirely from the
// current location — never from navigation history — so a deep link (a
// stock sub-tab URL pasted into a fresh tab) renders the identical trail an
// in-app navigation would have produced (FR-026).
export interface Crumb {
  label: string;
  to: string | null; // null = current page, not a link (FR-024/FR-025)
}

// Mirrors StockDetail.tsx's TABS list. "charts" is the default tab (no hash,
// or an unrecognized hash) and deliberately gets no third crumb segment —
// "Stocks / AVB" is already a "you are on AVB's default view" statement.
const STOCK_TAB_LABEL: Record<string, string> = {
  overview: "Overview",
  technicals: "Technicals",
  fundamentals: "Fundamentals",
  insider: "Insider",
  institutional: "Institutional",
  news: "News",
  sentiment: "Sentiment",
  "ai-summary": "AI Summary",
};

// Top-level pages that carry just their own name — mirrors App.tsx's route
// table. "/" (Stocks) and "/stock/:ticker" and "/sectors/:sector?" are
// handled separately below since they need more than a flat label.
const TOP_LEVEL_LABEL: Record<string, string> = {
  "/news": "News",
  "/macro": "Macro",
  "/watchlist": "Watchlist",
  "/earnings": "Earnings",
  "/institutional-flow": "Institutional Flow",
  "/congress": "Congress",
  "/chat": "Chat",
};

export function trailFor(pathname: string, hash: string = ""): Crumb[] {
  const cleanHash = hash.replace(/^#/, "");

  if (pathname === "/") {
    return [{ label: "Stocks", to: null }];
  }

  const stockMatch = pathname.match(/^\/stock\/([^/]+)\/?$/);
  if (stockMatch) {
    const ticker = decodeURIComponent(stockMatch[1]).toUpperCase();
    const tabLabel = STOCK_TAB_LABEL[cleanHash];
    if (tabLabel) {
      return [
        { label: "Stocks", to: "/" },
        { label: ticker, to: `/stock/${ticker}` },
        { label: tabLabel, to: null },
      ];
    }
    return [
      { label: "Stocks", to: "/" },
      { label: ticker, to: null },
    ];
  }

  const sectorsMatch = pathname.match(/^\/sectors(?:\/([^/]+))?\/?$/);
  if (sectorsMatch) {
    const sector = sectorsMatch[1] ? decodeURIComponent(sectorsMatch[1]) : null;
    if (sector) {
      return [
        { label: "Sectors", to: "/sectors" },
        { label: sector, to: null },
      ];
    }
    return [{ label: "Sectors", to: null }];
  }

  const topLevel = TOP_LEVEL_LABEL[pathname];
  if (topLevel) {
    return [{ label: topLevel, to: null }];
  }

  return [{ label: "Not Found", to: null }];
}
