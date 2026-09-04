// Chat history sidebar — specs/035-chat-and-news-upgrade US5.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Conversation, ConversationSummary } from "../api/types";

export function useConversations() {
  return useQuery({
    queryKey: ["conversations"],
    queryFn: async () => {
      const { data } = await api.get<{ conversations: ConversationSummary[] }>("/chat/conversations");
      return data.conversations;
    },
  });
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: ["conversations", id],
    queryFn: async () => {
      const { data } = await api.get<Conversation>(`/chat/conversations/${id}`);
      return data;
    },
    enabled: id !== null,
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/chat/conversations/${id}`);
      return id;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["conversations"] }),
  });
}
