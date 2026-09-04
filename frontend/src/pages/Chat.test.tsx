import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { api } from "../api/client";
import type { ChatResponse, Conversation, ConversationSummary, StrategyPicks } from "../api/types";
import Chat from "./Chat";

vi.mock("../api/client", () => ({ api: { post: vi.fn(), get: vi.fn(), delete: vi.fn() } }));

beforeEach(() => {
  // specs/035-chat-and-news-upgrade US5 — ChatSidebar always calls GET
  // /chat/conversations; default to empty so tests that don't care about
  // history don't need to mock it themselves.
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url === "/chat/conversations") return Promise.resolve({ data: { conversations: [] } });
    return Promise.resolve({ data: {} });
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderChat() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      {/* specs/035-chat-and-news-upgrade FR-013 — strategy-picks candidate
          tickers and linkified answer text both render react-router <Link>s now. */}
      <MemoryRouter>
        <Chat />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const flagshipResponse: ChatResponse = {
  answer: "13 stocks matched: TPR, MO, AAPL",
  criteria: [{ label: "zscore_20d < 0", field: "zscore_20d", op: "$lt", value: 0 }],
  match_count: 13,
  rows: [{ ticker: "TPR" }],
  generated_query: { collection: "screener", pipeline: [{ $match: {} }] },
  excluded_for_missing_data: 0,
  signals_as_of: "2026-08-23T00:00:00Z",
  degraded: false,
  note: null,
  strategy_picks: null,
  citations: [],
  conversation_id: "conv-1",
  conversation_title: "13 stocks matched",
};

// specs/032-weekly-strategy-picks
const strategyPicks: StrategyPicks = {
  direction: "buy",
  count_requested: 10,
  week_of: "2026-08-24",
  market_condition_note: null,
  market_condition_unavailable: false,
  lists: [
    {
      strategy: "the_strat",
      strategy_label: "The Strat",
      candidates: [
        { ticker: "AAPL", entry_price: 187.5, basis: "weekly revstrat 2bar bullish, strength 3/4" },
      ],
      note: null,
    },
    {
      strategy: "gap_analysis",
      strategy_label: "Gap Analysis",
      candidates: [],
      note: "no candidates currently qualify this week",
    },
  ],
  excluded_by_market_flow: [],
  // specs/033-strategy-picks-filters
  condition_requested: null,
  condition_applied: false,
  condition_note: null,
};

const strategyPicksResponse: ChatResponse = {
  answer: "The Strat likes AAPL above $187.50. This is informational analysis only, not executed trades or licensed financial advice.",
  criteria: [],
  match_count: 1,
  rows: [],
  generated_query: null,
  excluded_for_missing_data: 0,
  signals_as_of: null,
  degraded: false,
  note: null,
  strategy_picks: strategyPicks,
  citations: [],
  conversation_id: "conv-2",
  conversation_title: "The Strat picks",
};

test("submitting a question renders the answer, criteria, and match count without extra interaction", async () => {
  vi.mocked(api.post).mockResolvedValue({ data: flagshipResponse });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), {
    target: { value: "what stocks are near their 20-day low?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));

  await waitFor(() => expect(screen.getByText(flagshipResponse.answer)).toBeDefined());
  expect(screen.getByText("zscore_20d < 0")).toBeDefined();
  expect(screen.getByText("13 match(es)")).toBeDefined();
  // raw query is NOT shown by default (FR-014)
  expect(screen.queryByText(/"collection": "screener"/)).toBeNull();
});

test("the raw query is revealed only after clicking the toggle", async () => {
  vi.mocked(api.post).mockResolvedValue({ data: flagshipResponse });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "test question" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(screen.getByText(flagshipResponse.answer)).toBeDefined());

  fireEvent.click(screen.getByRole("button", { name: "show query" }));
  expect(screen.getByText(/"collection": "screener"/)).toBeDefined();
});

test("a follow-up question sends the prior exchange as history", async () => {
  vi.mocked(api.post).mockResolvedValue({ data: flagshipResponse });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "first question" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "which of those?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2));

  const secondCallBody = vi.mocked(api.post).mock.calls[1][1] as { history: unknown[] };
  expect(secondCallBody.history).toHaveLength(2); // prior user turn + assistant turn
});

test("a degraded response shows an explanatory note", async () => {
  vi.mocked(api.post).mockResolvedValue({
    data: { ...flagshipResponse, degraded: true, note: "no_data", match_count: 0, criteria: [] },
  });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "anything" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));

  await waitFor(() =>
    expect(screen.getByText("Screening data hasn't been computed yet.")).toBeDefined(),
  );
});

// specs/032-weekly-strategy-picks US1
test("a strategy-picks response renders per-strategy lists, prices, and an empty-list note", async () => {
  vi.mocked(api.post).mockResolvedValue({ data: strategyPicksResponse });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), {
    target: { value: "per my trading strategies what should I buy this week" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));

  await waitFor(() => expect(screen.getByText(strategyPicksResponse.answer)).toBeDefined());
  expect(screen.getByText("The Strat")).toBeDefined();
  expect(screen.getByText("Buy at $187.50")).toBeDefined();
  expect(screen.getByText("Gap Analysis")).toBeDefined();
  expect(screen.getByText("no candidates currently qualify this week")).toBeDefined();
});

test("a strategy-picks candidate ticker renders as a link to its stock page (specs/035-chat-and-news-upgrade FR-013)", async () => {
  vi.mocked(api.post).mockResolvedValue({ data: strategyPicksResponse });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), {
    target: { value: "per my trading strategies what should I buy this week" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));

  await waitFor(() => expect(screen.getByRole("link", { name: "AAPL" })).toBeDefined());
  expect(screen.getByRole("link", { name: "AAPL" }).getAttribute("href")).toBe("/stock/AAPL");
});

test("a short-direction strategy-picks response labels candidates as 'Short at $X'", async () => {
  vi.mocked(api.post).mockResolvedValue({
    data: { ...strategyPicksResponse, strategy_picks: { ...strategyPicks, direction: "short" } },
  });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), {
    target: { value: "per my trading strategies what should I short this week" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));

  await waitFor(() => expect(screen.getByText("Short at $187.50")).toBeDefined());
});

test("candidates excluded by market condition are shown with their reason", async () => {
  const withExclusions: ChatResponse = {
    ...strategyPicksResponse,
    strategy_picks: {
      ...strategyPicks,
      market_condition_note: "market overbought (NYMO +68) — breadth doesn't support new buys this week",
      lists: strategyPicks.lists.map((l) => ({ ...l, candidates: [], note: "excluded" })),
      excluded_by_market_flow: [
        {
          ticker: "AAPL", entry_price: 187.5, basis: "weekly revstrat 2bar bullish, strength 3/4",
          strategy: "the_strat",
          reason: "market overbought (NYMO +68) — breadth doesn't support new buys this week",
        },
      ],
    },
  };
  vi.mocked(api.post).mockResolvedValue({ data: withExclusions });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "buy picks" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));

  await waitFor(() => expect(screen.getByText("Excluded by market condition")).toBeDefined());
  expect(screen.getByText(/AAPL \(The Strat\): market overbought/)).toBeDefined();
});

test("a strategy-picks response does not render the raw-query toggle", async () => {
  vi.mocked(api.post).mockResolvedValue({ data: strategyPicksResponse });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "buy picks" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));

  await waitFor(() => expect(screen.getByText(strategyPicksResponse.answer)).toBeDefined());
  expect(screen.queryByRole("button", { name: "show query" })).toBeNull();
});

test("a multi-paragraph/list answer renders as multiple distinct elements via AnswerText", async () => {
  const listAnswer: ChatResponse = {
    ...flagshipResponse,
    answer: "Top candidates:\n\n- TPR\n- MO\n- AAPL",
  };
  vi.mocked(api.post).mockResolvedValue({ data: listAnswer });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), {
    target: { value: "what are the top candidates?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));

  await waitFor(() => expect(screen.getByText("Top candidates:")).toBeDefined());
  expect(screen.getAllByRole("list").length).toBeGreaterThan(0);
  expect(screen.getByText("TPR")).toBeDefined();
  expect(screen.getByText("MO")).toBeDefined();
  expect(screen.getByText("AAPL")).toBeDefined();
});

test("multiple exchanges each render their own differently-formatted answer through AnswerText (FR-007)", async () => {
  vi.mocked(api.post).mockResolvedValueOnce({ data: flagshipResponse });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "first question" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(screen.getByText(flagshipResponse.answer)).toBeDefined());

  const secondAnswer: ChatResponse = { ...flagshipResponse, answer: "- alpha\n- beta" };
  vi.mocked(api.post).mockResolvedValueOnce({ data: secondAnswer });

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "second question" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));

  await waitFor(() => expect(screen.getByText("alpha")).toBeDefined());
  expect(screen.getByText(flagshipResponse.answer)).toBeDefined();
  expect(screen.getByText("beta")).toBeDefined();
});

// --- specs/035-chat-and-news-upgrade US5 — conversations now persist
// server-side (FR-015), superseding 031's original "cleared on refresh"
// design (FR-004) the test above used to assert.

test("a successful exchange sends the current conversation_id and adopts the response's on first answer", async () => {
  vi.mocked(api.post).mockResolvedValue({ data: flagshipResponse });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "test" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(screen.getByText(flagshipResponse.answer)).toBeDefined());

  const firstCallBody = vi.mocked(api.post).mock.calls[0][1] as { conversation_id: string | null };
  expect(firstCallBody.conversation_id).toBeNull(); // no conversation yet on the very first message

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "follow-up" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(2));

  const secondCallBody = vi.mocked(api.post).mock.calls[1][1] as { conversation_id: string | null };
  expect(secondCallBody.conversation_id).toBe("conv-1"); // adopted from the first response
});

test("selecting a conversation from the sidebar loads and displays its stored messages", async () => {
  const summaries: ConversationSummary[] = [
    { id: "conv-1", title: "NVDA recent news", created_at: "2026-08-25T14:00:00Z", updated_at: "2026-08-25T14:06:00Z", message_count: 2 },
  ];
  const full: Conversation = {
    id: "conv-1", title: "NVDA recent news",
    created_at: "2026-08-25T14:00:00Z", updated_at: "2026-08-25T14:06:00Z",
    messages: [
      { role: "user", content: "what's the latest on NVDA?", timestamp: "2026-08-25T14:00:00Z" },
      { role: "assistant", content: "NVDA rose 3% today.", timestamp: "2026-08-25T14:00:05Z" },
    ],
  };
  vi.mocked(api.get).mockImplementation((url: string) => {
    if (url === "/chat/conversations") return Promise.resolve({ data: { conversations: summaries } });
    if (url === "/chat/conversations/conv-1") return Promise.resolve({ data: full });
    return Promise.resolve({ data: {} });
  });
  renderChat();

  await waitFor(() => expect(screen.getByText("NVDA recent news")).toBeDefined());
  fireEvent.click(screen.getByText("NVDA recent news"));

  await waitFor(() => expect(screen.getByText("NVDA rose 3% today.")).toBeDefined());
  expect(screen.getByText("what's the latest on NVDA?")).toBeDefined();
});

test("starting a new chat clears the pane", async () => {
  vi.mocked(api.post).mockResolvedValue({ data: flagshipResponse });
  renderChat();

  fireEvent.change(screen.getByLabelText("Ask a question"), { target: { value: "test" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(screen.getByText(flagshipResponse.answer)).toBeDefined());

  fireEvent.click(screen.getByRole("button", { name: "New chat" }));

  expect(screen.queryByText(flagshipResponse.answer)).toBeNull();
});
