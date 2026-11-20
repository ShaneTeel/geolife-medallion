"""Unit tests for extract.staypoint_clusterer (pandas, offline)."""

import pandas as pd
import pytest

from geolife_medallion.extract import (
    LocationParams,
    assign_locations,
    detect_staypoints,
    summarize_locations,
)
from geolife_medallion.extract.staypoint_clusterer import LOCATION_COLUMNS


@pytest.fixture
def staypoints(home_work_home) -> pd.DataFrame:
    """Three staypoints: home, work, home."""
    return detect_staypoints(home_work_home)


def test_repeat_visits_share_a_location_and_single_visit_is_null(staypoints):
    result = assign_locations(staypoints)

    home_1, work, home_2 = result["location_id"].tolist()
    assert home_1 == home_2
    assert pd.notna(home_1)
    assert pd.isna(work)   # visited once: not a location, and null rather than DBSCAN's -1


def test_assign_keeps_every_staypoint(staypoints):
    """Unclustered staypoints are kept with a null location_id, never dropped."""
    result = assign_locations(staypoints)

    assert len(result) == len(staypoints)
    assert result["staypoint_id"].tolist() == staypoints["staypoint_id"].tolist()


def test_fewer_staypoints_than_min_k_are_all_null(staypoints):
    result = assign_locations(staypoints.head(1), LocationParams(min_k=2))

    assert result["location_id"].isna().all()


def test_assign_does_not_modify_its_input(staypoints):
    before = staypoints.copy()

    assign_locations(staypoints)

    pd.testing.assert_frame_equal(staypoints, before)


def test_summarize_builds_one_row_per_location(staypoints):
    clustered = assign_locations(staypoints)

    result = summarize_locations(clustered)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["n_stays"] == 2
    assert row["first_seen"] == clustered["arrived"].iloc[0]
    assert row["last_seen"] == clustered["departed"].iloc[2]


def test_summarize_n_stays_matches_member_count(staypoints):
    clustered = assign_locations(staypoints)

    result = summarize_locations(clustered)

    members = clustered.dropna(subset=["location_id"]).groupby("location_id").size()
    assert result.set_index("location_id")["n_stays"].to_dict() == members.to_dict()


def test_summarize_with_no_locations_returns_empty_frame_with_schema_columns(staypoints):
    clustered = assign_locations(staypoints.head(1))   # one staypoint -> no locations

    result = summarize_locations(clustered)

    assert result.empty
    assert list(result.columns) == LOCATION_COLUMNS
