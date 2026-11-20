"""Bronze job: raw .plt files in the landing volume -> bronze_position_fixes.

Run by the `bronze` task in resources/geolife_medallion.job.yml through the
`geolife-bronze` entry point in pyproject.toml.
"""
import argparse
import os

from geolife_medallion.io import (
    audit_run,
    create_table_if_missing,
    get_spark,
    read_geolife,
    require_schema,
    write_table,
)
from geolife_medallion.schemas import BRONZE_POSITION_FIX_SCHEMA
from geolife_medallion.utils import get_logger, setup_logging

logger = get_logger(__name__)

def main() -> None:
    """Read every raw .plt file in the landing volume and write bronze_position_fixes.

    Command-line arguments:

    - `--catalog`: Unity Catalog catalog name.
    - `--schema`: Schema within the catalog.
    - `--run-id`: Job run ID, recorded on every row and in audit_runs (default `local`).
    """
    setup_logging(log_to_file="DATABRICKS_RUNTIME_VERSION" not in os.environ)

    parser = argparse.ArgumentParser(description="raw .plt files -> bronze")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--run-id", default="local")
    args = parser.parse_args()

    spark = get_spark()
    source = f"/Volumes/{args.catalog}/{args.schema}/landing/geolife/"
    target = f"{args.catalog}.{args.schema}.bronze_position_fixes"
    audit_table = f"{args.catalog}.{args.schema}.audit_runs"

    with audit_run(spark, audit_table, args.run_id, "bronze") as row_counts:
        # 1. Read every .plt file under the landing folder
        bronze = read_geolife(spark, source, args.run_id)

        # 2. Check structure, make sure the table exists with our schema, write
        require_schema(bronze, BRONZE_POSITION_FIX_SCHEMA, "bronze output")
        create_table_if_missing(spark, target, BRONZE_POSITION_FIX_SCHEMA)
        write_table(bronze, target)

        row_counts["bronze_position_fixes"] = spark.table(target).count()
        logger.info(f"Wrote {row_counts['bronze_position_fixes']} rows to {target}")


if __name__ == "__main__":
    main()