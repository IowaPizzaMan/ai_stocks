// React Query hook for POST /chat — specs/031-semantic-layer-chat.
// A mutation, not a query: no caching, no polling (repo-wide refetchInterval:
// false convention) — each question is a one-off request.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { ChatRequest, ChatResponse, ChatTurn } from "../api/types";

export function useChat() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (
      { question, history, conversationId }:
      { question: string; history: ChatTurn[]; conversationId: string | null },
    ) => {
      const body: ChatRequest = { question, history, conversation_id: conversationId };
      const { data } = await api.post<ChatResponse>("/chat", body);
      return data;
    },
    // specs/035-chat-and-news-upgrade US5 — a successful exchange creates or
    // updates a conversation; the sidebar list has no other refresh signal.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["conversations"] }),
  });
}
