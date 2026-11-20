"""Integration tests for preprocess.quarantine on real Spark (needs --databricks).

These run the SQL rules in Spark itself, so they prove the null handling and
rule wiring that the offline tests can only check as strings.
"""

from datetime import datetime

import pytest

from geolife_medallion.preprocess import split_duplicates, split_valid
from geolife_medallion.schemas import BRONZE_POSITION_FIX_SCHEMA, SILVER_FIX_RULES

TS = datetime(2008, 10, 23, 7, 0, 0)


def bronze_row(tid="1", lat=39.98, lon=116.31, ts=TS, uid="000"):
    return (uid, tid, lat, lon, ts, f"/landing/{uid}/Trajectory/{tid}.plt", TS, "test")


# One row per rule, each breaking only that rule.
BAD_ROWS = {
    "has_coordinates": bronze_row(lat=None),
    "has_timestamp": bronze_row(ts=None),
    "valid_latitude": bronze_row(lat=91.0),
    "valid_longitude": bronze_row(lon=-181.0),
    "not_null_island": bronze_row(lat=0.0, lon=0.0),
    "valid_timestamp": bronze_row(ts=datetime(1999, 12, 31)),
}


@pytest.fixture
def bronze(spark):
    rows = [bronze_row(tid="good"), *BAD_ROWS.values()]
    return spark.createDataFrame(rows, schema=BRONZE_POSITION_FIX_SCHEMA)


def test_every_rule_has_a_bad_row_test():
    assert set(BAD_ROWS) == set(SILVER_FIX_RULES)


def test_split_valid_keeps_only_the_good_row(bronze):
    valid, _ = split_valid(bronze, SILVER_FIX_RULES)

    assert [r.tid for r in valid.collect()] == ["good"]
    assert "failed_rules" not in valid.columns


def test_split_valid_tags_each_bad_row_with_its_rule(bronze):
    _, quarantined = split_valid(bronze, SILVER_FIX_RULES)

    failed = [set(r.failed_rules) for r in quarantined.collect()]
    for rule in SILVER_FIX_RULES:
        assert any(rule in f for f in failed), f"no row was quarantined for {rule}"


def test_null_latitude_is_tagged_has_coordinates(bronze):
    """The range check on a null is null (not false), so only the IS NOT NULL rule fires."""
    _, quarantined = split_valid(bronze, SILVER_FIX_RULES)

    row = quarantined.filter("latitude IS NULL").collect()[0]
    assert row.failed_rules == ["has_coordinates"]


def test_no_row_disappears(bronze):
    valid, quarantined = split_valid(bronze, SILVER_FIX_RULES)

    assert valid.count() + quarantined.count() == bronze.count()


def test_split_duplicates_keeps_lowest_tid(spark):
    rows = [
        bronze_row(tid="2"),
        bronze_row(tid="1"),
        bronze_row(tid="3", ts=datetime(2008, 10, 24)),
    ]
    df = spark.createDataFrame(rows, schema=BRONZE_POSITION_FIX_SCHEMA)

    kept, duplicates = split_duplicates(df, ["uid", "recorded_at_utc"], order_by="tid")

    assert sorted(r.tid for r in kept.collect()) == ["1", "3"]
    dup = duplicates.collect()
    assert [r.tid for r in dup] == ["2"]
    assert dup[0].failed_rules == ["duplicate"]
