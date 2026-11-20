"""Read raw GeoLife .plt files into a bronze-shaped Spark DataFrame.

Spark version of the original pandas GeoLifeReader. Reads every .plt file
under `path` in one pass (no per-file loop), and takes the user ID and
trajectory ID from the file path.

Expected layout under `path` (GeoLife's own structure):
    <path>/000/Trajectory/20081023025304.plt
    <path>/001/Trajectory/...
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from geolife_medallion.schemas import PLT_RAW_SCHEMA

# .plt data rows have the time "HH:MM:SS" in the 7th field; the 6 header lines don't.
_DATA_ROW = r"^\d{2}:\d{2}:\d{2}$"

def read_geolife(spark: SparkSession, path: str, run_id: str) -> DataFrame:
    """Read all GeoLife .plt files under `path`.

    Values are NOT validated here; bronze keeps bad rows as evidence, and
    silver quarantines them.

    Args:
        spark: Active SparkSession.
        path: Folder containing the user folders, e.g. `/Volumes/<cat>/<schema>/landing/geolife/`.
        run_id: ID of the job run, recorded on every row for lineage.

    Returns:
        One row per position fix, with the columns of BRONZE_POSITION_FIX_SCHEMA.
    """
    raw = (
        spark.read.schema(PLT_RAW_SCHEMA)
        .option("recursiveFileLookup", True)
        .option("pathGlobFilter", "*.plt")
        .csv(path)
    )

    file_path = F.col("_metadata.file_path")

    return raw.filter(F.col("_c6").rlike(_DATA_ROW)).select(
        F.regexp_extract(file_path, r"/(\d{3})/Trajectory/", 1).alias("uid"),
        F.regexp_extract(file_path, r"/(\d+)\.plt$", 1).alias("tid"),
        F.col("_c0").cast("double").alias("latitude"),
        F.col("_c1").cast("double").alias("longitude"),
        F.to_timestamp(F.concat_ws(" ", "_c5", "_c6"), "yyyy-MM-dd HH:mm:ss").alias(
            "recorded_at_utc"
        ),
        file_path.alias("source_file"),
        F.current_timestamp().alias("ingested_at"),
        F.lit(run_id).alias("run_id"),
    )