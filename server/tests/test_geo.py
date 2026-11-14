"""Unit tests for :mod:`app.geo` (pure rectangle logic)."""

from __future__ import annotations

import math

import pytest

from app.geo import BoundingBox, RectangleError, normalize_rectangle


def test_corners_in_any_order_give_same_box() -> None:
    expected = BoundingBox(min_lat=18.0, min_lon=-100.0, max_lat=20.0, max_lon=-98.0)
    assert normalize_rectangle(18, -100, 20, -98) == expected
    assert normalize_rectangle(20, -98, 18, -100) == expected
    assert normalize_rectangle(18, -98, 20, -100) == expected
    assert normalize_rectangle(20, -100, 18, -98) == expected


def test_contains_is_inclusive_on_edges() -> None:
    box = normalize_rectangle(18, -100, 20, -98)
    assert box.contains(20, -98)
    assert box.contains(18, -100)
    assert box.contains(19, -100)
    assert not box.contains(20.00001, -99)


def test_geojson_bbox_order() -> None:
    assert normalize_rectangle(18, -100, 20, -98).as_geojson_bbox() == [-100, 18, -98, 20]


@pytest.mark.parametrize(
    ("corners", "parameter"),
    [
        ((91, -100, 20, -98), "lat1"),
        ((18, -181, 20, -98), "lon1"),
        ((18, -100, -90.5, -98), "lat2"),
        ((18, -100, 20, 180.1), "lon2"),
        ((math.nan, -100, 20, -98), "lat1"),
    ],
)
def test_out_of_range_coordinates(corners: tuple[float, ...], parameter: str) -> None:
    with pytest.raises(RectangleError) as error:
        normalize_rectangle(*corners)
    assert error.value.parameter == parameter


def test_degenerate_rectangles_rejected() -> None:
    with pytest.raises(RectangleError, match="zero height"):
        normalize_rectangle(19, -100, 19, -98)
    with pytest.raises(RectangleError, match="zero width"):
        normalize_rectangle(18, -99, 20, -99)


def test_world_limits_are_valid() -> None:
    box = normalize_rectangle(-90, -180, 90, 180)
    assert box.as_geojson_bbox() == [-180, -90, 180, 90]
