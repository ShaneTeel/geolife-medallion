"""Table structure (columns and types) for position-fix tables.

Structure only. Value rules live in rules.py.
"""
from pyspark.sql.types import (
    DoubleType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# Bronze: everything as received. Coordinates and timestamp are nullable on
# purpose -- bad rows are kept as evidence and quarantined later in silver.
BRONZE_POSITION_FIX_SCHEMA = StructType(
    [
        StructField("uid", StringType(), False),
        StructField("tid", StringType(), False),
        StructField("latitude", DoubleType(), True),
        StructField("longitude", DoubleType(), True),
        StructField("recorded_at_utc", TimestampType(), True),
        StructField("source_file", StringType(), False),
        StructField("ingested_at", TimestampType(), False),
        StructField("run_id", StringType(), False),
    ]
)

# Silver: same columns as bronze. Silver differs in VALUES, enforced by
# SILVER_FIX_RULES in rules.py.
SILVER_POSITION_FIX_SCHEMA = BRONZE_POSITION_FIX_SCHEMA