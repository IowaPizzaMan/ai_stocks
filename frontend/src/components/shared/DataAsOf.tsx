// Caption showing when the underlying data (not the LLM synthesis) is from.
import { formatDate } from "../../lib/time";

export default function DataAsOf({
  date,
  label = "data as of",
  className = "text-xs text-zinc-600",
}: {
  date?: string | null;
  label?: string;
  className?: string;
}) {
  if (!date) return null;
  const formatted = formatDate(date);
  if (!formatted) return null;
  return <p className={className}>{label} {formatted}</p>;
}
