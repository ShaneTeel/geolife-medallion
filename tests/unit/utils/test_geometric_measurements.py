"""Unit tests for utils.math.geometric_measurements (offline)."""

import pytest

from geolife_medallion.utils import (
    center_of_mass,
    centermost_point,
    great_circle_distance,
    radius_of_gyration,
)

# One degree of arc on a 6,371 km sphere.
ONE_DEGREE_M = 111_194.93


def test_distance_to_self_is_zero():
    assert great_circle_distance((39.98, 116.31), (39.98, 116.31)) == 0


def test_one_degree_along_the_equator():
    assert great_circle_distance((0, 0), (0, 1)) == pytest.approx(ONE_DEGREE_M, rel=1e-4)


def test_distance_is_symmetric():
    a, b = (39.98, 116.31), (40.00, 116.35)
    assert great_circle_distance(a, b) == pytest.approx(great_circle_distance(b, a))


def test_center_of_mass_of_symmetric_points_is_the_middle():
    lat, lon = center_of_mass([0, 0], [-1, 1])
    assert lat == pytest.approx(0, abs=1e-9)
    assert lon == pytest.approx(0, abs=1e-9)


def test_weights_pull_the_center_of_mass():
    _, lon = center_of_mass([0, 0], [-1, 1], weights=[1, 3])
    assert lon > 0


def test_radius_of_gyration_of_repeated_point_is_zero():
    assert radius_of_gyration([39.98, 39.98], [116.31, 116.31]) == pytest.approx(0, abs=1e-6)


def test_radius_of_gyration_of_two_points_is_half_their_distance():
    rog = radius_of_gyration([0, 0], [0, 1])
    assert rog == pytest.approx(ONE_DEGREE_M / 2, rel=1e-3)


def test_centermost_point_returns_an_input_point():
    cluster = [(0.0, 0.0), (0.0, 0.001), (0.0, 0.010)]
    assert centermost_point(cluster) in cluster
