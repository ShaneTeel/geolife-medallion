"""Integration test: an audit row converts to AUDIT_RUN_SCHEMA in real Spark (needs --databricks).

No table is written; this only checks the dict -> DataFrame conversion that
io.audit._record relies on (the map column and timezone-aware timestamps).
"""

from datetime import UTC, datetime

from geolife_medallion.io.audit import _audit_row
from geolife_medallion.schemas import AUDIT_RUN_SCHEMA


def test_audit_row_converts_to_schema(spark):
    row = _audit_row(
        "123", "silver", "SUCCEEDED", datetime.now(UTC), {"silver_position_fixes": 10}, None
    )

    df = spark.createDataFrame([row], schema=AUDIT_RUN_SCHEMA)

    result = df.collect()[0]
    assert result.row_counts == {"silver_position_fixes": 10}
    assert result.status == "SUCCEEDED"
    assert result.started_at <= result.finished_at
