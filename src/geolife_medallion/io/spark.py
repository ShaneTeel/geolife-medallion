"""Get a Spark session that works both on Databricks and locally."""

import os

from pyspark.sql import SparkSession


def get_spark() -> SparkSession:
    """Return the right Spark session for where the code is running.

    On Databricks this is the session the job already has. Locally it is a
    Databricks Connect session on serverless compute.

    Returns:
        An active SparkSession.
    """
    if "DATABRICKS_RUNTIME_VERSION" in os.environ:
        return SparkSession.builder.getOrCreate()

    from databricks.connect import DatabricksSession
    return DatabricksSession.builder.serverless(True).getOrCreate()
