"""Detect staypoints in ONE user's position fixes (pandas).

Same algorithm as the original StayPointDetector class, rewritten as a
function plus a small settings object. It processes one user at a time;
the gold job runs it for every user in parallel with Spark's applyInPandas.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from geolife_medallion.schemas import STAYPOINT_SCHEMA
from geolife_medallion.utils import great_circle_distance, radius_of_gyration

# Output columns, in the same order as STAYPOINT_SCHEMA in schemas/gold_schemas.py.
STAYPOINT_COLUMNS = STAYPOINT_SCHEMA.fieldNames()

@dataclass(frozen=True)
class StayPointParams:
    """Staypoint detection thresholds.

    Attributes:
        distance_m: Max distance in meters from the anchor fix to still be "in place".
        time_min: Minimum duration of a stay, in minutes.
        gap_min: A time gap between fixes longer than this (minutes) ends the stay.
    """

    distance_m: float = 100.0
    time_min: float = 30.0
    gap_min: float = 60.0


def detect_staypoints(
    fixes: pd.DataFrame, params: StayPointParams = StayPointParams()
) -> pd.DataFrame:
    """Detect staypoints in one user's position fixes.

    Args:
        fixes: One user's silver fixes with columns `uid`, `latitude`,
            `longitude`, `recorded_at_utc`. Any row order.
        params: Detection thresholds.

    Returns:
        One row per staypoint with STAYPOINT_COLUMNS. Empty (with the right
            columns) if no staypoints were found.
    """
    if fixes.empty:
        return pd.DataFrame(columns=STAYPOINT_COLUMNS)

    # applyInPandas does not guarantee row order, so sort here.
    fixes = fixes.sort_values("recorded_at_utc").reset_index(drop=True)
    lats = fixes["latitude"].to_numpy()
    lons = fixes["longitude"].to_numpy()
    times = fixes["recorded_at_utc"].to_numpy()
    n = len(fixes)

    staypoints = []
    i = 0
    while i < n:
        j = i + 1
        while j < n:
            if j > i + 1:
                gap = _minutes(times[j] - times[j - 1])
                if gap > params.gap_min:
                    if _minutes(times[j - 1] - times[i]) >= params.time_min:
                        staypoints.append(_make_staypoint(fixes.iloc[i:j]))
                    i = j
                    break

            distance = great_circle_distance((lats[i], lons[i]), (lats[j], lons[j]))
            if distance >= params.distance_m:
                if _minutes(times[j] - times[i]) >= params.time_min:
                    staypoints.append(_make_staypoint(fixes.iloc[i:j]))
                i = j
                break
            j += 1

        if j == n:
            if _minutes(times[-1] - times[i]) >= params.time_min:
                staypoints.append(_make_staypoint(fixes.iloc[i:]))
            break

    return pd.DataFrame(staypoints, columns=STAYPOINT_COLUMNS)


def _make_staypoint(records: pd.DataFrame) -> dict:
    """Summarize the consecutive fixes of one stay into a STAYPOINT_SCHEMA row."""
    arrived = records["recorded_at_utc"].iloc[0]
    uid = records["uid"].iloc[0]
    return {
        "uid": uid,
        "staypoint_id": f"{uid}-{pd.Timestamp(arrived):%Y%m%dT%H%M%S}",   # stable across reruns
        "latitude": records["latitude"].mean(),
        "longitude": records["longitude"].mean(),
        "arrived": arrived,
        "departed": records["recorded_at_utc"].iloc[-1],
        "n_fixes": len(records),
        "radius_m": float(
            radius_of_gyration(records["latitude"].tolist(), records["longitude"].tolist())
        ),
    }


def _minutes(td: np.timedelta64) -> float:
    """Convert a numpy timedelta to minutes."""
    return td / np.timedelta64(1, "m")