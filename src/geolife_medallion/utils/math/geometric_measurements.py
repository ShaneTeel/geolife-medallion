"""Geospatial mobility and distance measurements.

Functions for human mobility metrics such as radius of gyration, center of
mass, and great-circle distance between geographic coordinates.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from geopy.distance import great_circle
from shapely.geometry import MultiPoint

from geolife_medallion.utils import get_logger

logger = get_logger(__name__)

def radius_of_gyration(lat: list, lon: list, weights: list | None = None) -> float:
    """Compute the (optionally weighted) radius of gyration of a set of points.

    The radius of gyration is the root-mean-square distance of the points
    from their center of mass: the characteristic spatial scale of a
    trajectory. Without weights, duplicate coordinates are collapsed and each
    unique point counts once.

    Args:
        lat: Latitudes in decimal degrees.
        lon: Longitudes in decimal degrees.
        weights: Weight per point (e.g. visit count or dwell duration).
            None means unweighted, over unique points.

    Returns:
        The radius of gyration in meters.
    """
    if weights is None:
        unique_points = list(set(zip(lat, lon, strict=True)))
        lat = [point[0] for point in unique_points]
        lon = [point[1] for point in unique_points]
        weights = [1] * len(lat)

    cm = center_of_mass(lat, lon, weights)
    total_weight = sum(weights)

    squared_distances = [
        great_circle_distance((lt, ln), cm) ** 2 * w
        for lt, ln, w in zip(lat, lon, weights, strict=True)
    ]
    return np.sqrt(sum(squared_distances) / total_weight)

def great_circle_distance(pt1: tuple, pt2: tuple) -> float:
    """Compute the great-circle distance between two points (haversine formula).

    Assumes a spherical earth with a radius of 6,371 km.

    Args:
        pt1: First point as (latitude, longitude) in decimal degrees.
        pt2: Second point as (latitude, longitude) in decimal degrees.

    Returns:
        The distance between the points in meters.
    """
    lat1, lon1 = pt1
    lat2, lon2 = pt2

    R = 6371 # Radius in kms
    phi_1, phi_2 = np.radians(lat1), np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1) # Change in latitutde (in radians)
    delta_lambda = np.radians(lon2 - lon1) # Change in longitude (in radians)
    a = np.sin(delta_phi / 2)**2 + np.cos(phi_1) * np.cos(phi_2) * np.sin(delta_lambda / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    return R * c * 1000

def center_of_mass(lat: list, lon: list, weights: list | None = None) -> tuple[float, float]:
    """Compute the geographic center of mass of a set of points.

    Converts the coordinates to 3D Cartesian points on a unit sphere, takes
    the weighted average, and converts the result back to latitude/longitude.

    Args:
        lat: Latitudes in decimal degrees.
        lon: Longitudes in decimal degrees.
        weights: Weight per point (e.g. visit frequency or duration).
            None gives every point a weight of 1.

    Returns:
        The center of mass as (latitude, longitude) in decimal degrees.
    """
    if weights is None:
        weights = [1] * len(lat)

    total_weight = sum(weights)

    # Convert to radians
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)

    # Assuming a unit sphere (Radius = 1) for mean calc
    x = np.cos(lat_rad) * np.cos(lon_rad)
    y = np.cos(lat_rad) * np.sin(lon_rad)
    z = np.sin(lat_rad)

    # Compute Weighted Average
    avg_x = sum(x * weights) / total_weight
    avg_y = sum(y * weights) / total_weight
    avg_z = sum(z * weights) / total_weight

    # Convert back to Lat/Lon
    central_lon = np.arctan2(avg_y, avg_x)
    hyp = np.sqrt(avg_x**2 + avg_y**2)
    central_lat = np.arctan2(avg_z, hyp)

    return (np.degrees(central_lat), np.degrees(central_lon))

def centermost_point(cluster: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """Find the recorded point closest to a cluster's centroid.

    A geometric centroid can fall somewhere never visited (e.g. the middle of
    a lake); this returns the actual input point nearest to it instead.

    Args:
        cluster: Sequence of (latitude, longitude) points in decimal degrees.

    Returns:
        The input point, as (latitude, longitude), closest to the centroid.
    """
    centroid = (MultiPoint(cluster).centroid.x, MultiPoint(cluster).centroid.y)
    lat, lon = min(cluster, key=lambda point: great_circle(point, centroid).m)
    return (lat, lon)