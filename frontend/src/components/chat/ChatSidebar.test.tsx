// specs/035-chat-and-news-upgrade US5 — chat history sidebar.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import type { ConversationSummary } from "../../api/types";
import ChatSidebar from "./ChatSidebar";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const CONVERSATIONS: ConversationSummary[] = [
  { id: "1", title: "NVDA recent news", created_at: "2026-08-25T14:00:00Z", updated_at: "2026-08-25T14:06:00Z", message_count: 4 },
  { id: "2", title: "Improving financials screen", created_at: "2026-08-24T09:00:00Z", updated_at: "2026-08-24T09:01:00Z", message_count: 2 },
];

function renderSidebar(props: Partial<React.ComponentProps<typeof ChatSidebar>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const onSelect = props.onSelect ?? vi.fn();
  const onNewChat = props.onNewChat ?? vi.fn();
  return {
    onSelect,
    onNewChat,
    ...render(
      <QueryClientProvider client={client}>
        <ChatSidebar activeId={props.activeId ?? null} onSelect={onSelect} onNewChat={onNewChat} />
      </QueryClientProvider>,
    ),
  };
}

test("renders each conversation's title and a formatted date", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { conversations: CONVERSATIONS } });
  renderSidebar();

  await waitFor(() => expect(screen.getByText("NVDA recent news")).toBeTruthy());
  expect(screen.getByText("Improving financials screen")).toBeTruthy();
});

test("clicking a conversation calls onSelect with its id", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { conversations: CONVERSATIONS } });
  const { onSelect } = renderSidebar();

  await waitFor(() => expect(screen.getByText("NVDA recent news")).toBeTruthy());
  fireEvent.click(screen.getByText("NVDA recent news"));

  expect(onSelect).toHaveBeenCalledWith("1");
});

test("deleting a conversation removes it from the list", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { conversations: CONVERSATIONS } });
  (api.delete as ReturnType<typeof vi.fn>).mockResolvedValue({ data: null });
  renderSidebar();

  await waitFor(() => expect(screen.getByText("NVDA recent news")).toBeTruthy());
  fireEvent.click(screen.getByRole("button", { name: /delete nvda recent news/i }));

  await waitFor(() => expect(api.delete).toHaveBeenCalledWith("/chat/conversations/1"));
});

test("clicking new chat calls onNewChat", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { conversations: CONVERSATIONS } });
  const { onNewChat } = renderSidebar();

  await waitFor(() => expect(screen.getByText("NVDA recent news")).toBeTruthy());
  fireEvent.click(screen.getByRole("button", { name: /new chat/i }));

  expect(onNewChat).toHaveBeenCalled();
});

test("an empty conversation list shows an empty-state message", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { conversations: [] } });
  renderSidebar();

  await waitFor(() => expect(screen.getByText(/no saved conversations/i)).toBeTruthy());
});

test("the active conversation is visually distinguished", async () => {
  (api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { conversations: CONVERSATIONS } });
  renderSidebar({ activeId: "1" });

  await waitFor(() => expect(screen.getByText("NVDA recent news")).toBeTruthy());
  const activeRow = screen.getByText("NVDA recent news").closest("button");
  const inactiveRow = screen.getByText("Improving financials screen").closest("button");
  expect(activeRow?.className).not.toBe(inactiveRow?.className);
});
