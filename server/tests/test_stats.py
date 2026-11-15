"""Endpoint tests for ``GET /api/v1/stats/*`` using ``STATS_ROWS`` from conftest."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from werkzeug.test import TestResponse

from app.serializers import NO_DATA_MESSAGE

Get = Callable[..., TestResponse]

#: Every stats endpoint with the options needed to call it.
ENDPOINTS: list[tuple[str, dict]] = [
    ("summary", {}),
    ("timeseries", {}),
    ("distribution", {}),
    ("scatter", {}),
    ("calendar", {}),
    ("by-hour", {}),
    ("by-category", {"field": "daynight"}),
    ("by-scan", {}),
    ("top-events", {}),
    ("points", {}),
    ("grid", {}),
    ("sensor-comparison", {}),
    ("monthly", {}),
]

#: A valid rectangle with no detections (the Pacific Ocean).
EMPTY_AREA = {"lat1": 10, "lon1": -120, "lat2": 12, "lon2": -118}


def _data(response: TestResponse) -> object:
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


# --- Common behavior ------------------------------------------------------------------


@pytest.mark.parametrize(("endpoint", "options"), ENDPOINTS)
def test_envelope_with_results(get_stats: Get, endpoint: str, options: dict) -> None:
    body = get_stats(endpoint, **options).get_json()
    assert set(body) == {"data", "metadata"}
    metadata = body["metadata"]
    assert metadata["bbox"] == [-100.0, 18.0, -98.0, 20.0]
    assert (metadata["start_date"], metadata["end_date"]) == ("2024-04-15", "2024-04-20")
    assert metadata["filters"] == {
        "confidence_min": "low", "daynight": None, "instrument": None, "satellite": None, "fire_type": 0,
    }
    assert isinstance(metadata["units"], dict)


@pytest.mark.parametrize(("endpoint", "options"), ENDPOINTS)
def test_empty_rectangle_returns_200_and_message(get_stats: Get, endpoint: str, options: dict) -> None:
    response = get_stats(endpoint, **options, **EMPTY_AREA)
    assert response.status_code == 200
    body = response.get_json()
    assert body["message"] == NO_DATA_MESSAGE
    assert body["data"] in ([], {"daily": [], "ratio": []})


@pytest.mark.parametrize(("endpoint", "options"), ENDPOINTS)
@pytest.mark.parametrize(
    ("bad", "parameter"),
    [
        ({"lat1": 95}, "lat1"),
        ({"lon2": -181}, "lon2"),
        ({"lat2": 18}, "lat2"),  # zero-height rectangle
        ({"start_date": "2024-04-21"}, "end_date"),  # inverted dates
        ({"start_date": "15/04/2024"}, "start_date"),
        ({"end_date": None}, "end_date"),
        ({"instrument": "GOES"}, "instrument"),
        ({"satellite": "Landsat"}, "satellite"),
        ({"fire_type": "7"}, "fire_type"),
        ({"daynight": "X"}, "daynight"),
        ({"confidence_min": "medium"}, "confidence_min"),
    ],
)
def test_invalid_common_parameters(get_stats: Get, endpoint: str, options: dict, bad: dict, parameter: str) -> None:
    response = get_stats(endpoint, **{**options, **bad})
    assert response.status_code == 400
    error = response.get_json()["error"]
    assert error["code"] == "INVALID_PARAMETER"
    assert error["parameter"] == parameter


@pytest.mark.parametrize(
    ("endpoint", "bad", "parameter"),
    [
        ("timeseries", {"freq": "year"}, "freq"),
        ("distribution", {"field": "scan"}, "field"),
        ("distribution", {"bins": 0}, "bins"),
        ("distribution", {"bins": 101}, "bins"),
        ("distribution", {"log": "maybe"}, "log"),
        ("scatter", {"x": "frp"}, "x"),
        ("scatter", {"y": "lat"}, "y"),
        ("scatter", {"limit": 5001}, "limit"),
        ("calendar", {"metric": "area"}, "metric"),
        ("calendar", {"granularity": "month"}, "granularity"),
        ("by-category", {}, "field"),
        ("by-category", {"field": "sensor"}, "field"),
        ("by-scan", {"bins": 51}, "bins"),
        ("top-events", {"n": 0}, "n"),
        ("top-events", {"n": 101}, "n"),
        ("points", {"limit": 101}, "limit"),  # MAX_LIMIT is 100 in this test app
        ("points", {"limit": 0}, "limit"),
        ("grid", {"cell": 0}, "cell"),
        ("grid", {"cell": 6}, "cell"),
        ("grid", {"cell": "abc"}, "cell"),
    ],
)
def test_invalid_endpoint_options(get_stats: Get, endpoint: str, bad: dict, parameter: str) -> None:
    response = get_stats(endpoint, **bad)
    assert response.status_code == 400
    body = response.get_json()["error"]
    assert body["parameter"] == parameter
    assert parameter in body["message"]


def test_null_instead_of_nan(get_stats: Get) -> None:
    # V3 is the only detection on 2024-04-17 and has no FRP: mean and total are null.
    rows = _data(get_stats("timeseries", start_date="2024-04-17", end_date="2024-04-17"))
    assert rows == [
        {"period": "2024-04-17", "sensor": "VIIRS", "detections": 1, "frp_total": None,
         "frp_mean": None, "bright_mir_mean": 300.0},
    ]


# --- Filters ----------------------------------------------------------------------------


def _counts(get_stats: Get, **params: object) -> dict[str, int]:
    return {row["sensor"]: row["total_detections"] for row in _data(get_stats("summary", **params))}


def test_default_fire_type_keeps_vegetation_and_unknown(get_stats: Get) -> None:
    assert _counts(get_stats) == {"MODIS": 2, "VIIRS": 3}  # M3 (type 2) excluded, V1 (NULL) kept


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"fire_type": "all"}, {"MODIS": 3, "VIIRS": 3}),
        ({"fire_type": 2}, {"MODIS": 1}),
        ({"confidence_min": "high"}, {"MODIS": 1, "VIIRS": 1}),
        ({"confidence_min": "nominal"}, {"MODIS": 1, "VIIRS": 2}),
        ({"satellite": "noaa-20"}, {"VIIRS": 2}),
        ({"instrument": "viirs"}, {"VIIRS": 3}),
        ({"daynight": "n"}, {"VIIRS": 1}),
        ({"lat1": 20, "lon1": -98, "lat2": 18, "lon2": -100}, {"MODIS": 2, "VIIRS": 3}),  # reversed corners
    ],
)
def test_filters(get_stats: Get, params: dict, expected: dict) -> None:
    assert _counts(get_stats, **params) == expected


# --- Endpoints --------------------------------------------------------------------------


def test_summary(get_stats: Get) -> None:
    body = get_stats("summary").get_json()
    assert body["data"] == [
        {"sensor": "MODIS", "total_detections": 2, "frp_mean": 20.0, "frp_max": 30.0,
         "bright_mir_mean": 330.0, "bright_tir_mean": 297.5},
        {"sensor": "VIIRS", "total_detections": 3, "frp_mean": 3.5, "frp_max": 5.0,
         "bright_mir_mean": 313.333333, "bright_tir_mean": 285.0},
    ]
    assert body["metadata"]["units"]["frp_mean"] == "MW"
    assert body["metadata"]["units"]["bright_mir_mean"] == "K"


def test_timeseries_day(get_stats: Get) -> None:
    rows = _data(get_stats("timeseries", freq="day"))
    assert [(r["period"], r["sensor"], r["detections"], r["frp_total"]) for r in rows] == [
        ("2024-04-15", "MODIS", 2, 40.0),
        ("2024-04-15", "VIIRS", 2, 7.0),
        ("2024-04-17", "VIIRS", 1, None),
    ]


@pytest.mark.parametrize(("freq", "period"), [("week", "2024-04-15"), ("month", "2024-04-01"), ("WEEK", "2024-04-15")])
def test_timeseries_week_and_month(get_stats: Get, freq: str, period: str) -> None:
    body = get_stats("timeseries", freq=freq).get_json()
    assert [(r["period"], r["sensor"], r["detections"]) for r in body["data"]] == [
        (period, "MODIS", 2), (period, "VIIRS", 3),
    ]
    assert body["metadata"]["freq"] == freq.lower()


def test_distribution_linear(get_stats: Get) -> None:
    body = get_stats("distribution", field="frp", bins=2).get_json()
    # Valid FRP: 10, 30 (MODIS), 5, 2 (VIIRS); range 2..30 -> width 14.
    assert body["data"] == [
        {"bin_start": 2.0, "bin_end": 16.0, "sensor": "MODIS", "count": 1},
        {"bin_start": 2.0, "bin_end": 16.0, "sensor": "VIIRS", "count": 2},
        {"bin_start": 16.0, "bin_end": 30.0, "sensor": "MODIS", "count": 1},
        {"bin_start": 16.0, "bin_end": 30.0, "sensor": "VIIRS", "count": 0},
    ]
    assert body["metadata"]["excluded"] == 1  # V3 has no FRP
    assert body["metadata"]["units"] == {"bin_start": "MW", "bin_end": "MW"}


def test_distribution_log(get_stats: Get) -> None:
    rows = _data(get_stats("distribution", field="frp", bins=2, log="true"))
    assert rows[0]["bin_start"] == pytest.approx(2.0)
    assert rows[-1]["bin_end"] == pytest.approx(30.0)
    assert rows[0]["bin_end"] == pytest.approx((2 * 30) ** 0.5, rel=1e-5)  # geometric middle
    assert sum(r["count"] for r in rows) == 4


def test_distribution_confidence_raw_is_modis_only(get_stats: Get) -> None:
    rows = _data(get_stats("distribution", field="confidence_raw", bins=4))
    assert {r["sensor"] for r in rows} == {"MODIS"}
    assert [(r["bin_start"], r["count"]) for r in rows] == [(0.0, 0), (25.0, 1), (50.0, 0), (75.0, 1)]


def test_scatter_sample(get_stats: Get) -> None:
    body = get_stats("scatter", x="pixel_area_km2", y="frp", limit=2).get_json()
    assert len(body["data"]) == 2
    assert set(body["data"][0]) == {"x", "y", "sensor", "confidence_level"}
    assert body["metadata"]["available"] == 4  # V3 has no FRP
    assert body["metadata"]["sampled"] is True
    assert body["metadata"]["units"] == {"x": "km2", "y": "MW"}
    assert get_stats("scatter", x="pixel_area_km2", y="frp", limit=2).get_json() == body  # deterministic


def test_scatter_all_rows(get_stats: Get) -> None:
    rows = _data(get_stats("scatter"))
    assert sorted((r["x"], r["y"]) for r in rows) == [(300, 280), (310, 285), (320, 295), (330, 290), (340, 300)]


def test_calendar_day(get_stats: Get) -> None:
    rows = _data(get_stats("calendar"))
    assert rows == [
        {"year": 2024, "day_of_year": 106, "date": "2024-04-15", "sensor": "MODIS", "value": 2},
        {"year": 2024, "day_of_year": 106, "date": "2024-04-15", "sensor": "VIIRS", "value": 2},
        {"year": 2024, "day_of_year": 108, "date": "2024-04-17", "sensor": "VIIRS", "value": 1},
    ]


def test_calendar_week_frp(get_stats: Get) -> None:
    body = get_stats("calendar", metric="frp", granularity="week").get_json()
    assert body["data"] == [
        {"year": 2024, "week": 16, "date": "2024-04-15", "sensor": "MODIS", "value": 40.0},
        {"year": 2024, "week": 16, "date": "2024-04-15", "sensor": "VIIRS", "value": 7.0},
    ]
    assert body["metadata"]["units"] == {"value": "MW"}


def test_by_hour(get_stats: Get) -> None:
    rows = _data(get_stats("by-hour"))
    assert [(r["hour_utc"], r["sensor"], r["satellite"], r["detections"]) for r in rows] == [
        (8, "VIIRS", "SNPP", 1),
        (19, "MODIS", "Terra", 1),
        (19, "VIIRS", "NOAA-20", 1),
        (20, "MODIS", "Aqua", 1),
        (20, "VIIRS", "NOAA-20", 1),
    ]


@pytest.mark.parametrize(
    ("field", "extra", "expected"),
    [
        ("daynight", {}, [("D", "MODIS", 2, 20.0), ("D", "VIIRS", 2, 5.0), ("N", "VIIRS", 1, 2.0)]),
        ("type", {"fire_type": "all"},
         [(0, "MODIS", 2, 20.0), (2, "MODIS", 1, 50.0), (0, "VIIRS", 2, 2.0), (None, "VIIRS", 1, 5.0)]),
        ("satellite", {}, [("Aqua", "MODIS", 1, 30.0), ("Terra", "MODIS", 1, 10.0),
                           ("NOAA-20", "VIIRS", 2, 5.0), ("SNPP", "VIIRS", 1, 2.0)]),
        ("confidence_level", {}, [("high", "MODIS", 1, 10.0), ("low", "MODIS", 1, 30.0),
                                  ("high", "VIIRS", 1, 5.0), ("low", "VIIRS", 1, None),
                                  ("nominal", "VIIRS", 1, 2.0)]),
    ],
)
def test_by_category(get_stats: Get, field: str, extra: dict, expected: list) -> None:
    rows = _data(get_stats("by-category", field=field, **extra))
    assert [(r["category"], r["sensor"], r["detections"], r["frp_mean"]) for r in rows] == expected


def test_by_scan(get_stats: Get) -> None:
    rows = _data(get_stats("by-scan", bins=2))
    modis = [r for r in rows if r["sensor"] == "MODIS"]
    # MODIS scans 1.0 and 2.0 -> ranges [1.0, 1.5] and [1.5, 2.0] (max goes to the last range).
    assert modis == [
        {"sensor": "MODIS", "scan_start": 1.0, "scan_end": 1.5, "detections": 1, "frp_p5": 10.0, "frp_median": 10.0},
        {"sensor": "MODIS", "scan_start": 1.5, "scan_end": 2.0, "detections": 1, "frp_p5": 30.0, "frp_median": 30.0},
    ]
    viirs = [r for r in rows if r["sensor"] == "VIIRS"]
    assert sum(r["detections"] for r in viirs) == 3
    assert viirs[0]["scan_start"] == pytest.approx(0.4)  # ranges are computed per sensor


def test_top_events(get_stats: Get) -> None:
    rows = _data(get_stats("top-events", n=2))
    assert rows == [
        {"timestamp_utc": "2024-04-15T20:10:00Z", "lat": 19.2, "lon": -99.2, "frp": 30.0,
         "bright_mir": 340.0, "bright_tir": 300.0, "sensor": "MODIS", "satellite": "Aqua"},
        {"timestamp_utc": "2024-04-15T19:42:00Z", "lat": 19.0, "lon": -99.0, "frp": 10.0,
         "bright_mir": 320.0, "bright_tir": 295.0, "sensor": "MODIS", "satellite": "Terra"},
    ]
    assert _data(get_stats("top-events", n=1, fire_type="all"))[0]["frp"] == 50.0


def test_points(get_stats: Get) -> None:
    body = get_stats("points", limit=2).get_json()
    assert body["data"] == [
        {"lat": 19.2, "lon": -99.2, "frp": 30.0, "sensor": "MODIS"},
        {"lat": 19.0, "lon": -99.0, "frp": 10.0, "sensor": "MODIS"},
    ]
    assert (body["metadata"]["returned"], body["metadata"]["truncated"]) == (2, True)
    everything = get_stats("points").get_json()
    assert everything["metadata"]["limit"] == 100  # default min(5000, MAX_LIMIT)
    assert everything["metadata"]["truncated"] is False
    assert everything["data"][-1]["frp"] is None  # unknown FRP last


def test_grid(get_stats: Get) -> None:
    body = get_stats("grid", cell=1).get_json()
    assert [(r["lat"], r["lon"], r["sensor"], r["detections"], r["frp_total"]) for r in body["data"]] == [
        (18.5, -99.5, "VIIRS", 1, 2.0),
        (18.5, -98.5, "VIIRS", 1, None),
        (19.5, -99.5, "MODIS", 1, 30.0),
        (19.5, -99.5, "VIIRS", 1, 5.0),
        (19.5, -98.5, "MODIS", 1, 10.0),
    ]
    assert body["metadata"]["cell"] == 1.0


def test_sensor_comparison(get_stats: Get) -> None:
    data = _data(get_stats("sensor-comparison"))
    assert data["daily"] == [
        {"date": "2024-04-15", "sensor": "MODIS", "detections": 2, "frp_total": 40.0},
        {"date": "2024-04-15", "sensor": "VIIRS", "detections": 2, "frp_total": 7.0},
        {"date": "2024-04-17", "sensor": "VIIRS", "detections": 1, "frp_total": None},
    ]
    assert data["ratio"] == [
        {"date": "2024-04-15", "modis_detections": 2, "viirs_detections": 2,
         "detections_ratio": 1.0, "frp_ratio": 0.175},
    ]


def test_sensor_comparison_without_viirs(get_stats: Get) -> None:
    body = get_stats("sensor-comparison", instrument="MODIS").get_json()
    assert len(body["data"]["daily"]) == 1
    assert body["data"]["ratio"] == []
    assert "message" not in body


def test_monthly(get_stats: Get) -> None:
    assert _data(get_stats("monthly")) == [
        {"month": 4, "sensor": "MODIS", "detections": 2, "years_with_data": 1},
        {"month": 4, "sensor": "VIIRS", "detections": 3, "years_with_data": 1},
    ]
