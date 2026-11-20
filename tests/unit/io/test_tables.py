"""Unit tests for io.tables.require_schema (offline).

require_schema only reads `df.schema`, so a stand-in object is enough; no Spark needed.
"""

from types import SimpleNamespace

import pytest
from pyspark.sql.types import DoubleType, StringType, StructField, StructType

from geolife_medallion.io import require_schema

EXPECTED = StructType(
    [StructField("uid", StringType()), StructField("latitude", DoubleType())]
)


def fake_df(*fields: StructField) -> SimpleNamespace:
    return SimpleNamespace(schema=StructType(list(fields)))


def test_matching_schema_passes():
    require_schema(fake_df(*EXPECTED.fields), EXPECTED, "test")


def test_extra_columns_are_allowed():
    df = fake_df(*EXPECTED.fields, StructField("extra", StringType()))

    require_schema(df, EXPECTED, "test")


def test_missing_column_raises_with_its_name():
    df = fake_df(StructField("uid", StringType()))

    with pytest.raises(ValueError, match=r"missing=\['latitude'\]"):
        require_schema(df, EXPECTED, "test")


def test_wrong_type_raises_with_its_name():
    df = fake_df(StructField("uid", StringType()), StructField("latitude", StringType()))

    with pytest.raises(ValueError, match=r"wrong_type=\['latitude'\]"):
        require_schema(df, EXPECTED, "test")


def test_error_message_includes_label():
    with pytest.raises(ValueError, match="bronze input"):
        require_schema(fake_df(), EXPECTED, "bronze input")
