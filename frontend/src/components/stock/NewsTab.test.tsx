import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import type { NewsReport } from "../../api/types";
import NewsTab from "./NewsTab";
import SentimentTimeline from "./SentimentTimeline";

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 800 });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 400 });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
    width: 800, height: 400, top: 0, left: 0, bottom: 400, right: 800, x: 0, y: 0, toJSON: () => {},
  } as DOMRect);
});

afterEach(cleanup);

const news: NewsReport = {
  articles: [
    {
      date: "2026-08-15",
      datetime: "2026-08-15 09:00:00",
      source: "Reuters",
      headline: "Record quarter beats expectations",
      url: "https://example.com/a",
      text_excerpt: "The company reported strong demand.",
      bullish_count: 6,
      bearish_count: 2,
      ai_summary: "Results came in ahead of consensus on strong demand.",
    },
    {
      date: "2026-08-10",
      datetime: "2026-08-10 09:00:00",
      source: "Bloomberg",
      headline: "Regulatory review opens",
      url: "https://example.com/b",
      text_excerpt: "An investigation was disclosed.",
      bullish_count: 0,
      bearish_count: 6,
      ai_summary: null,
    },
  ],
  timeline: [
    { date: "2026-08-10", bullish: 0, bearish: 6, article_count: 1 },
    { date: "2026-08-15", bullish: 6, bearish: 2, article_count: 1 },
  ],
  trend: "bullish",
  stance: { direction: "bullish", reasoning: "The beat outweighs the review." },
  news_count: 2,
  days_covered: 2,
  window_days: 30,
  as_of: "2026-08-15",
};

test("lists each article with its date, source and headline", () => {
  render(<NewsTab news={news} />);
  expect(screen.getByText("Record quarter beats expectations")).toBeTruthy();
  expect(screen.getByText("Regulatory review opens")).toBeTruthy();
  expect(screen.getByText("Reuters")).toBeTruthy();
  expect(screen.getByText("Bloomberg")).toBeTruthy();
});

test("shows the AI summary when present and the excerpt when not", () => {
  render(<NewsTab news={news} />);
  expect(screen.getByText("Results came in ahead of consensus on strong demand.")).toBeTruthy();
  expect(screen.getByText("An investigation was disclosed.")).toBeTruthy();
});

test("shows per-article tone counts", () => {
  render(<NewsTab news={news} />);
  expect(screen.getByText(/6 bullish/)).toBeTruthy();
  expect(screen.getAllByText(/bearish/).length).toBeGreaterThan(0);
});

test("renders the timeline above the article list", () => {
  const { container } = render(<NewsTab news={news} />);
  expect(screen.getByText(/news tone over time/i)).toBeTruthy();
  const sections = container.querySelectorAll("section");
  expect(sections[0].textContent).toMatch(/news tone over time/i);
});

test("labels the content with its as-of date, since news only refreshes on pull", () => {
  render(<NewsTab news={news} />);
  expect(screen.getByText(/most recent article/i)).toBeTruthy();
});

test("shows an empty state when there is no coverage", () => {
  render(<NewsTab news={{ ...news, articles: [], timeline: [], news_count: 0 }} />);
  expect(screen.getByText(/no recent news coverage/i)).toBeTruthy();
});

test("shows an empty state when the news sub-report is absent entirely", () => {
  render(<NewsTab />);
  expect(screen.getByText(/no recent news coverage/i)).toBeTruthy();
});

// --- a month of coverage paginates rather than dumping hundreds of rows -----

const manyArticles = (n: number): NewsReport => ({
  ...news,
  news_count: n,
  days_covered: 30,
  articles: Array.from({ length: n }, (_, i) => ({
    date: "2026-08-15",
    datetime: `2026-08-15 09:${String(i % 60).padStart(2, "0")}:00`,
    source: "Wire",
    headline: `Story number ${i}`,
    url: `https://example.com/${i}`,
    text_excerpt: "excerpt",
    bullish_count: 1,
    bearish_count: 0,
    ai_summary: null,
  })),
});

test("renders only the first page of a month's coverage", () => {
  render(<NewsTab news={manyArticles(120)} />);
  expect(screen.getByText("Story number 0")).toBeTruthy();
  expect(screen.getByText("Story number 24")).toBeTruthy();
  expect(screen.queryByText("Story number 25")).toBeNull();
  expect(screen.getByText(/showing 25 of 120/i)).toBeTruthy();
});

test("the show-more button reveals the next page", () => {
  render(<NewsTab news={manyArticles(120)} />);
  fireEvent.click(screen.getByRole("button", { name: /show 25 more/i }));
  expect(screen.getByText("Story number 25")).toBeTruthy();
  expect(screen.getByText(/showing 50 of 120/i)).toBeTruthy();
});

test("the show-more button disappears once everything is visible", () => {
  render(<NewsTab news={manyArticles(30)} />);
  fireEvent.click(screen.getByRole("button", { name: /show 5 more/i }));
  expect(screen.queryByRole("button", { name: /show .* more/i })).toBeNull();
  expect(screen.getByText("Story number 29")).toBeTruthy();
});

test("no show-more button when the window fits on one page", () => {
  render(<NewsTab news={news} />);
  expect(screen.queryByRole("button", { name: /show .* more/i })).toBeNull();
});

test("reports the window and how many days actually had coverage", () => {
  render(<NewsTab news={manyArticles(120)} />);
  expect(screen.getByText(/last 30 days/i)).toBeTruthy();
  expect(screen.getByText(/30 days with coverage/i)).toBeTruthy();
});

// --- SentimentTimeline (shared with the Sentiment tab) ----------------------

test("timeline surfaces the trend direction as a label", () => {
  render(<SentimentTimeline timeline={news.timeline} trend="bearish" />);
  expect(screen.getByText(/trending bearish/i)).toBeTruthy();
});

test("timeline reports how much coverage it is based on", () => {
  render(<SentimentTimeline timeline={news.timeline} trend="bullish" />);
  expect(screen.getByText(/2 articles across 2 days/i)).toBeTruthy();
});

test("timeline degrades to a message when there is nothing to chart", () => {
  render(<SentimentTimeline timeline={[]} />);
  expect(screen.getByText(/no dated news language/i)).toBeTruthy();
});

test("a zero-term article still contributes a neutral point, not a bearish one", () => {
  render(<SentimentTimeline timeline={[{ date: "2026-08-01", bullish: 0, bearish: 0, article_count: 1 }]} trend="mixed" />);
  expect(screen.getByText(/mixed/i)).toBeTruthy();
});
