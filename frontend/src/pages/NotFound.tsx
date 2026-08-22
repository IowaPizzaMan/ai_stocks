// specs/028-dashboard-tweaks-batch US1 (FR-001, R1) — catch-all so an
// unmatched path (e.g. a mistyped ticker link) renders a visible message
// instead of an empty <main>, which is what made the original blank-page
// bug silent.
import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-24 text-center">
      <h1 className="mb-2 text-xl font-semibold text-white">Page not found</h1>
      <p className="mb-6 text-sm text-zinc-500">
        There's nothing here — the link may be out of date.
      </p>
      <Link to="/" className="text-sky-400 hover:underline">
        Back to Stocks
      </Link>
    </div>
  );
}
