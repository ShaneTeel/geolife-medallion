"""Unit tests for io.audit.audit_run (offline).

The table write is replaced with a stand-in that captures rows, so these tests
check the behavior (what gets recorded, and that errors still propagate)
without Spark. That the row fits AUDIT_RUN_SCHEMA in real Spark is tested in
tests/integration/test_audit_spark.py.
"""

import pytest

from geolife_medallion.io import audit
from geolife_medallion.io.audit import audit_run
from geolife_medallion.schemas import AUDIT_RUN_SCHEMA


@pytest.fixture
def recorded(monkeypatch) -> list[dict]:
    """Capture audit rows instead of writing them."""
    rows: list[dict] = []
    monkeypatch.setattr(audit, "_record", lambda spark, table, row: rows.append(row))
    return rows


def test_success_records_one_succeeded_row_with_counts(recorded):
    with audit_run(None, "cat.sch.audit_runs", "123", "silver") as row_counts:
        row_counts["silver_position_fixes"] = 10

    assert len(recorded) == 1
    row = recorded[0]
    assert (row["run_id"], row["stage"], row["status"]) == ("123", "silver", "SUCCEEDED")
    assert row["row_counts"] == {"silver_position_fixes": 10}
    assert row["error"] is None
    assert row["started_at"] <= row["finished_at"]


def test_row_has_exactly_the_schema_columns(recorded):
    with audit_run(None, "t", "1", "bronze"):
        pass

    assert list(recorded[0]) == AUDIT_RUN_SCHEMA.fieldNames()


def test_failure_records_failed_row_and_reraises(recorded):
    with pytest.raises(RuntimeError, match="Row count mismatch"):
        with audit_run(None, "t", "1", "silver") as row_counts:
            row_counts["bronze_position_fixes"] = 5
            raise RuntimeError("Row count mismatch 5 vs. 4")

    row = recorded[0]
    assert row["status"] == "FAILED"
    assert row["error"] == "RuntimeError: Row count mismatch 5 vs. 4"
    assert row["row_counts"] == {"bronze_position_fixes": 5}   # counts gathered before the error


def test_long_error_messages_are_truncated(recorded):
    with pytest.raises(ValueError):
        with audit_run(None, "t", "1", "gold"):
            raise ValueError("x" * 10_000)

    assert len(recorded[0]["error"]) == audit._MAX_ERROR_CHARS


def test_broken_audit_write_does_not_fail_a_successful_stage(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("table unavailable")

    monkeypatch.setattr(audit, "create_table_if_missing", broken)

    with audit_run(None, "t", "1", "bronze"):
        pass   # no exception escapes


def test_broken_audit_write_does_not_hide_the_stage_error(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("table unavailable")

    monkeypatch.setattr(audit, "create_table_if_missing", broken)

    with pytest.raises(KeyError):   # the stage's own error, not the OSError
        with audit_run(None, "t", "1", "bronze"):
            raise KeyError("missing column")
