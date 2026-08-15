Here's the standard spec-kit flow, in order:

/speckit-specify -- Can use big LLM if complex task -- — Edit the feature description; this command updates spec.md in place (it's the same command whether you're creating a spec or altering an existing one). Give it a description of what's changing and it rewrites the relevant scenarios/requirements.

/speckit-clarify - big LLM --  (optional but recommended after any real change) — Asks up to 5 targeted questions about anything left ambiguous and encodes the answers back into spec.md.

/speckit-checklist (optional) — Generates a custom review checklist for the spec if you want a structured gut-check before moving on.

/speckit-plan - Big LLM — Regenerates plan.md, research.md, data-model.md, contracts/, and quickstart.md from the (now-altered) spec. This is where Technical Context and design decisions get worked out.

/speckit-tasks -- free LLM -- — Generates/regenerates tasks.md, the dependency-ordered task breakdown, from the plan's design artifacts.

/speckit-analyze (optional but valuable after altering) — Non-destructive cross-check of spec.md / plan.md / tasks.md for consistency — catches drift where an edited spec left the plan or tasks stale.

/speckit-implement -- free LLM — Executes tasks.md against the codebase.

/speckit-converge (optional, after implementing) — Diffs the actual codebase against spec/plan/tasks and appends any remaining unbuilt work as new tasks, so a partial implementation can be finished.

Alternative to step 7: /speckit-taskstoissues converts tasks.md into GitHub issues instead of (or alongside) direct implementation, if you want to track the work there.

One thing to flag: if a feature already has plan.md/tasks.md from before (like 011-the-strat, which we just planned), altering the spec afterward means those downstream files go stale — you'll want to re-run /speckit-plan → /speckit-tasks (and /speckit-analyze is cheap insurance) rather than jumping straight to /speckit-implement on old tasks.