"""
Record one row per pipeline stage run in the audit_runs table.

Usage in a job:

```python
with audit_run(spark, f"{prefix}.audit_runs", args.run_id, "silver") as row_counts:
    ...
    row_counts["silver_position_fixes"] = silver.count()
```

The row is appended when the block exits: SUCCEEDED if it finished, FAILED (with
the error message) if it raised. The original error is always re-raised, so the
job still fails.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from pyspark.sql import SparkSession

from geolife_medallion.schemas import AUDIT_RUN_SCHEMA
from geolife_medallion.utils import get_logger

from .tables import create_table_if_missing, write_table

logger = get_logger(__name__)

_MAX_ERROR_CHARS = 2000


@contextmanager
def audit_run(spark: SparkSession, table: str, run_id: str, stage: str) -> Iterator[dict[str, int]]:
    """Time a pipeline stage and append its outcome to the audit table.

    Args:
        spark: Active SparkSession.
        table: Three-part name of the audit table, e.g. `workspace.dev.audit_runs`.
            Created on first use.
        run_id: Job run ID shared by all stages of one run (`{{job.run_id}}`).
        stage: Name of the stage, e.g. `bronze`.

    Yields:
        An empty dict for the stage to fill with table name -> row count.

    Raises:
        Exception: Whatever the stage raised, unchanged, after the FAILED row is written.
    """
    row_counts: dict[str, int] = {}
    started_at = datetime.now(UTC)
    try:
        yield row_counts
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:_MAX_ERROR_CHARS]
        _record(spark, table, _audit_row(run_id, stage, "FAILED", started_at, row_counts, error))
        raise
    _record(spark, table, _audit_row(run_id, stage, "SUCCEEDED", started_at, row_counts, None))

def _audit_row(
    run_id: str,
    stage: str,
    status: str,
    started_at: datetime,
    row_counts: dict[str, int],
    error: str | None,
) -> dict[str, Any]:
    """Build one audit row with AUDIT_RUN_SCHEMA's columns."""
    return {
        "run_id": run_id,
        "stage": stage,
        "status": status,
        "started_at": started_at,
        "finished_at": datetime.now(UTC),
        "row_counts": dict(row_counts),
        "error": error
    }

def _record(spark: SparkSession, table: str, row: dict[str, Any]) -> None:
    """Append the row to the audit table; log, never raise, if that fails.

    A broken audit write must not fail a stage whose data was written, and must
    not hide the stage's own error.
    """
    try:
        create_table_if_missing(spark, table, AUDIT_RUN_SCHEMA)
        write_table(spark.createDataFrame([row], schema=AUDIT_RUN_SCHEMA), table, mode="append")
        logger.info(f"Audit: {row['stage']} {row['status']} {row['row_counts']}")
    except Exception:
        logger.exception(f"Could not write audit row to {table}: {row}")