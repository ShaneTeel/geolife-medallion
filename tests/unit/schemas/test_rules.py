"""Unit tests for schemas.rules (offline).

These check the rule definitions themselves. Whether Spark applies them correctly
is tested in tests/integration/test_quarantine_spark.py.
"""

from geolife_medallion.schemas import (
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    MIN_TS,
    SILVER_FIX_RULES,
)


def test_coordinate_thresholds_are_the_valid_earth_ranges():
    assert (LAT_MIN, LAT_MAX) == (-90.0, 90.0)
    assert (LON_MIN, LON_MAX) == (-180.0, 180.0)


def test_rules_use_the_shared_thresholds():
    """Rules are built from the constants, so the numbers live in one place."""
    assert f"BETWEEN {LAT_MIN} AND {LAT_MAX}" in SILVER_FIX_RULES["valid_latitude"]
    assert f"BETWEEN {LON_MIN} AND {LON_MAX}" in SILVER_FIX_RULES["valid_longitude"]
    assert MIN_TS in SILVER_FIX_RULES["valid_timestamp"]


def test_every_ranged_column_has_an_explicit_not_null_rule():
    """A range check on null evaluates to null, which does NOT fail the row."""
    not_null_rules = " ".join(
        cond for cond in SILVER_FIX_RULES.values() if "IS NOT NULL" in cond
    )
    for column in ("latitude", "longitude", "recorded_at_utc"):
        assert f"{column} IS NOT NULL" in not_null_rules


def test_rule_names_are_snake_case_identifiers():
    """Names end up in the failed_rules column, so keep them clean and stable."""
    for name in SILVER_FIX_RULES:
        assert name.isidentifier() and name == name.lower()
