// Shared hash-tab nav, extracted from StockDetail.tsx (specs/021-stock-page-redesign)
// so the Stocks page (specs/027) can reuse the same tab convention instead of a
// second one.
import type { ReactNode } from "react";

export interface Tab {
  id: string;
  label: string;
}

export default function TabBar({
  tabs,
  activeTab,
  onSelect,
  trailing,
}: {
  tabs: Tab[];
  activeTab: string;
  onSelect: (id: string) => void;
  trailing?: ReactNode;
}) {
  return (
    <nav className="flex flex-wrap gap-1 border-b border-zinc-800">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onSelect(tab.id)}
          className={`px-3 py-2 text-sm transition-colors ${
            activeTab === tab.id
              ? "border-b-2 border-sky-500 text-white"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          {tab.label}
        </button>
      ))}
      {trailing && <span className="ml-auto self-center text-xs text-zinc-600">{trailing}</span>}
    </nav>
  );
}
