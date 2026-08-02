// Spec: specs/component-specs/frontend/pages — implement in Phase 5
import { useParams } from "react-router-dom";

export default function Sectors() {
  const { sector } = useParams();
  return (
    <section>
      <h1 className="text-xl font-semibold">{sector ?? "Sectors"}</h1>
      <p className="mt-2 text-zinc-400">Sector heatmap coming in Phase 5.</p>
    </section>
  );
}
