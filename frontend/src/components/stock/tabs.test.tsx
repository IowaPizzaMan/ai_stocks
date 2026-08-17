import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import type { InsiderReport, NewsReport, SentimentReport } from "../../api/types";
import FormattedProse from "./FormattedProse";
import { InsiderTab, SentimentTab } from "./tabs";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn().mockResolvedValue({ data: {} }), post: vi.fn(), delete: vi.fn() },
}));

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 800 });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 400 });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    width: 800, height: 400, top: 0, left: 0, bottom: 400, right: 800, x: 0, y: 0, toJSON: () => {},
  } as DOMRect);
});

afterEach(cleanup);

const withQuery = (ui: React.ReactNode) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {ui}
  </QueryClientProvider>
);

// --- FormattedProse ---------------------------------------------------------

test("FormattedProse renders bullets for a long narrative", () => {
  const { container } = render(
    <FormattedProse text="Alpha happened. Beta happened. Gamma happened. Delta happened." />,
  );
  expect(container.querySelectorAll("li")).toHaveLength(4);
});

test("FormattedProse renders short text as paragraphs, not bullets", () => {
  const { container } = render(<FormattedProse text="One thing. Two things." />);
  expect(container.querySelectorAll("li")).toHaveLength(0);
  expect(container.querySelectorAll("p")).toHaveLength(1);
});

test("FormattedProse emphasizes price levels and direction words", () => {
  const { container } = render(
    <FormattedProse text="It is bullish above 182.50 with support holding." />,
  );
  const strongs = [...container.querySelectorAll("strong")].map((s) => s.textContent);
  expect(strongs).toContain("bullish");
  expect(strongs).toContain("182.50");
});

test("FormattedProse renders nothing for empty text", () => {
  const { container } = render(<FormattedProse text="" />);
  expect(container.innerHTML).toBe("");
});

// --- Sentiment tab ----------------------------------------------------------

const sentiment: SentimentReport = {
  overall_sentiment_signal: "mildly_bullish",
  confidence: "medium",
  current_tone: "cautiously_optimistic",
  tone_evidence: ["Analysts cite improving demand"],
  earnings_surprise_read: "Three straight beats.",
  narrative: "Coverage has turned more constructive over the last month.",
  news_count: 12,
  transcripts_available: false,
  bullish_keywords: { terms: ["strong"], count: 4 },
  cautious_keywords: { terms: ["headwind"], count: 1 },
  as_of: "2026-08-15",
};

const news: NewsReport = {
  articles: [],
  timeline: [
    { date: "2026-08-10", bullish: 2, bearish: 5, article_count: 2 },
    { date: "2026-08-15", bullish: 7, bearish: 1, article_count: 3 },
  ],
  trend: "bullish",
  stance: null,
  news_count: 5,
  as_of: "2026-08-15",
};

test("Sentiment tab leads with the signal gauge and the news timeline", () => {
  const { container } = render(<SentimentTab sentiment={sentiment} news={news} />);
  const sections = container.querySelectorAll("section");
  const first = sections[0].textContent ?? "";
  expect(first).toMatch(/where sentiment stands/i);
  expect(first).toMatch(/mildly bullish/i);
  expect(first).toMatch(/trending bullish/i);
});

test("Sentiment tab keeps tone evidence, keyword pills and the earnings read below", () => {
  render(<SentimentTab sentiment={sentiment} news={news} />);
  expect(screen.getByText(/analysts cite improving demand/i)).toBeTruthy();
  expect(screen.getByText(/bullish language/i)).toBeTruthy();
  expect(screen.getByText(/cautious language/i)).toBeTruthy();
  expect(screen.getByText(/three straight beats/i)).toBeTruthy();
});

test("Sentiment tab explains the missing timeline rather than rendering an empty chart", () => {
  render(<SentimentTab sentiment={sentiment} />);
  expect(screen.getByText(/timeline appears here after the next analysis pull/i)).toBeTruthy();
});

test("Sentiment tab shows its empty state without a sub-report", () => {
  render(<SentimentTab />);
  expect(screen.getByText(/no sentiment sub-report/i)).toBeTruthy();
});

// --- Insider tab ------------------------------------------------------------

const insider: InsiderReport = {
  overall_insider_signal: "neutral",
  confidence: "medium",
  narrative: "Selling has been routine.",
  key_buyers: [],
  recent_transactions: [],
  cluster_signal: { detected: false, insiders: [], window_days: null },
  net_direction: "balanced",
  mspr_trend: { direction: "flat", commentary: "flat" },
  unusual_size: "none",
  signal_strength: "weak",
  as_of: "2026-08-01",
};

test("Insider tab renders the quarterly flow section alongside the transaction table", () => {
  render(withQuery(<InsiderTab insider={{
    ...insider,
    quarterly_stats: [{
      year: 2026, quarter: 2, acquired_transactions: 7, disposed_transactions: 40,
      acquired_disposed_ratio: 0.175, total_acquired: 303199, total_disposed: 927380,
      total_purchases: 1, total_sales: 12,
    }],
  }} />));
  expect(screen.getByText(/quarterly flow/i)).toBeTruthy();
  expect(screen.getByText(/net disposed/i)).toBeTruthy();
  expect(screen.getByText(/transactions \(90 days\)/i)).toBeTruthy();
});

test("Insider tab degrades gracefully when quarterly stats are missing", () => {
  render(withQuery(<InsiderTab insider={insider} />));
  expect(screen.getByText(/no quarterly insider statistics/i)).toBeTruthy();
});
