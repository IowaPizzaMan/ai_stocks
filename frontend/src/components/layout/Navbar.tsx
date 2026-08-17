// Spec: specs/component-specs/frontend/components/layout/Navbar.md — flesh out in Phase 4
import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Stocks" },
  { to: "/macro", label: "Macro" },
  { to: "/institutional-flow", label: "Institutional Flow" },
  { to: "/sectors", label: "Sectors" },
  { to: "/earnings", label: "Earnings" },
];

export default function Navbar() {
  return (
    <nav className="flex items-center gap-6 border-b border-zinc-800 px-6 py-3">
      <span className="font-semibold tracking-tight">StockAI</span>
      {links.map(({ to, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            isActive ? "text-white" : "text-zinc-400 hover:text-zinc-200"
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
