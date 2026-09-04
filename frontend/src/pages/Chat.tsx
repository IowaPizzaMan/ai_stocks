// Ask a data-grounded question about tracked stocks — specs/031-semantic-layer-chat.
// specs/035-chat-and-news-upgrade US5 — conversations now persist server-side
// (superseding 031's original FR-004 "stateless, cleared on refresh" design)
// and a sidebar lists past ones, matching the pattern the response's
// `history` replay already used for follow-ups within one session.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AnswerText from "../components/chat/AnswerText";
import ChatSidebar from "../components/chat/ChatSidebar";
import { useChat } from "../hooks/useChat";
import { useConversation } from "../hooks/useConversations";
import type { ChatResponse, ChatTurn, StrategyKey } from "../api/types";

// specs/032-weekly-strategy-picks
const STRATEGY_LABELS: Record<StrategyKey, string> = {
  the_strat: "The Strat",
  gap_analysis: "Gap Analysis",
};

interface Exchange {
  question: string;
  response: ChatResponse;
}

// A conversation reopened from history only has role/content/timestamp per
// message (data-model.md §2) — none of a live response's structured
// metadata (criteria, strategy_picks, generated_query…) survives a reload.
// Stubbing those fields to empty/null lets the same render path handle both
// a live exchange and a reloaded one without a second code path.
function stubResponse(answer: string): ChatResponse {
  return {
    answer, criteria: [], match_count: 0, rows: [], generated_query: null,
    excluded_for_missing_data: 0, signals_as_of: null, degraded: false, note: null,
    strategy_picks: null, citations: [], conversation_id: null, conversation_title: null,
  };
}

export default function Chat() {
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [expandedQuery, setExpandedQuery] = useState<Set<number>>(new Set());
  const chat = useChat();
  const loaded = useConversation(conversationId);

  useEffect(() => {
    document.title = "StockAI — Chat";
  }, []);

  // Reconstruct the exchange list from a reopened conversation's flat
  // message history — pairs (user, assistant) in order.
  useEffect(() => {
    if (!loaded.data?.messages) return;
    const messages = loaded.data.messages;
    const nextExchanges: Exchange[] = [];
    const nextTurns: ChatTurn[] = [];
    for (let i = 0; i < messages.length - 1; i += 2) {
      const question = messages[i];
      const answer = messages[i + 1];
      if (question?.role !== "user" || answer?.role !== "assistant") continue;
      nextExchanges.push({ question: question.content, response: stubResponse(answer.content) });
      nextTurns.push({ role: "user", content: question.content }, { role: "assistant", content: answer.content });
    }
    setExchanges(nextExchanges);
    setTurns(nextTurns);
  }, [loaded.data]);

  function handleSelectConversation(id: string) {
    setConversationId(id);
  }

  function handleNewChat() {
    setConversationId(null);
    setExchanges([]);
    setTurns([]);
    setInput("");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question || chat.isPending) return;

    chat.mutate(
      { question, history: turns, conversationId },
      {
        onSuccess: (data) => {
          setExchanges((prev) => [...prev, { question, response: data }]);
          setTurns((prev) => [
            ...prev,
            { role: "user", content: question },
            { role: "assistant", content: data.answer },
          ]);
          if (data.conversation_id) setConversationId(data.conversation_id);
          setInput("");
        },
      },
    );
  }

  function toggleQuery(index: number) {
    setExpandedQuery((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  return (
    <div className="flex gap-6">
      <ChatSidebar activeId={conversationId} onSelect={handleSelectConversation} onNewChat={handleNewChat} />

      <div className="mx-auto max-w-3xl flex-1 space-y-6">
        <h1 className="text-xl font-semibold text-white">Chat</h1>

        {exchanges.length === 0 && !chat.isPending && (
          <p className="py-6 text-center text-sm text-zinc-600">
            Ask a question about the stocks you track — e.g. "what stocks are near the bottom of
            their 20-day range but rising this week?" or "per my trading strategies, what should I
            buy this week and at what prices?"
          </p>
        )}

        <div className="space-y-4">
          {exchanges.map((exchange, index) => (
            <section
              key={index}
              className="space-y-3 rounded-xl border border-zinc-800 bg-zinc-900 p-5"
            >
              <p className="text-sm font-medium text-zinc-300">{exchange.question}</p>

              <AnswerText text={exchange.response.answer} />

              {exchange.response.strategy_picks && (
                <div className="space-y-3">
                  {exchange.response.strategy_picks.market_condition_unavailable && (
                    <p className="rounded-lg border border-amber-900 bg-amber-950/40 px-3 py-1.5 text-xs text-amber-400">
                      Market-condition data was unavailable — no breadth filter was applied.
                    </p>
                  )}
                  {exchange.response.strategy_picks.market_condition_note && (
                    <p className="rounded-lg border border-amber-900 bg-amber-950/40 px-3 py-1.5 text-xs text-amber-400">
                      {exchange.response.strategy_picks.market_condition_note}
                    </p>
                  )}

                  {exchange.response.strategy_picks.lists.map((list) => (
                    <div key={list.strategy} className="space-y-1">
                      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        {list.strategy_label}
                      </p>
                      {list.candidates.length > 0 ? (
                        <ul className="space-y-1 text-sm text-zinc-100">
                          {list.candidates.map((c) => (
                            <li key={c.ticker} className="flex items-baseline justify-between gap-3">
                              <span>
                                {/* specs/035-chat-and-news-upgrade FR-013 — same
                                    clickable-ticker guarantee as free-form prose answers. */}
                                <Link to={`/stock/${c.ticker}`} className="font-medium text-sky-400 hover:underline">
                                  {c.ticker}
                                </Link>{" "}
                                <span className="text-zinc-500">— {c.basis}</span>
                              </span>
                              <span className="whitespace-nowrap text-zinc-300">
                                {exchange.response.strategy_picks?.direction === "short" ? "Short" : "Buy"} at $
                                {c.entry_price.toFixed(2)}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-zinc-500">{list.note}</p>
                      )}
                    </div>
                  ))}

                  {exchange.response.strategy_picks.excluded_by_market_flow.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                        Excluded by market condition
                      </p>
                      <ul className="space-y-0.5 text-xs text-zinc-500">
                        {exchange.response.strategy_picks.excluded_by_market_flow.map((item) => (
                          <li key={`${item.strategy}-${item.ticker}`}>
                            {item.ticker} ({STRATEGY_LABELS[item.strategy]}): {item.reason}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {exchange.response.degraded && (
                <p className="rounded-lg border border-amber-900 bg-amber-950/40 px-3 py-1.5 text-xs text-amber-400">
                  {exchange.response.note === "no_data" &&
                    "Screening data hasn't been computed yet."}
                  {exchange.response.note === "model_unavailable" &&
                    "The chat model is temporarily unavailable."}
                  {exchange.response.note === "query_rejected" &&
                    "That question couldn't be answered safely."}
                  {!["no_data", "model_unavailable", "query_rejected"].includes(
                    exchange.response.note ?? "",
                  ) && "This answer may be incomplete."}
                </p>
              )}

              {exchange.response.criteria.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                    Criteria applied
                  </p>
                  <ul className="space-y-0.5 text-xs text-zinc-400">
                    {exchange.response.criteria.map((c, i) => (
                      <li key={i}>{c.label}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex items-center gap-3 text-xs text-zinc-500">
                <span>{exchange.response.match_count} match(es)</span>
                {exchange.response.excluded_for_missing_data > 0 && (
                  <span>
                    {exchange.response.excluded_for_missing_data} excluded (insufficient data)
                  </span>
                )}
                {exchange.response.generated_query && (
                  <button
                    onClick={() => toggleQuery(index)}
                    className="text-sky-500 hover:text-sky-400"
                  >
                    {expandedQuery.has(index) ? "hide query" : "show query"}
                  </button>
                )}
              </div>

              {exchange.response.generated_query && expandedQuery.has(index) && (
                <pre className="overflow-x-auto rounded-lg bg-zinc-950 p-3 text-xs text-zinc-400">
                  {JSON.stringify(exchange.response.generated_query, null, 2)}
                </pre>
              )}
            </section>
          ))}
        </div>

        {chat.isPending && (
          <p className="py-2 text-center text-sm text-zinc-600">thinking…</p>
        )}

        {chat.isError && (
          <p className="py-2 text-center text-sm text-zinc-600">
            Something went wrong asking that question. Try again.
          </p>
        )}

        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about your tracked stocks…"
            aria-label="Ask a question"
            disabled={chat.isPending}
            className="flex-1 rounded-full border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm placeholder:text-zinc-600 focus:border-sky-500 focus:outline-none disabled:opacity-40"
          />
          <button
            type="submit"
            disabled={chat.isPending || !input.trim()}
            className="rounded-full border border-zinc-700 px-4 py-2 text-sm text-zinc-300 transition-colors hover:border-zinc-500 disabled:opacity-40"
          >
            Ask
          </button>
        </form>
      </div>
    </div>
  );
}
