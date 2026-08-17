// Small "x" glyph for remove/delete controls. Pure SVG, no text nodes, so it
// never shows up in a component's visible textContent — the accessible name
// comes from the wrapping button's aria-label instead.
export default function RemoveIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}
