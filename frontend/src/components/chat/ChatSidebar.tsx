// Chat history sidebar — specs/035-chat-and-news-upgrade US5 (FR-017..FR-020).
import { useState } from "react";
import RemoveIcon from "../shared/RemoveIcon";
import { useConversations, useDeleteConversation } from "../../hooks/useConversations";
import { formatDate } from "../../lib/time";
import type { ConversationSummary } from "../../api/types";

interface ChatSidebarProps {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
}

function ConversationRow({
  conversation, active, onSelect,
}: { conversation: ConversationSummary; active: boolean; onSelect: (id: string) => void }) {
  const deleteMutation = useDeleteConversation();
  const [revealed, setRevealed] = useState(false);

  return (
    <li
      className="relative"
      onMouseEnter={() => setRevealed(true)}
      onMouseLeave={() => setRevealed(false)}
      onFocus={() => setRevealed(true)}
      onBlur={() => setRevealed(false)}
    >
      <button
        type="button"
        onClick={() => onSelect(conversation.id)}
        className={`block w-full rounded-md px-2 py-1.5 pr-7 text-left transition-colors ${
          active ? "bg-zinc-800 text-white" : "hover:bg-zinc-900 hover:text-zinc-200"
        }`}
      >
        <p className="truncate text-sm">{conversation.title}</p>
        <p className="text-xs text-zinc-500">{formatDate(conversation.updated_at)}</p>
      </button>
      <button
        type="button"
        aria-label={`Delete ${conversation.title}`}
        disabled={deleteMutation.isPending}
        onClick={() => deleteMutation.mutate(conversation.id)}
        className={`absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-zinc-500 transition-opacity hover:bg-zinc-800 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50 ${
          revealed ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <RemoveIcon className="h-3 w-3" />
      </button>
    </li>
  );
}

export default function ChatSidebar({ activeId, onSelect, onNewChat }: ChatSidebarProps) {
  const { data, isLoading } = useConversations();

  return (
    <aside className="flex w-56 shrink-0 flex-col gap-3 border-r border-zinc-800 p-4 text-sm text-zinc-400">
      <button
        type="button"
        onClick={onNewChat}
        className="rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition-colors hover:border-zinc-500"
      >
        New chat
      </button>
      <p className="font-medium text-zinc-300">History</p>
      {isLoading && <p className="text-xs text-zinc-600">loading…</p>}
      {!isLoading && (data?.length ?? 0) === 0 && (
        <p className="text-xs text-zinc-600">No saved conversations yet.</p>
      )}
      <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto">
        {data?.map((conversation) => (
          <ConversationRow
            key={conversation.id}
            conversation={conversation}
            active={conversation.id === activeId}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </aside>
  );
}
