// Spec: specs/029-company-profile-tweaks (US1) — market news promoted from a
// tab nested inside the Stocks page to its own top-level nav destination.
// MarketNewsPanel is reused unchanged (research R9): it already owns its
// loading/error/empty states and the 20-article, no-infinite-scroll contract
// (spec 022), so this page is a thin wrapper that guarantees FR-002's
// "same content and behavior" by construction.
import { useEffect } from "react";
import MarketNewsPanel from "../components/feed/MarketNewsPanel";

export default function News() {
  useEffect(() => {
    document.title = "StockAI — News";
  }, []);

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="sr-only">Market News</h1>
      <MarketNewsPanel />
    </div>
  );
}
