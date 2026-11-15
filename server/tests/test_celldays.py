"""Tests for the cell-day harmonization (``harmonizer/celldays.py``, ``GET /api/v1/stats/celldays``).

Own small database, same rectangle as ``BASE_QUERY`` (lat 18..20, lon -100..-98)::

    day         SNPP anywhere?  in the rectangle                         expected source / value
    2024-04-15  yes             SNPP: 2 detections in one cell + 1 other  SNPP, 2 cell-days (3 detections)
                                Aqua: 1 detection (ignored: SNPP wins)
    2024-04-16  no              Aqua: 2 detections in 2 cells             Aqua, 2 × 18376/2391
    2024-04-17  no (no Aqua)    Terra: 1 detection                        Terra, 1 × 18376/1944
    2024-04-18  yes (outside)   nothing                                   SNPP, 0
    2024-04-19  nobody          nothing                                   none
    2024-04-20  nobody          nothing                                   none
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from app import create_app
from app.repository import bulk_insert_hotspots, create_hotspots_table
from app.serializers import NO_DATA_MESSAGE
from harmonizer import celldays
from harmonizer.celldays import FACTORS, PILOT_BOUNDS, DayValue, Period
from tests.conftest import BASE_QUERY, make_settings

AQUA = FACTORS["Aqua"]
TERRA = FACTORS["Terra"]


def _row(lat: float, lon: float, when: str, satellite: str) -> dict[str, Any]:
    """One detection with neutral values except place, time and satellite."""
    acquired_at = datetime.fromisoformat(when)
    return {
        "latitude": lat, "longitude": lon, "acquired_at": acquired_at, "acq_date": acquired_at.date(),
        "instrument": "VIIRS" if satellite == "SNPP" else "MODIS", "satellite": satellite, "source": None,
        "daynight": "D", "bright_mir": 330.0, "bright_tir": 295.0, "frp": 5.0, "pixel_scan": 1.0,
        "pixel_track": 1.0, "confidence": "nominal", "confidence_raw": "n", "fire_type": 0, "version": "t",
    }


CELL_ROWS = [
    _row(19.0, -99.0, "2024-04-15 19:00", "SNPP"),
    _row(19.001, -99.001, "2024-04-15 19:01", "SNPP"),
    _row(18.5, -99.5, "2024-04-15 19:02", "SNPP"),
    _row(19.0, -99.0, "2024-04-15 19:30", "Aqua"),
    _row(19.0, -99.0, "2024-04-16 19:30", "Aqua"),
    _row(18.5, -99.5, "2024-04-16 19:31", "Aqua"),
    _row(19.5, -98.5, "2024-04-17 17:00", "Terra"),
    _row(25.0, -105.0, "2024-04-18 19:00", "SNPP"),
]


@pytest.fixture(scope="module")
def cell_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Database with :data:`CELL_ROWS`."""
    path = tmp_path_factory.mktemp("celldays") / "celldays.duckdb"
    with duckdb.connect(str(path)) as connection:
        create_hotspots_table(connection)
        bulk_insert_hotspots(connection, CELL_ROWS)
    return path


@pytest.fixture()
def get_cells(cell_db: Path) -> Iterator[Callable[..., TestResponse]]:
    """Call ``/api/v1/stats/celldays`` with ``BASE_QUERY`` plus overrides."""
    flask_app = create_app(make_settings(cell_db))
    flask_app.config["TESTING"] = True
    client: FlaskClient = flask_app.test_client()

    def _get(**overrides: Any) -> TestResponse:
        params = {**BASE_QUERY, **overrides}
        return client.get("/api/v1/stats/celldays", query_string={k: v for k, v in params.items() if v is not None})

    yield _get
    flask_app.extensions["hotspots_db"].close()


# --- Pure functions -------------------------------------------------------------------


def test_grid_matches_pilot_function() -> None:
    grid = celldays.build_grid(*PILOT_BOUNDS)
    assert grid.dy == pytest.approx(5 / 111.32)
    assert grid.dx == pytest.approx(grid.dy / math.cos(math.radians(24.595)))
    assert (grid.nx, grid.ny) == (96, 101)


def test_pilot_area_tolerance() -> None:
    west, east, south, north = PILOT_BOUNDS
    assert celldays.is_pilot_area(west, east, south, north)
    assert celldays.is_pilot_area(west + 0.005, east - 0.005, south, north)
    assert not celldays.is_pilot_area(west + 0.5, east, south, north)


def test_daily_series_priority_and_factors() -> None:
    counts = {date(2024, 1, 1): {"SNPP": (3, 4), "Aqua": (1, 1)}, date(2024, 1, 2): {"Aqua": (2, 2)}}
    available = {"SNPP": {date(2024, 1, 1)}, "Aqua": {date(2024, 1, 1), date(2024, 1, 2)}, "Terra": set()}
    days = celldays.daily_series(counts, available, date(2024, 1, 1), date(2024, 1, 3))
    assert [d.source for d in days] == ["SNPP", "Aqua", None]
    assert [d.value for d in days] == [3.0, pytest.approx(2 * AQUA), None]


def test_weeks_are_anchored_at_start_and_partial() -> None:
    days = [DayValue(date(2024, 1, 1 + i), "SNPP", 1, 1, 1.0) for i in range(9)]
    weeks = celldays.aggregate(days, "week", date(2024, 1, 1), date(2024, 1, 9))
    assert [(p.start, p.end, p.partial, p.value) for p in weeks] == [
        (date(2024, 1, 1), date(2024, 1, 7), False, 7.0),
        (date(2024, 1, 8), date(2024, 1, 9), True, 2.0),
    ]


def test_monthly_profile_uses_full_months_only() -> None:
    def month(year: int, value: float | None, partial: bool = False) -> Period:
        return Period(start=date(year, 3, 1), end=date(year, 3, 31), partial=partial, value=value)

    profile = celldays.monthly_profile([month(2020, 10), month(2021, 30), month(2022, 1000, True), month(2023, None)])
    march = profile[2]
    assert march == {"month": 3, "mean": 20.0, "min": 10.0, "max": 30.0, "years": 2}
    assert profile[0] == {"month": 1, "mean": None, "min": None, "max": None, "years": 0}


def test_phases_fold_short_gaps() -> None:
    def run(source: str, start: str, end: str, days: int) -> dict[str, Any]:
        return {"source": source, "start": start, "end": end, "days": days}

    runs = [
        run("terra", "2000-11-01", "2002-07-03", 600),
        run("none", "2002-07-04", "2002-07-04", 1),
        run("aqua", "2002-07-05", "2012-01-19", 3500),
        run("viirs", "2012-01-20", "2015-01-01", 1000),
        run("aqua", "2015-01-02", "2015-01-06", 5),  # outage filled with Aqua
        run("viirs", "2015-01-07", "2020-12-31", 2000),
    ]
    assert celldays.phases(runs) == [
        {"category": "extrapolated", "start": "2000-11-01", "end": "2012-01-19", "days": 4101,
         "days_viirs": 0, "days_aqua": 3500, "days_terra": 600, "days_missing": 1},
        {"category": "viirs", "start": "2012-01-20", "end": "2020-12-31", "days": 3005,
         "days_viirs": 3000, "days_aqua": 5, "days_terra": 0, "days_missing": 0},
    ]


# --- Endpoint -------------------------------------------------------------------------


def test_daily_values_sources_and_periods(get_cells: Callable[..., TestResponse]) -> None:
    response = get_cells(freq="day")
    assert response.status_code == 200
    body = response.get_json()
    series = body["data"]["series"]
    assert [row["source"] for row in series] == ["viirs", "extrapolated", "extrapolated", "viirs", "none", "none"]
    assert [row["value"] for row in series] == [2.0, pytest.approx(2 * AQUA), pytest.approx(TERRA), 0.0, None, None]
    assert [p["source"] for p in body["data"]["periods"]] == ["viirs", "aqua", "terra", "viirs", "none"]
    assert body["data"]["periods"][-1] == {"source": "none", "start": "2024-04-19", "end": "2024-04-20", "days": 2}
    # Six days are too short for separate phases: one VIIRS phase with the filled days counted.
    assert body["data"]["phases"] == [
        {"category": "viirs", "start": "2024-04-15", "end": "2024-04-20", "days": 6,
         "days_viirs": 2, "days_aqua": 1, "days_terra": 1, "days_missing": 2},
    ]
    assert "message" not in body


def test_month_totals_and_metadata(get_cells: Callable[..., TestResponse]) -> None:
    body = get_cells().get_json()
    (month,) = body["data"]["months"]
    assert month["start"] == "2024-04-15" and month["partial"] is True
    assert month["source"] == "mixed"
    assert month["viirs"] == 2.0
    assert month["extrapolated"] == pytest.approx(2 * AQUA + TERRA)
    assert (month["days_viirs"], month["days_aqua"], month["days_terra"], month["days_missing"]) == (2, 1, 1, 2)
    assert body["data"]["series"] == body["data"]["months"]
    meta = body["metadata"]
    assert meta["freq"] == "month" and meta["filters_applied"] is False
    assert meta["pilot_area"] is False and "Durango" in meta["warning"]
    assert meta["disclaimer"].startswith("Cell-days are an indirect metric")


def test_filters_are_ignored(get_cells: Callable[..., TestResponse]) -> None:
    plain = get_cells().get_json()["data"]
    filtered = get_cells(instrument="MODIS", confidence_min="high", fire_type="1").get_json()["data"]
    assert plain == filtered


def test_pilot_area_has_no_warning(get_cells: Callable[..., TestResponse]) -> None:
    west, east, south, north = PILOT_BOUNDS
    meta = get_cells(lat1=south, lon1=west, lat2=north, lon2=east).get_json()["metadata"]
    assert meta["pilot_area"] is True and meta["warning"] is None


def test_empty_rectangle(get_cells: Callable[..., TestResponse]) -> None:
    body = get_cells(lat1=10, lon1=-120, lat2=12, lon2=-118).get_json()
    assert body["message"] == NO_DATA_MESSAGE


def test_invalid_freq(get_cells: Callable[..., TestResponse]) -> None:
    response = get_cells(freq="quarter")
    assert response.status_code == 400
    assert response.get_json()["error"]["parameter"] == "freq"
