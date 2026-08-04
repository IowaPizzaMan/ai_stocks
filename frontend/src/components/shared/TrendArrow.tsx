// Small up/down trend indicator used beside metric values.
export default function TrendArrow({
  direction,
  className = "",
}: {
  direction: "up" | "down" | "flat";
  className?: string;
}) {
  if (direction === "flat") return null;
  return (
    <span aria-label={`trend ${direction}`} className={className}>
      {direction === "up" ? "▲" : "▼"}
    </span>
  );
}
