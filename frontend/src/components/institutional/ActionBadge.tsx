import type { FlowAction } from "../../api/types";

const ACTION_CONFIG: Record<FlowAction, { label: string; classes: string }> = {
  new_position: { label: "New Position", classes: "bg-sky-500/10 text-sky-300 border-sky-500/40" },
  add: { label: "Add", classes: "bg-emerald-500/10 text-emerald-300 border-emerald-500/40" },
  trim: { label: "Trim", classes: "bg-amber-500/10 text-amber-300 border-amber-500/40" },
  exit: { label: "Exit", classes: "bg-red-500/10 text-red-300 border-red-500/40" },
};

export default function ActionBadge({ action }: { action: FlowAction }) {
  const config = ACTION_CONFIG[action] ?? ACTION_CONFIG.add;
  return (
    <span
      className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${config.classes}`}
    >
      {config.label}
    </span>
  );
}
