// Spec: specs/029-company-profile-tweaks/contracts/company-profile-api.md
//
// Shared fallback behavior across three surfaces (grid tiles, hover cards,
// stock header, research R6): a null/undefined src renders the monogram
// fallback immediately with no network attempt, and an onError (a
// reachable-but-broken URL) swaps to the same fallback rather than a broken
// image icon. Fixed dimensions on both states prevent layout shift.
import { useState } from "react";

const SIZE_PX: Record<"sm" | "md" | "lg", number> = {
  sm: 16,
  md: 24,
  lg: 40,
};

export default function CompanyLogo({
  ticker,
  src,
  size = "md",
}: {
  ticker: string;
  src?: string | null;
  size?: "sm" | "md" | "lg";
}) {
  const [errored, setErrored] = useState(false);
  const px = SIZE_PX[size];
  const showImage = !!src && !errored;

  if (!showImage) {
    // At "sm" (the compact grid tile, 16px, right beside the ticker text
    // itself — specs/029-company-profile-tweaks US3 FR-021a) a monogram
    // would just repeat the first letters of the ticker sitting right next
    // to it, so the fallback there is a plain neutral chip with no text.
    return (
      <span
        role="img"
        aria-label={`${ticker} logo`}
        className="inline-flex shrink-0 items-center justify-center rounded bg-zinc-700 font-semibold text-zinc-300"
        style={{ width: px, height: px, fontSize: px * 0.42 }}
      >
        {size !== "sm" && ticker.slice(0, 2)}
      </span>
    );
  }

  return (
    <img
      src={src}
      alt={`${ticker} logo`}
      width={px}
      height={px}
      loading="lazy"
      className="shrink-0 rounded bg-zinc-800 object-contain"
      style={{ width: px, height: px }}
      onError={() => setErrored(true)}
    />
  );
}
