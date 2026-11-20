"""Create the SQL functions and views kept as .sql files in the package's `sql/` folder.

Bundles can't manage functions or views (they're catalog objects created by SQL),
so the pipeline applies them itself, as the job's last task:

```text
sql/
  functions/*.sql   applied first, so views can use them
  views/*.sql       applied second
```

Conventions for the .sql files:

- One `CREATE OR REPLACE ...` statement per file, so re-running is always safe.
- No catalog or schema names: the current catalog and schema are set before the
  files run, so the same file works in dev and prod (and in the SQL editor).
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from pyspark.sql import SparkSession

from geolife_medallion.utils import get_logger

logger = get_logger(__name__)

# Applied in this order: functions before the views that may use them.
SQL_FOLDERS = ("functions", "views")


def read_sql_file(file: Path) -> list[str]:
    """Read a .sql file and split it into individual statements.

    Full-line `--` comments and blank lines are dropped first, then the text is
    split on `;`. A `;` inside a string literal would also split, which is one
    reason for the one-statement-per-file convention.

    Args:
        file: Path to the .sql file.

    Returns:
        The non-empty SQL statements, in file order.
    """
    lines = file.read_text(encoding="utf-8").splitlines()
    code = "\n".join(line for line in lines if not line.strip().startswith("--"))
    return [statement.strip() for statement in code.split(";") if statement.strip()]


def sql_files(root: Path | None = None) -> list[Path]:
    """List the .sql files to apply, in the order they must run.

    Args:
        root: Folder containing `functions/` and `views/`. Defaults to the
            package's own `sql/` folder (shipped inside the wheel).

    Returns:
        Function files, then view files, each group sorted by file name.
    """
    root = root or Path(str(resources.files("geolife_medallion") / "sql"))
    return [path for folder in SQL_FOLDERS for path in sorted((root / folder).glob("*.sql"))]


def apply_sql_objects(
    spark: SparkSession, catalog: str, schema: str, root: Path | None = None
) -> list[str]:
    """Run every function and view file against `catalog.schema`.

    Args:
        spark: Active SparkSession.
        catalog: Catalog the objects are created in.
        schema: Schema the objects are created in.
        root: Folder containing `functions/` and `views/`; see `sql_files`.

    Returns:
        The names (file stems) of the applied files, in order.
    """
    spark.catalog.setCurrentCatalog(catalog)
    spark.catalog.setCurrentDatabase(schema)

    applied = []
    for path in sql_files(root):
        for statement in read_sql_file(path):
            spark.sql(statement)
        logger.info(f"Applied {path.parent.name}/{path.name} in {catalog}.{schema}")
        applied.append(path.stem)
    return applied
