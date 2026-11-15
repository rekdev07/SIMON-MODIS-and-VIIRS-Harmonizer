"""Tests for ``GET /api/v1/calendar`` and the pure grid builder in ``app.calendar``.

The known database (see conftest) covers 2024-04-15 .. 2024-05-10, so both
April and May 2024 are *partial* months.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from flask.testing import FlaskClient

from app.calendar import NO_DATA_MESSAGE, build_calendar, is_partial_month
from app.geo import BoundingBox

AREA: dict[str, Any] = {"lat1": 18, "lon1": -100, "lat2": 20, "lon2": -98}
BOX = BoundingBox(18, -100, 20, -98)


def _get(client: FlaskClient, **params: Any) -> Any:
    return client.get("/api/v1/calendar", query_string={**AREA, **params})


def test_counts_per_month_split_by_instrument(client: FlaskClient) -> None:
    response = _get(client)
    assert response.status_code == 200
    body = response.get_json()
    assert body["coverage"] == {"start_date": "2024-04-15", "end_date": "2024-05-10"}
    assert body["harmonized"] is False
    assert body["total"] == 6
    assert body["months"] == [
        {"year": 2024, "month": 4, "count": 5, "modis": 2, "viirs": 3, "partial": True},
        {"year": 2024, "month": 5, "count": 1, "modis": 0, "viirs": 1, "partial": True},
    ]
    assert body["years"] == [{"year": 2024, "count": 6, "partial": True}]
    assert "message" not in body


def test_partial_months_are_left_out_of_the_median(client: FlaskClient) -> None:
    assert _get(client).get_json()["monthly_median"] == [None] * 12


def test_reversed_corners_give_the_same_calendar(client: FlaskClient) -> None:
    reversed_corners = client.get(
        "/api/v1/calendar", query_string={"lat1": 20, "lon1": -98, "lat2": 18, "lon2": -100}
    )
    assert reversed_corners.get_json() == _get(client).get_json()


def test_filters_apply_to_the_counts(client: FlaskClient) -> None:
    assert _get(client, instrument="modis").get_json()["total"] == 2
    assert _get(client, vegetation_only="true").get_json()["total"] == 3  # A, B (NULL), G
    assert _get(client, confidence_min="high").get_json()["total"] == 2  # C, E
    assert _get(client, daynight="N").get_json()["total"] == 2  # B, E


def test_instrument_filter_limits_coverage(client: FlaskClient) -> None:
    body = _get(client, instrument="MODIS").get_json()
    assert body["coverage"] == {"start_date": "2024-04-15", "end_date": "2024-04-18"}
    assert [m["month"] for m in body["months"]] == [4]


def test_empty_area_keeps_zero_months_and_message(client: FlaskClient) -> None:
    body = client.get(
        "/api/v1/calendar", query_string={"lat1": 40, "lon1": 0, "lat2": 41, "lon2": 1}
    ).get_json()
    assert body["total"] == 0
    assert [m["count"] for m in body["months"]] == [0, 0]
    assert body["message"] == NO_DATA_MESSAGE


def test_invalid_rectangle_is_400(client: FlaskClient) -> None:
    response = client.get(
        "/api/v1/calendar", query_string={"lat1": 18, "lon1": -100, "lat2": 18, "lon2": -98}
    )
    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "INVALID_PARAMETER"


def test_missing_corner_is_400(client: FlaskClient) -> None:
    response = client.get("/api/v1/calendar", query_string={"lat1": 18, "lon1": -100, "lat2": 20})
    assert response.status_code == 400
    assert response.get_json()["error"]["parameter"] == "lon2"


def test_build_calendar_fills_zeros_and_computes_medians() -> None:
    rows = [(2020, 1, 10, 10, 0), (2021, 1, 30, 0, 30), (2022, 1, 20, 0, 20), (2022, 2, 4, 0, 4)]
    body = build_calendar(rows, (date(2020, 1, 1), date(2022, 2, 28)), BOX)
    assert len(body["months"]) == 26  # Jan 2020 .. Feb 2022, zeros included
    assert body["months"][1] == {
        "year": 2020, "month": 2, "count": 0, "modis": 0, "viirs": 0, "partial": False,
    }
    assert body["monthly_median"][0] == 20.0  # median of 10, 30, 20
    assert body["monthly_median"][1] == 0.0  # median of 0, 0, 4
    assert body["monthly_median"][2] == 0.0  # March: 2020 and 2021 only
    assert body["years"] == [
        {"year": 2020, "count": 10, "partial": False},
        {"year": 2021, "count": 30, "partial": False},
        {"year": 2022, "count": 24, "partial": True},  # only 2 of 12 months loaded
    ]


def test_build_calendar_without_data() -> None:
    body = build_calendar([], None, BOX)
    assert body["coverage"] is None
    assert body["months"] == []
    assert body["monthly_median"] == [None] * 12
    assert body["message"] == NO_DATA_MESSAGE


def test_is_partial_month() -> None:
    first, last = date(2013, 1, 1), date(2014, 1, 1)
    assert not is_partial_month(2013, 1, first, last)
    assert not is_partial_month(2013, 12, first, last)
    assert is_partial_month(2014, 1, first, last)
    assert is_partial_month(2012, 12, date(2012, 12, 2), last)
