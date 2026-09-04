// specs/037-stocks-conviction-and-activity US4 (FR-023-FR-026).
// Mounted once in App.tsx's layout, above <Routes>, so every page gets a
// consistent trail without each page having to remember to render one.
import { Fragment } from "react";
import { Link, useLocation } from "react-router-dom";
import { trailFor } from "../../lib/breadcrumbs";

export default function Breadcrumbs() {
  const location = useLocation();
  const crumbs = trailFor(location.pathname, location.hash);

  return (
    <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1.5 text-sm text-zinc-500">
      {crumbs.map((crumb, i) => (
        <Fragment key={`${crumb.label}-${i}`}>
          {i > 0 && <span className="text-zinc-700">/</span>}
          {crumb.to ? (
            <Link to={crumb.to} className="hover:text-zinc-300">
              {crumb.label}
            </Link>
          ) : (
            <span className="text-zinc-300" aria-current="page">
              {crumb.label}
            </span>
          )}
        </Fragment>
      ))}
    </nav>
  );
}
