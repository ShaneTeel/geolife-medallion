"""SQL objects job: create or replace the SQL functions and views in the schema.

Run by the `sql_objects` task in resources/geolife_medallion.job.yml through the
`sql-objects` entry point in pyproject.toml. It runs last, because views
can only be created once the tables they read exist.

The objects themselves are .sql files in src/geolife_medallion/sql/; see io/sql.py.
"""

import argparse
import os

from geolife_medallion.io import apply_sql_objects, audit_run, get_spark
from geolife_medallion.utils import get_logger, setup_logging

logger = get_logger(__name__)


def main() -> None:
    """Apply every function and view .sql file to the target schema.

    Command-line arguments:

    - `--catalog`: Unity Catalog catalog name.
    - `--schema`: Schema within the catalog.
    - `--run-id`: Job run ID, recorded in audit_runs (default `local`).
    """
    setup_logging(log_to_file="DATABRICKS_RUNTIME_VERSION" not in os.environ)

    parser = argparse.ArgumentParser(description="apply SQL functions and views")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--run-id", default="local")
    args = parser.parse_args()

    spark = get_spark()
    prefix = f"{args.catalog}.{args.schema}"

    # Views aren't tables, so there are no row counts; the audit row records success or failure.
    with audit_run(spark, f"{prefix}.audit_runs", args.run_id, "sql_objects"):
        applied = apply_sql_objects(spark, args.catalog, args.schema)
        logger.info(f"Applied {len(applied)} SQL objects: {', '.join(applied)}")


if __name__ == "__main__":
    main()
