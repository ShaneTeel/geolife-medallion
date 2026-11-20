"""Table structure for gold tables.

Also used as the output schema for applyInPandas, so column names, order,
and types must match the DataFrames the extract functions return.
"""

from pyspark.sql.types import (
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

STAYPOINT_SCHEMA = StructType(
    [
        StructField("uid", StringType(), False),
        StructField("staypoint_id", StringType(), False),
        StructField("latitude", DoubleType(), False),
        StructField("longitude", DoubleType(), False),
        StructField("arrived", TimestampType(), False),
        StructField("departed", TimestampType(), False),
        StructField("n_fixes", LongType(), False),
        StructField("radius_m", DoubleType(), False),
    ]
)

# gold_staypoints: staypoints plus their location (null = not part of a location).
CLUSTERED_STAYPOINT_SCHEMA = StructType(
    STAYPOINT_SCHEMA.fields + [StructField("location_id", LongType(), True)]
)

# gold_locations: one row per location. Key: (uid, location_id).
LOCATION_SCHEMA = StructType(
    [
        StructField("uid", StringType(), False),
        StructField("location_id", LongType(), False),
        StructField("latitude", DoubleType(), False),
        StructField("longitude", DoubleType(), False),
        StructField("first_seen", TimestampType(), False),
        StructField("last_seen", TimestampType(), False),
        StructField("n_stays", LongType(), False),
        StructField("radius_m", DoubleType(), False),
    ]
)