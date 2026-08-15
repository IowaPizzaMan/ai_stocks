# Quickstart: Validating The Strat Rule Engine

## Prerequisites

- `agent-runner/` Python environment set up (`agent-runner/.venv`, or
  `pip install -r agent-runner/requirements.txt`)
- No network/API keys required for the unit-test path below (`yfinance` is only
  needed for the live-ticker smoke check)

## 1. Run the existing + extended test suite

```bash
cd agent-runner
pytest tests/test_the_strat.py -v
```

Expected: all tests pass, including the existing bar-classification, hammer/shooter,
Rev Strat, and TFC tests, plus new tests added for each FR area covered by
[data-model.md](./data-model.md) (outside-bar subtypes, stop/level-of-defense,
Broadening Formation tracking, pre-trade checklist, VIX-ETN adjustment).

## 2. Validate against the spec's acceptance scenarios directly

Each `specs/011-the-strat/spec.md` Acceptance Scenario maps to a test case; spot-check
a few by name once implemented, e.g.:

```bash
pytest tests/test_the_strat.py -k "outside_subtype" -v      # spec US1 scenario 2
pytest tests/test_the_strat.py -k "tfc_control" -v           # spec US2 scenario 3
pytest tests/test_the_strat.py -k "broadening_formation" -v  # spec US3 scenario 1
pytest tests/test_the_strat.py -k "checklist" -v              # spec US4 scenarios 1-3
pytest tests/test_the_strat.py -k "vix_etn" -v                 # FR-040-042
```

## 3. Manual smoke check against a live ticker

```bash
cd agent-runner
python - <<'PY'
from tools import price
from skills import the_strat

history = price.get_price_history("AAPL")
result = the_strat.run("AAPL", history)

print(result["tfc"])
print(result["signal"])
print(result["broadening_formation"])
print(result["pre_trade_checklist"])
PY
```

Expected outcome: a populated dict per
[contracts/the_strat_run.md](./contracts/the_strat_run.md) — no exceptions, `tfc`
reports one of `full_bullish`/`full_bearish`/`conflict` plus a non-empty `control`
list, and `pre_trade_checklist` is present (fields may be empty/"n/a" if AAPL has no
in-force signal on the day this is run).

## 4. Confirm the existing pipeline still works end-to-end

```bash
cd agent-runner
pytest tests/test_crew.py -v
```

Expected: unchanged — `crew.py:152`'s call site (`the_strat.run(ticker, price_history)`)
must keep working with no new required arguments, per the additive-only contract
guarantee in [contracts/the_strat_run.md](./contracts/the_strat_run.md).

## Out of scope for this quickstart

- Updating `agents/technical_analyst.py`'s LLM prompt to narrate the new fields —
  tracked separately in tasks.md, not required for the rule engine itself to be
  correct.
- Any UI/frontend surface for the new fields — no frontend component-spec
  currently reads `the_strat` output directly.
