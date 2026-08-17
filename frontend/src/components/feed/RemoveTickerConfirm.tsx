// Inline destructive-deletion confirm popover. Spec: specs/023-remove-stocks
// FR-008 — a small anchored Confirm/Cancel step, not a full modal dialog.
import { useEffect, useRef } from "react";

export default function RemoveTickerConfirm({
  ticker,
  onConfirm,
  onCancel,
  pending = false,
  error = null,
}: {
  ticker: string;
  onConfirm: () => void;
  onCancel: () => void;
  pending?: boolean;
  error?: string | null;
}) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    confirmRef.current?.focus();
  }, []);

  return (
    <div
      role="dialog"
      aria-label={`Delete ${ticker}`}
      // Stops any interaction here (click, keydown) from bubbling to the
      // tile it's anchored to — opening/confirming/cancelling must never
      // also trigger the tile's own click-to-navigate handler.
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Escape") onCancel();
      }}
      className="w-48 rounded-lg border border-zinc-700 bg-zinc-900 p-3 text-left shadow-xl"
    >
      <p className="mb-3 text-xs leading-snug text-zinc-300">
        Delete <span className="font-semibold text-white">{ticker}</span> and all its data?
      </p>
      {error && (
        <p role="alert" className="mb-2 text-[11px] leading-snug text-red-400">
          {error}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          aria-label={`Cancel delete ${ticker}`}
          disabled={pending}
          onClick={onCancel}
          className="rounded px-2 py-1 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          ref={confirmRef}
          type="button"
          aria-label={`Confirm delete ${ticker}`}
          disabled={pending}
          onClick={onConfirm}
          className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {pending ? "Deleting…" : "Delete"}
        </button>
      </div>
    </div>
  );
}
