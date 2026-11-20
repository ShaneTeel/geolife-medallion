"""Gold job: silver fixes -> gold_staypoints and gold_locations.

Run by the `gold` task in resources/geolife_medallion.job.yml through the
`geolife-gold` entry point in pyproject.toml.

The per-user algorithms are plain pandas functions in extract/. Spark runs
them for every user in parallel with groupBy("uid").applyInPandas(...).
"""

import argparse
import os

import pandas as pd

from geolife_medallion.extract import (
    LocationParams,
    StayPointParams,
    assign_locations,
    detect_staypoints,
    summarize_locations,
)
from geolife_medallion.io import (
    audit_run,
    create_table_if_missing,
    get_spark,
    read_table,
    write_table,
)
from geolife_medallion.schemas import (
    CLUSTERED_STAYPOINT_SCHEMA,
    LOCATION_SCHEMA,
    STAYPOINT_SCHEMA,
)
from geolife_medallion.utils import get_logger, setup_logging

logger = get_logger(__name__)

def main() -> None:
    """Build gold_staypoints and gold_locations from silver_position_fixes.

    Command-line arguments:

    - `--catalog`: Unity Catalog catalog name.
    - `--schema`: Schema within the catalog.
    - `--run-id`: Job run ID, recorded in audit_runs (default `local`).
    """
    setup_logging(log_to_file="DATABRICKS_RUNTIME_VERSION" not in os.environ)

    parser = argparse.ArgumentParser(description="silver -> gold")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--run-id", default="local")
    args = parser.parse_args()

    spark = get_spark()
    prefix = f"{args.catalog}.{args.schema}"
    staypoints_table = f"{prefix}.gold_staypoints"
    locations_table = f"{prefix}.gold_locations"

    sp_params = StayPointParams()
    loc_params = LocationParams()
    logger.info(f"Staypoint params: {sp_params}  Location params: {loc_params}")

    with audit_run(spark, f"{prefix}.audit_runs", args.run_id, "gold") as row_counts:
        # 1. Read only the columns the algorithms need
        fixes = read_table(spark, f"{prefix}.silver_position_fixes").select(
            "uid", "latitude", "longitude", "recorded_at_utc"
        )
        row_counts["silver_position_fixes"] = fixes.count()

        def _detect(fixes: pd.DataFrame) -> pd.DataFrame:
            return detect_staypoints(fixes, sp_params)

        def _assign(staypoints: pd.DataFrame) -> pd.DataFrame:
            return assign_locations(staypoints, loc_params)

        # 2. Detect staypoints per user, then assign each to a location per user
        staypoints = fixes.groupBy("uid").applyInPandas(_detect, schema=STAYPOINT_SCHEMA)
        clustered = staypoints.groupBy("uid").applyInPandas(
            _assign, schema=CLUSTERED_STAYPOINT_SCHEMA
        )

        create_table_if_missing(spark, staypoints_table, CLUSTERED_STAYPOINT_SCHEMA)
        write_table(clustered, staypoints_table)

        # 3. Build locations from the table just written (avoids recomputing the steps above)
        locations = (
            read_table(spark, staypoints_table)
            .groupBy("uid")
            .applyInPandas(summarize_locations, schema=LOCATION_SCHEMA)
        )
        create_table_if_missing(spark, locations_table, LOCATION_SCHEMA)
        write_table(locations, locations_table)

        # 4. Report
        n_sp = spark.table(staypoints_table).count()
        n_unclustered = spark.table(staypoints_table).filter("location_id IS NULL").count()
        n_loc = spark.table(locations_table).count()
        row_counts.update(gold_staypoints=n_sp, gold_locations=n_loc)
        logger.info(f"staypoints={n_sp} unclustered={n_unclustered} locations={n_loc}")


if __name__ == "__main__":
    main()