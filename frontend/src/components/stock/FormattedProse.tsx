// Spec: specs/021-stock-page-redesign US4 (FR-010) — renders narrative text as
// short paragraphs (or bullets when long) with key terms picked out.
import { formatProse } from "../../lib/prose";

export default function FormattedProse({
  text,
  className = "",
}: {
  text?: string | null;
  className?: string;
}) {
  const { blocks, asBullets } = formatProse(text ?? "");
  if (!blocks.length) return null;

  const rendered = blocks.map((block, i) => (
    <span key={i}>
      {block.segments.map((seg, j) =>
        seg.emphasis ? (
          <strong key={j} className="font-medium text-zinc-100">
            {seg.text}
          </strong>
        ) : (
          <span key={j}>{seg.text}</span>
        ),
      )}
    </span>
  ));

  if (asBullets) {
    return (
      <ul className={`space-y-1.5 text-sm leading-relaxed text-zinc-300 ${className}`}>
        {rendered.map((block, i) => (
          <li key={i} className="flex gap-2">
            <span className="mt-[0.45rem] h-1 w-1 shrink-0 rounded-full bg-zinc-600" />
            <span>{block}</span>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className={`space-y-2 text-sm leading-relaxed text-zinc-300 ${className}`}>
      {rendered.map((block, i) => (
        <p key={i}>{block}</p>
      ))}
    </div>
  );
}
