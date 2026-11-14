"""Endpoint tests for ``GET /api/v1/hotspots`` using the known rows in conftest."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from werkzeug.test import TestResponse

from app.schemas import utc_today
from app.serializers import NO_DATA_MESSAGE
from tests.conftest import ids

Get = Callable[..., TestResponse]


def test_basic_query_geojson(get_hotspots: Get) -> None:
    response = get_hotspots()
    assert response.status_code == 200
    body = response.get_json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 5
    assert "message" not in body
    assert body["metadata"] == {
        "bbox": [-100.0, 18.0, -98.0, 20.0],
        "start_date": "2024-04-15",
        "end_date": "2024-04-20",
        "returned": 5,
        "limit": 10000,
        "offset": 0,
        "truncated": False,
    }


def test_geojson_coordinates_are_lon_lat(get_hotspots: Get) -> None:
    feature = get_hotspots().get_json()["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"] == {"type": "Point", "coordinates": [-99.0, 19.0]}
    assert feature["properties"] == {
        "acquired_at": "2024-04-15T19:42:00Z",
        "instrument": "VIIRS",
        "satellite": "NOAA-20",
        "daynight": "D",
        "frp": 12.4,
        "confidence": "nominal",
        "fire_type": 0,
    }


def test_results_ordered_by_acquired_at(get_hotspots: Get) -> None:
    assert ids(get_hotspots(format="json").get_json()) == ["A", "B", "C", "D", "E"]


def test_json_format_returns_full_records(get_hotspots: Get) -> None:
    body = get_hotspots(format="json").get_json()
    assert set(body) == {"data", "metadata"}
    first = body["data"][0]
    assert first["acquired_at"] == "2024-04-15T19:42:00Z"
    assert first["acq_date"] == "2024-04-15"
    assert {"bright_mir", "bright_tir", "pixel_scan", "confidence_raw"} <= set(first)


@pytest.mark.parametrize(
    "corners",
    [
        {"lat1": 20, "lon1": -98, "lat2": 18, "lon2": -100},
        {"lat1": 18, "lon1": -98, "lat2": 20, "lon2": -100},
        {"lat1": 20, "lon1": -100, "lat2": 18, "lon2": -98},
    ],
)
def test_reversed_corners_same_result(get_hotspots: Get, corners: dict[str, float]) -> None:
    reference = get_hotspots(format="json").get_json()
    reversed_body = get_hotspots(format="json", **corners).get_json()
    assert reversed_body == reference


def test_point_on_edge_is_included(get_hotspots: Get) -> None:
    # D lies exactly on lat=20, lon=-98 (the north-east corner).
    assert "D" in ids(get_hotspots(format="json").get_json())
    # Shrink the box so D is exactly on its south-west corner: still included.
    body = get_hotspots(format="json", lat1=20, lon1=-98, lat2=21, lon2=-97).get_json()
    assert ids(body) == ["D"]


def test_dates_are_inclusive(get_hotspots: Get) -> None:
    assert ids(get_hotspots(format="json", start_date="2024-04-20", end_date="2024-04-20").get_json()) == ["E"]
    assert ids(get_hotspots(format="json", start_date="2024-04-15", end_date="2024-04-15").get_json()) == ["A"]


@pytest.mark.parametrize("output", ["geojson", "json"])
def test_empty_result_message(get_hotspots: Get, output: str) -> None:
    response = get_hotspots(lat1=-40, lon1=140, lat2=-30, lon2=150, format=output)
    assert response.status_code == 200
    body = response.get_json()
    assert body["message"] == NO_DATA_MESSAGE == "No data found in the selected area"
    assert body["metadata"]["returned"] == 0
    assert body["metadata"]["truncated"] is False
    assert body.get("features", body.get("data")) == []


def test_limit_and_truncated(get_hotspots: Get) -> None:
    body = get_hotspots(format="json", limit=2).get_json()
    assert ids(body) == ["A", "B"]
    assert body["metadata"]["truncated"] is True
    assert body["metadata"]["returned"] == 2

    body = get_hotspots(format="json", limit=2, offset=4).get_json()
    assert ids(body) == ["E"]
    assert body["metadata"]["truncated"] is False

    body = get_hotspots(format="json", limit=5).get_json()
    assert body["metadata"]["truncated"] is False


def test_offset_paginates_without_gaps(get_hotspots: Get) -> None:
    pages = [ids(get_hotspots(format="json", limit=2, offset=o).get_json()) for o in (0, 2, 4)]
    assert sum(pages, []) == ["A", "B", "C", "D", "E"]


def test_vegetation_only_keeps_null_and_zero(get_hotspots: Get) -> None:
    assert ids(get_hotspots(format="json", vegetation_only="true").get_json()) == ["A", "B"]
    assert len(ids(get_hotspots(format="json", vegetation_only="false").get_json())) == 5


def test_confidence_min(get_hotspots: Get) -> None:
    assert ids(get_hotspots(format="json", confidence_min="nominal").get_json()) == ["A", "C", "D", "E"]
    assert ids(get_hotspots(format="json", confidence_min="high").get_json()) == ["C", "E"]
    assert len(ids(get_hotspots(format="json", confidence_min="low").get_json())) == 5


def test_daynight_filter(get_hotspots: Get) -> None:
    assert ids(get_hotspots(format="json", daynight="N").get_json()) == ["B", "E"]
    assert ids(get_hotspots(format="json", daynight="d").get_json()) == ["A", "C", "D"]


def test_instrument_filter(get_hotspots: Get) -> None:
    assert ids(get_hotspots(format="json", instrument="MODIS").get_json()) == ["C", "D"]
    assert ids(get_hotspots(format="json", instrument="viirs").get_json()) == ["A", "B", "E"]


@pytest.mark.parametrize(
    ("overrides", "parameter"),
    [
        ({"lat1": 91}, "lat1"),
        ({"lat2": -91}, "lat2"),
        ({"lon1": -181}, "lon1"),
        ({"lon2": 200}, "lon2"),
        ({"lat1": "abc"}, "lat1"),
        ({"lat1": "nan"}, "lat1"),
        ({"lat2": 18}, "lat2"),  # zero height
        ({"lon2": -100}, "lon2"),  # zero width
        ({"lat1": None}, "lat1"),  # missing
        ({"start_date": None}, "start_date"),
        ({"start_date": "2024/04/15"}, "start_date"),
        ({"start_date": "2024-02-30"}, "start_date"),
        ({"start_date": "2000-10-31"}, "start_date"),
        ({"start_date": "2024-04-21"}, "end_date"),  # reversed dates
        ({"confidence_min": "medium"}, "confidence_min"),
        ({"daynight": "X"}, "daynight"),
        ({"instrument": "GOES"}, "instrument"),
        ({"vegetation_only": "maybe"}, "vegetation_only"),
        ({"limit": 0}, "limit"),
        ({"limit": 50001}, "limit"),
        ({"offset": -1}, "offset"),
        ({"format": "csv"}, "format"),
    ],
)
def test_invalid_parameters_return_400(get_hotspots: Get, overrides: dict, parameter: str) -> None:
    response = get_hotspots(**overrides)
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "INVALID_PARAMETER"
    assert error["parameter"] == parameter
    assert parameter in error["message"] or "rectangle" in error["message"]


def test_future_end_date_rejected(get_hotspots: Get) -> None:
    tomorrow = (utc_today() + timedelta(days=1)).isoformat()
    response = get_hotspots(end_date=tomorrow)
    assert response.status_code == 400
    assert response.get_json()["error"]["parameter"] == "end_date"


def test_unknown_route_returns_json_404(client) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.get_json()["error"]["code"] == "NOT_FOUND"


def test_cors_header_for_vite_client(get_hotspots: Get, client) -> None:
    response = client.get(
        "/api/v1/hotspots",
        query_string={"lat1": 18, "lon1": -100, "lat2": 20, "lon2": -98,
                      "start_date": "2024-04-15", "end_date": "2024-04-20"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
