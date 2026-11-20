"""Cluster ONE user's staypoints into locations (pandas).

Same DBSCAN approach as the original StayPointClusterer class, split into
two functions with one job each:

    assign_locations    staypoints -> staypoints + location_id   (gold_staypoints)
    summarize_locations staypoints with location_id -> locations  (gold_locations)

Unclustered staypoints keep location_id = null instead of being dropped.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from geolife_medallion.schemas import LOCATION_SCHEMA
from geolife_medallion.utils import centermost_point, radius_of_gyration

_KM_PER_RADIAN = 6371.0088

LOCATION_COLUMNS = LOCATION_SCHEMA.fieldNames()

@dataclass(frozen=True)
class LocationParams:
    """DBSCAN clustering settings.

    Attributes:
        eps_km: DBSCAN neighborhood radius, in kilometers.
        min_k: Minimum number of staypoints needed to form a location.
    """

    eps_km: float = 0.2
    min_k: int = 2


def assign_locations(
    staypoints: pd.DataFrame, params: LocationParams = LocationParams()
) -> pd.DataFrame:
    """Assign each of one user's staypoints to a location with DBSCAN.

    Args:
        staypoints: One user's staypoints with STAYPOINT_SCHEMA columns.
        params: Clustering settings.

    Returns:
        A copy of `staypoints` with an added nullable `location_id` column.
            Null means the staypoint is not part of any location.
    """
    out = staypoints.copy()

    if len(out) < params.min_k:
        out["location_id"] = pd.array([pd.NA] * len(out), dtype="Int64")
        return out

    coords = np.radians(out[["latitude", "longitude"]].to_numpy())
    model = DBSCAN(
        eps=params.eps_km / _KM_PER_RADIAN,
        min_samples=params.min_k,
        metric="haversine",
        algorithm="ball_tree",
    )
    labels = pd.Series(model.fit(coords).labels_, index=out.index)

    # DBSCAN marks noise as -1; store that as null, not as a fake location.
    out["location_id"] = labels.where(labels != -1).astype("Int64")
    return out


def summarize_locations(clustered: pd.DataFrame) -> pd.DataFrame:
    """Build one row per location from one user's clustered staypoints.

    Args:
        clustered: One user's staypoints with CLUSTERED_STAYPOINT_SCHEMA columns.
            Rows with a null `location_id` are ignored.

    Returns:
        One row per location with LOCATION_COLUMNS. Empty (with the right
            columns) if no staypoint belongs to a location.
    """
    members = clustered.dropna(subset=["location_id"])
    if members.empty:
        return pd.DataFrame(columns=LOCATION_COLUMNS)

    rows = []
    for location_id, group in members.groupby("location_id"):
        lat, lon = centermost_point(list(group[["latitude", "longitude"]].to_numpy()))
        rows.append({
            "uid": group["uid"].iloc[0],
            "location_id": int(location_id),
            "latitude": lat,
            "longitude": lon,
            "first_seen": group["arrived"].min(),
            "last_seen": group["departed"].max(),
            "n_stays": len(group),
            "radius_m": float(
                radius_of_gyration(group["latitude"].tolist(), group["longitude"].tolist())
            ),
        })
    return pd.DataFrame(rows, columns=LOCATION_COLUMNS)