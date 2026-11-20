"""Unit tests for extract.staypoint_detector (pandas, offline)."""

import pandas as pd
import pytest

from conftest import HOME, WORK, make_fixes
from geolife_medallion.extract import StayPointParams, detect_staypoints
from geolife_medallion.extract.staypoint_detector import STAYPOINT_COLUMNS


def test_empty_input_returns_empty_frame_with_schema_columns():
    empty = pd.DataFrame(columns=["uid", "latitude", "longitude", "recorded_at_utc"])

    result = detect_staypoints(empty)

    assert result.empty
    assert list(result.columns) == STAYPOINT_COLUMNS


def test_home_work_home_gives_three_staypoints(home_work_home):
    result = detect_staypoints(home_work_home)

    assert len(result) == 3
    assert result["arrived"].tolist() == [
        pd.Timestamp("2008-10-23 07:00"),
        pd.Timestamp("2008-10-23 08:30"),
        pd.Timestamp("2008-10-23 18:00"),
    ]
    assert result["n_fixes"].tolist() == [13, 13, 13]
    # Each stay is centered on where it happened (jitter is ~10 m).
    assert result["latitude"].iloc[1] == pytest.approx(WORK[0], abs=1e-3)
    assert result["latitude"].iloc[0] == pytest.approx(HOME[0], abs=1e-3)


def test_row_order_does_not_matter(home_work_home):
    """applyInPandas does not preserve order, so the function must sort itself."""
    shuffled = home_work_home.sample(frac=1, random_state=0)

    pd.testing.assert_frame_equal(detect_staypoints(shuffled), detect_staypoints(home_work_home))


def test_stay_shorter_than_time_min_is_ignored():
    fixes = pd.concat(
        [make_fixes(HOME, "2008-10-23 07:00", 20), make_fixes(WORK, "2008-10-23 07:25", 0)],
        ignore_index=True,
    )

    assert detect_staypoints(fixes, StayPointParams(time_min=30)).empty


def test_time_gap_longer_than_gap_min_splits_a_stay():
    """Same place, but a 90-minute recording gap: two stays, not one."""
    fixes = pd.concat(
        [make_fixes(HOME, "2008-10-23 07:00", 40), make_fixes(HOME, "2008-10-23 09:10", 40)],
        ignore_index=True,
    )

    result = detect_staypoints(fixes, StayPointParams(gap_min=60))

    assert len(result) == 2


def test_staypoint_id_is_uid_plus_arrival_time(home_work_home):
    """IDs are derived from the data, so reruns produce the same IDs."""
    result = detect_staypoints(home_work_home)

    assert result["staypoint_id"].iloc[0] == "000-20081023T070000"
    assert result["staypoint_id"].is_unique
