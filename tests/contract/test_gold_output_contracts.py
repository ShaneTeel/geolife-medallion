"""Contract tests: extract/ output must match the gold StructTypes (offline).

applyInPandas(fn, schema=...) maps pandas columns to the schema, and a mismatch
only fails at runtime on Databricks. These tests catch it locally.
"""

import pandas as pd
from pyspark.sql.types import DoubleType, LongType, StringType, TimestampType

from geolife_medallion.extract import assign_locations, detect_staypoints, summarize_locations
from geolife_medallion.schemas import (
    CLUSTERED_STAYPOINT_SCHEMA,
    LOCATION_SCHEMA,
    STAYPOINT_SCHEMA,
)


def _assert_matches(df: pd.DataFrame, schema) -> None:
    assert list(df.columns) == schema.fieldNames()

    checks = {
        StringType: pd.api.types.is_string_dtype,
        DoubleType: pd.api.types.is_float_dtype,
        LongType: pd.api.types.is_integer_dtype,
        TimestampType: pd.api.types.is_datetime64_any_dtype,
    }
    for field in schema.fields:
        is_ok = checks[type(field.dataType)]
        assert is_ok(df[field.name]), f"{field.name}: {df[field.name].dtype} vs {field.dataType}"
        if not field.nullable:
            assert df[field.name].notna().all(), f"{field.name} is non-nullable but has nulls"


def test_detect_staypoints_matches_staypoint_schema(home_work_home):
    _assert_matches(detect_staypoints(home_work_home), STAYPOINT_SCHEMA)


def test_assign_locations_matches_clustered_staypoint_schema(home_work_home):
    _assert_matches(assign_locations(detect_staypoints(home_work_home)), CLUSTERED_STAYPOINT_SCHEMA)


def test_summarize_locations_matches_location_schema(home_work_home):
    clustered = assign_locations(detect_staypoints(home_work_home))
    _assert_matches(summarize_locations(clustered), LOCATION_SCHEMA)
