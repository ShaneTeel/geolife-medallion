"""Silver job: bronze -> silver + quarantine.

Run by the `silver` task in resources/geolife_medallion.job.yml through the
`geolife-silver` entry point in pyproject.toml.
"""
import argparse
import os

from geolife_medallion.io import (
    audit_run,
    create_table_if_missing,
    get_spark,
    read_table,
    require_schema,
    write_table,
)
from geolife_medallion.preprocess import split_duplicates, split_valid
from geolife_medallion.schemas import (
    BRONZE_POSITION_FIX_SCHEMA,
    SILVER_FIX_KEEP_LOWEST,
    SILVER_FIX_KEY,
    SILVER_FIX_RULES,
    SILVER_POSITION_FIX_SCHEMA,
)
from geolife_medallion.utils import get_logger, setup_logging

logger = get_logger(__name__)

def main() -> None:
    """Validate and deduplicate bronze fixes into silver and quarantine tables.

    Writes `silver_position_fixes` and `quarantine_position_fixes`.

    Command-line arguments:

    - `--catalog`: Unity Catalog catalog name.
    - `--schema`: Schema within the catalog.
    - `--run-id`: Job run ID, recorded in audit_runs (default `local`).

    Raises:
        ValueError: If the bronze table does not match BRONZE_POSITION_FIX_SCHEMA.
        RuntimeError: If bronze rows != silver rows + quarantined rows.
    """
    setup_logging(log_to_file="DATABRICKS_RUNTIME_VERSION" not in os.environ)

    parser = argparse.ArgumentParser(description="bronze -> silver")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--run-id", default="local")
    args = parser.parse_args()

    spark = get_spark()
    prefix = f"{args.catalog}.{args.schema}"
    silver_table = f"{prefix}.silver_position_fixes"
    quarantine_table = f"{prefix}.quarantine_position_fixes"

    with audit_run(spark, f"{prefix}.audit_runs", args.run_id, "silver") as row_counts:
        # 1. Read bronze and check its STRUCTURE (input contract)
        bronze = read_table(spark, f"{prefix}.bronze_position_fixes")
        require_schema(bronze, BRONZE_POSITION_FIX_SCHEMA, "bronze input")

        # 2. Make sure the silver table exists with OUR schema (output contract)
        create_table_if_missing(spark, silver_table, SILVER_POSITION_FIX_SCHEMA)

        # 3. Apply the VALUE rules
        valid, quarantined = split_valid(bronze, SILVER_FIX_RULES)

        # 4. Apply the UNIQUENESS rule (key + tie-breaker in rules.py); duplicates are
        #    quarantined with a reason instead of silently dropped.
        silver, duplicates = split_duplicates(
            valid, SILVER_FIX_KEY, order_by=SILVER_FIX_KEEP_LOWEST
        )
        quarantined = quarantined.unionByName(duplicates)

        # 5. Write both outputs (Delta checks structure on write)
        write_table(silver, silver_table)
        write_table(quarantined, quarantine_table)

        # 6. Reconcile: every bronze row was either kept or quarantined
        n_bronze = bronze.count()
        n_silver = silver.count()
        n_quarantined = quarantined.count()
        row_counts.update(
            bronze_position_fixes=n_bronze,
            silver_position_fixes=n_silver,
            quarantine_position_fixes=n_quarantined,
        )
        logger.info(f"bronze={n_bronze} silver={n_silver} quarantined={n_quarantined}")
        if n_bronze != n_silver + n_quarantined:
            raise RuntimeError(
                f"Row count mismatch {n_bronze} vs. {n_silver + n_quarantined}: "
                "some rows were neither kept nor quarantined"
            )


if __name__ == "__main__":
    main()