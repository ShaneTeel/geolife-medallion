"""Split rows into kept and quarantined rows, recording why each row was rejected.

- `split_valid`: row rules (SQL conditions checked on each row alone).
- `split_duplicates`: uniqueness on a key (rows compared with each other).

Both are generic; the rules themselves live in `schemas/rules.py`.
"""

from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from geolife_medallion.utils import get_logger

logger = get_logger(__name__)


def split_valid(df: DataFrame, rules: dict[str, str]) -> tuple[DataFrame, DataFrame]:
    """Check every row against every rule and split into valid and quarantined rows.

    A rule whose condition evaluates to null does not fail the row, which is
    why the rules need explicit `IS NOT NULL` checks.

    Args:
        df: Input rows.
        rules: Mapping of rule name -> SQL condition that a valid row makes TRUE.

    Returns:
        A `(valid, quarantined)` tuple. `valid` has the columns of `df`;
            `quarantined` adds `failed_rules`, the names of the rules each row broke.
    """
    failed = F.array_compact(
        F.array(*[F.when(~F.expr(cond), F.lit(name)) for name, cond in rules.items()])
    )

    tagged = df.withColumn("failed_rules", failed)

    valid = tagged.filter(F.size("failed_rules") == 0).drop("failed_rules")
    quarantined = tagged.filter(F.size("failed_rules") > 0)

    n_quarantined = quarantined.count()
    logger.info(
        f"{n_quarantined} rows failed Silver Rule validation. "
        "Splitting off invalid for quarantine..."
    )
    return valid, quarantined


def split_duplicates(
    df: DataFrame, key: list[str], order_by: str
) -> tuple[DataFrame, DataFrame]:
    """Keep one row per key and return the others as quarantine rows.

    Within each group of rows sharing `key`, the row with the lowest `order_by`
    value is kept. The rest get `failed_rules = ["duplicate"]`, so they can be
    unioned with the output of `split_valid` instead of being silently dropped.

    Args:
        df: Input rows.
        key: Columns that together identify a unique row, e.g. `["uid", "recorded_at_utc"]`.
        order_by: Column that decides which row in a group is kept (lowest wins).

    Returns:
        A `(kept, duplicates)` tuple. `kept` has the columns of `df`;
            `duplicates` has those columns plus `failed_rules`.
    """
    w = Window.partitionBy(*key).orderBy(order_by)
    ranked = df.withColumn("_rank", F.row_number().over(w))

    kept = ranked.filter("_rank = 1").drop("_rank")
    duplicates = (
        ranked.filter("_rank > 1")
        .drop("_rank")
        .withColumn("failed_rules", F.array(F.lit("duplicate")))
    )
    n_duplicates = duplicates.count()
    logger.info(f"{n_duplicates} duplicate rows. Splitting off duplicates for quarantine...")
    return kept, duplicates
