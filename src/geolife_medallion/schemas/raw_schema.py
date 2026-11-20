"""Structure of a raw GeoLife .plt file as read by Spark's CSV reader."""

from pyspark.sql.types import StringType, StructField, StructType

# The 7 comma-separated fields of a .plt data row, read as text first.
PLT_RAW_SCHEMA = StructType([StructField(f"_c{i}", StringType(), True) for i in range(7)])
