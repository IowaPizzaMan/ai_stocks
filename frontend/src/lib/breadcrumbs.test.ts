import { expect, test } from "vitest";
import { trailFor } from "./breadcrumbs";

test("the Stocks page shows just its own name, no link, no trailing separator", () => {
  expect(trailFor("/")).toEqual([{ label: "Stocks", to: null }]);
});

test("a stock detail page (default tab, no hash) shows Stocks / TICKER", () => {
  expect(trailFor("/stock/AVB")).toEqual([
    { label: "Stocks", to: "/" },
    { label: "AVB", to: null },
  ]);
});

test("a stock detail page on the default (charts) tab omits a third segment", () => {
  expect(trailFor("/stock/AVB", "#charts")).toEqual([
    { label: "Stocks", to: "/" },
    { label: "AVB", to: null },
  ]);
});

test("a stock sub-tab shows Stocks / TICKER / Tab, each ancestor a link", () => {
  expect(trailFor("/stock/AVB", "#news")).toEqual([
    { label: "Stocks", to: "/" },
    { label: "AVB", to: "/stock/AVB" },
    { label: "News", to: null },
  ]);
});

test("an unrecognized hash on a stock page falls back to the two-segment trail", () => {
  expect(trailFor("/stock/AVB", "#not-a-real-tab")).toEqual([
    { label: "Stocks", to: "/" },
    { label: "AVB", to: null },
  ]);
});

test("the ticker segment is uppercased regardless of URL casing", () => {
  expect(trailFor("/stock/avb")).toEqual([
    { label: "Stocks", to: "/" },
    { label: "AVB", to: null },
  ]);
});

test("Sectors with no sector param shows just its own name", () => {
  expect(trailFor("/sectors")).toEqual([{ label: "Sectors", to: null }]);
});

test("Sectors with a sector param shows Sectors / <Sector>", () => {
  expect(trailFor("/sectors/Technology")).toEqual([
    { label: "Sectors", to: "/sectors" },
    { label: "Technology", to: null },
  ]);
});

test.each([
  ["/news", "News"],
  ["/macro", "Macro"],
  ["/watchlist", "Watchlist"],
  ["/earnings", "Earnings"],
  ["/institutional-flow", "Institutional Flow"],
  ["/congress", "Congress"],
  ["/chat", "Chat"],
])("top-level page %s shows just %s, no trailing separator", (path, label) => {
  expect(trailFor(path)).toEqual([{ label, to: null }]);
});

// FR-026: the trail must come from the current location alone, with no
// dependence on how the page was reached — a pasted deep link produces the
// identical trail an in-app click-through would have.
test("a deep-linked stock sub-tab produces the same trail as an in-app navigation would", () => {
  const viaDeepLink = trailFor("/stock/AVB", "#news");
  const viaNavigation = trailFor("/stock/AVB", "#news");
  expect(viaDeepLink).toEqual(viaNavigation);
  expect(viaDeepLink).toEqual([
    { label: "Stocks", to: "/" },
    { label: "AVB", to: "/stock/AVB" },
    { label: "News", to: null },
  ]);
});

test("an unmatched route falls back to a single non-link crumb rather than throwing", () => {
  expect(trailFor("/this-route-does-not-exist")).toEqual([{ label: "Not Found", to: null }]);
});
