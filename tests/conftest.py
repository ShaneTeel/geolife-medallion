"""Pytest configuration for geolife-medallion.

Tests run OFFLINE by default. Any test that needs Spark (by requesting the
`spark` fixture, or by being marked `@pytest.mark.databricks`) is skipped unless
you pass --databricks, in which case it runs on Databricks via Databricks Connect.

    pytest                         # offline: smoke, unit, contract
    pytest --databricks            # everything, including Databricks tests
    pytest --databricks -m databricks   # only the Databricks tests

Test data is built in code (see `make_fixes` below), not loaded from files.
"""

import os

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Opt-in switch for Databricks tests
# ---------------------------------------------------------------------------
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--databricks",
        action="store_true",
        default=False,
        help="Run tests that need Databricks (Databricks Connect).",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-mark Spark tests as `databricks`, then skip them unless --databricks was given."""
    run_databricks = config.getoption("--databricks")
    skip_remote = pytest.mark.skip(reason="needs Databricks; rerun with --databricks")

    for item in items:
        # Any test that asks for Spark needs Databricks, even if someone forgot the marker.
        if "spark" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.databricks)

        if "databricks" in item.keywords and not run_databricks:
            item.add_marker(skip_remote)


# ---------------------------------------------------------------------------
# Spark: created lazily, once per test session, only if a test needs it
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def spark():
    """Remote SparkSession via Databricks Connect.

    Imported and created here (not at pytest startup), so offline runs never
    need credentials, network access, or databricks-connect installed.
    """
    from databricks.connect import DatabricksSession
    from databricks.sdk import WorkspaceClient

    # Fall back to serverless compute if no cluster is configured.
    conf = WorkspaceClient().config
    if not (conf.serverless_compute_id or conf.cluster_id or os.environ.get("SPARK_REMOTE")):
        os.environ["DATABRICKS_SERVERLESS_COMPUTE_ID"] = "auto"

    builder = DatabricksSession.builder
    if hasattr(builder, "validateSession"):   # Databricks Connect 15+: check version compatibility
        builder = builder.validateSession()
    return builder.getOrCreate()


# ---------------------------------------------------------------------------
# Synthetic GPS data for the extract/ algorithms (offline)
# ---------------------------------------------------------------------------
HOME = (39.9840, 116.3180)
WORK = (40.0000, 116.3500)   # about 3.3 km from HOME


def make_fixes(
    place: tuple[float, float], start: str, minutes: int, uid: str = "000", step_min: int = 5
) -> pd.DataFrame:
    """Fixes every `step_min` minutes at `place` (with ~10 m jitter) for `minutes` minutes."""
    times = pd.date_range(start, periods=minutes // step_min + 1, freq=f"{step_min}min")
    jitter = [0.0001 * ((i % 3) - 1) for i in range(len(times))]   # -0.0001, 0, +0.0001, ...
    return pd.DataFrame(
        {
            "uid": uid,
            "latitude": [place[0] + j for j in jitter],
            "longitude": [place[1] - j for j in jitter],
            "recorded_at_utc": times,
        }
    )


@pytest.fixture
def home_work_home() -> pd.DataFrame:
    """One user's day: 1 h at home, 1 h at work, 1 h back at home (silver-fix columns)."""
    return pd.concat(
        [
            make_fixes(HOME, "2008-10-23 07:00", 60),
            make_fixes(WORK, "2008-10-23 08:30", 60),
            make_fixes(HOME, "2008-10-23 18:00", 60),
        ],
        ignore_index=True,
    )
