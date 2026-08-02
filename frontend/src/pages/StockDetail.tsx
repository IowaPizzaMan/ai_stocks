// Spec: specs/component-specs/frontend/pages/StockDetail.md — implement in Phases 4–5
import { useParams } from "react-router-dom";

export default function StockDetail() {
  const { ticker } = useParams();
  return (
    <section>
      <h1 className="text-xl font-semibold">{ticker?.toUpperCase()}</h1>
      <p className="mt-2 text-zinc-400">Stock detail coming in Phase 4.</p>
    </section>
  );
}
