"""Cross-service field-vocabulary contract for the `screener` collection.
Spec: specs/031-semantic-layer-chat; contracts/screener-collection.md.

Mirrored verbatim in agent-runner/tests/test_screener.py — that duplication
IS the cross-service consistency check (constitution Principle VI): if a
field is added/renamed in agent-runner/tools/screener.py's compute_signals()
without updating semantic/schema.py's description (or vice versa), the model
either can't see a field that exists or is told about one that doesn't.
Either failure mode is caught here instead of being discovered as a bad chat
answer.
"""
from semantic import schema

# Mirrored verbatim in agent-runner/tests/test_screener.py.
SCREENER_FIELDS = {
    "ticker", "name", "sector", "industry", "market_cap", "is_tracked",
    "last_close", "last_bar_date", "range_pct_20d", "zscore_20d",
    "weekly_change_pct", "monthly_change_pct", "weekly_trend",
    "revenue_growth_yoy", "net_income_growth_yoy", "net_profit_margin",
    "margin_trend", "financials_trend", "free_cash_flow", "total_debt",
    "fcf_exceeds_debt", "signals_as_of", "price_data_through",
    "financials_as_of", "insufficient_history", "liked_status",
}


def test_schema_field_names_match_the_mirrored_contract_table():
    described = {field["name"] for field in schema.SCREENER_SCHEMA["fields"]}
    assert described == SCREENER_FIELDS


def test_every_field_has_a_type_and_description():
    for field in schema.SCREENER_SCHEMA["fields"]:
        assert field.get("type"), f"{field['name']} missing type"
        assert field.get("description"), f"{field['name']} missing description"


def test_schema_names_the_screener_collection():
    assert schema.SCREENER_SCHEMA["collection"] == "screener"


# --- 035-chat-and-news-upgrade (US1, FR-011) — verbose per-field metadata ---
# `unit`/`enum`/`aggregation` are optional additions to the existing field
# dicts, not new fields in SCREENER_FIELDS above — data-model.md §3 is
# explicit that this feature adds keys, never renames/adds/removes a field,
# so the two tests above stay the authority on the field-name contract.

def test_numeric_aggregation_fields_are_typed_as_numbers():
    for field in schema.SCREENER_SCHEMA["fields"]:
        if field.get("aggregation") == "numeric":
            assert field["type"] == "number", f"{field['name']} marked numeric aggregation but typed {field['type']!r}"


def test_groupable_aggregation_fields_are_typed_as_string_or_boolean():
    for field in schema.SCREENER_SCHEMA["fields"]:
        if field.get("aggregation") == "groupable":
            assert field["type"] in ("string", "boolean"), (
                f"{field['name']} marked groupable aggregation but typed {field['type']!r}"
            )


def test_enum_values_are_all_non_empty_strings():
    for field in schema.SCREENER_SCHEMA["fields"]:
        enum = field.get("enum")
        if enum is None:
            continue
        assert enum, f"{field['name']} has an empty enum list"
        assert all(isinstance(v, str) and v for v in enum), f"{field['name']}'s enum has a non-string/empty value"
