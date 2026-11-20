"""Read, write, create, and check Unity Catalog tables."""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import StructType

from geolife_medallion.utils import get_logger

logger = get_logger(__name__)

def read_table(spark: SparkSession, name: str) -> DataFrame:
    """Read a table by its full name.

    Args:
        spark: Active SparkSession.
        name: Three-part table name, e.g. `workspace.svteel1106.bronze_position_fixes`.

    Returns:
        The table as a DataFrame.
    """
    logger.info(f"Reading {name} table...")
    return spark.table(name)


def write_table(df: DataFrame, name: str, mode: str = "overwrite") -> None:
    """Write a DataFrame to a table.

    Delta rejects the write if the columns or types don't match the table.

    Args:
        df: Rows to write.
        name: Three-part table name.
        mode: Spark save mode, e.g. `overwrite` or `append`.
    """
    logger.info(f"Writing {name} table with mode == {mode}...")
    df.write.mode(mode).saveAsTable(name)


def create_table_if_missing(spark: SparkSession, name: str, schema: StructType) -> None:
    """Create an empty table with a fixed schema if it doesn't exist yet.

    Call this before the first write so the table schema is decided by us,
    not inferred from whatever the first write happens to contain.

    Args:
        spark: Active SparkSession.
        name: Three-part table name.
        schema: Columns and types the table must have.
    """
    if not spark.catalog.tableExists(name):
        logger.info(f"Creating {name} table under {schema} schema...")
        spark.catalog.createTable(name, schema=schema)


def require_schema(df: DataFrame, schema: StructType, label: str) -> None:
    """Fail fast if a DataFrame is missing columns or has the wrong types.

    Extra columns in `df` are allowed; nullability is not checked.

    Args:
        df: DataFrame to check.
        schema: Expected columns and types.
        label: Name used in the error message, e.g. `bronze input`.

    Raises:
        ValueError: If any expected column is missing or has a different type.
    """
    expected = {f.name: f.dataType for f in schema}
    actual = {f.name: f.dataType for f in df.schema}

    missing = sorted(set(expected) - set(actual))
    wrong = sorted(n for n in expected if n in actual and actual[n] != expected[n])

    if missing or wrong:
        raise ValueError(f"{label}: missing={missing} wrong_type={wrong}")
