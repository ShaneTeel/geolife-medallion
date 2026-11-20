"""Table structure for audit_runs: one row per pipeline stage run.

Generic across data sources: row counts are a map of table name -> row count,
so adding or renaming tables never changes this schema.
"""

from pyspark.sql.types import (
    LongType,
    MapType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

AUDIT_RUN_SCHEMA = StructType(
    [
        StructField("run_id", StringType(), False),       # {{job.run_id}}; "local" locally
        StructField("stage", StringType(), False),        # e.g. bronze, silver, gold
        StructField("status", StringType(), False),       # SUCCEEDED or FAILED
        StructField("started_at", TimestampType(), False),
        StructField("finished_at", TimestampType(), False),
        StructField("row_counts", MapType(StringType(), LongType()), False),
        StructField("error", StringType(), True),         # null when SUCCEEDED
    ]
)
