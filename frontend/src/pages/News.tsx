// Spec: specs/029-company-profile-tweaks (US1) — market news promoted from a
// tab nested inside the Stocks page to its own top-level nav destination.
// specs/035-chat-and-news-upgrade US2 — MarketNewsPanel (stock-latest only)
// superseded by NewsFeed, the mixed general/stock/FMP-article stream.
import { useEffect } from "react";
import NewsFeed from "../components/feed/NewsFeed";

export default function News() {
  useEffect(() => {
    document.title = "StockAI — News";
  }, []);

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="sr-only">News</h1>
      <NewsFeed />
    </div>
  );
}
