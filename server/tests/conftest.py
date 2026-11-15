"""Shared pytest fixtures: a tiny, fully known hotspots database and a test client.

The tests never touch ``data/`` or the real FIRMS JSON. Instead they use the
rows below, laid out like this (``*`` = inside the test rectangle
lat 18..20, lon -100..-98, dates 2024-04-15..2024-04-20)::

    id  lat     lon      acquired_at (UTC)   instr  sat      D/N conf     type
    A*  19.0   -99.0     2024-04-15 19:42    VIIRS  NOAA-20  D   nominal  0
    B*  18.5   -99.5     2024-04-16 07:30    VIIRS  SNPP     N   low      NULL
    C*  19.5   -98.5     2024-04-17 16:30    MODIS  Terra    D   high     1
    D*  20.0   -98.0     2024-04-18 19:00    MODIS  Aqua     D   nominal  2   (exactly on the NE corner)
    E*  18.2   -99.9     2024-04-20 04:00    VIIRS  NOAA-21  N   high     3   (last inclusive day)
    F   25.0  -105.0     2024-04-15 17:00    MODIS  Terra    D   high     0   (outside the rectangle)
    G   19.0   -99.0     2024-05-10 19:00    VIIRS  SNPP     D   nominal  0   (outside the dates)
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from app import create_app
from app.config import Settings
from app.repository import bulk_insert_hotspots, create_hotspots_table

#: Query parameters selecting rows A–E.
BASE_QUERY: dict[str, Any] = {
    "lat1": 18,
    "lon1": -100,
    "lat2": 20,
    "lon2": -98,
    "start_date": "2024-04-15",
    "end_date": "2024-04-20",
}


def _row(
    name: str,
    lat: float,
    lon: float,
    when: str,
    instrument: str,
    satellite: str,
    daynight: str,
    confidence: str,
    raw: str,
    fire_type: int | None,
) -> dict[str, Any]:
    """Build one known test row (``name`` is stored in ``version`` to identify it)."""
    acquired_at = datetime.fromisoformat(when)
    return {
        "latitude": lat,
        "longitude": lon,
        "acquired_at": acquired_at,
        "acq_date": acquired_at.date(),
        "instrument": instrument,
        "satellite": satellite,
        "source": None,
        "daynight": daynight,
        "bright_mir": 330.0,
        "bright_tir": 295.0,
        "frp": 12.4,
        "pixel_scan": 0.4,
        "pixel_track": 0.4,
        "confidence": confidence,
        "confidence_raw": raw,
        "fire_type": fire_type,
        "version": name,
    }


KNOWN_ROWS: list[dict[str, Any]] = [
    _row("A", 19.0, -99.0, "2024-04-15 19:42", "VIIRS", "NOAA-20", "D", "nominal", "n", 0),
    _row("B", 18.5, -99.5, "2024-04-16 07:30", "VIIRS", "SNPP", "N", "low", "l", None),
    _row("C", 19.5, -98.5, "2024-04-17 16:30", "MODIS", "Terra", "D", "high", "85", 1),
    _row("D", 20.0, -98.0, "2024-04-18 19:00", "MODIS", "Aqua", "D", "nominal", "50", 2),
    _row("E", 18.2, -99.9, "2024-04-20 04:00", "VIIRS", "NOAA-21", "N", "high", "h", 3),
    _row("F", 25.0, -105.0, "2024-04-15 17:00", "MODIS", "Terra", "D", "high", "90", 0),
    _row("G", 19.0, -99.0, "2024-05-10 19:00", "VIIRS", "SNPP", "D", "nominal", "n", 0),
]


@pytest.fixture(scope="session")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create the known test database once per test session.

    Returns:
        Path to the temporary DuckDB file.
    """
    path = tmp_path_factory.mktemp("db") / "test_hotspots.duckdb"
    with duckdb.connect(str(path)) as connection:
        create_hotspots_table(connection)
        bulk_insert_hotspots(connection, KNOWN_ROWS)
    return path


def make_settings(db_path: Path, **overrides: Any) -> Settings:
    """Build test settings pointing at ``db_path``.

    Args:
        db_path: Database to use.
        **overrides: Any :class:`Settings` field to override.

    Returns:
        The settings.
    """
    values: dict[str, Any] = {
        "db_path": db_path,
        "cors_origins": ["http://localhost:5173"],
        "default_limit": 10_000,
        "max_limit": 50_000,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture()
def app(db_path: Path) -> Iterator[Flask]:
    """Flask app bound to the known test database."""
    flask_app = create_app(make_settings(db_path))
    flask_app.config["TESTING"] = True
    yield flask_app
    flask_app.extensions["hotspots_db"].close()


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    """Flask test client."""
    return app.test_client()


@pytest.fixture()
def get_hotspots(client: FlaskClient) -> Callable[..., TestResponse]:
    """Call ``/api/v1/hotspots`` with :data:`BASE_QUERY` plus overrides.

    Passing ``name=None`` removes a parameter from the query.
    """

    def _get(**overrides: Any) -> TestResponse:
        params = {**BASE_QUERY, **overrides}
        params = {key: value for key, value in params.items() if value is not None}
        return client.get("/api/v1/hotspots", query_string=params)

    return _get


def ids(body: dict[str, Any]) -> list[str]:
    """Return the test-row names (stored in ``version``) of a ``format=json`` body."""
    return [row["version"] for row in body["data"]]


# --- Dashboard statistics (/api/v1/stats/*) -------------------------------------------
#
# A second small database with varied values, so aggregates are easy to check
# by hand. Same rectangle and dates as BASE_QUERY (``*`` = selected by default;
# ``fire_type`` defaults to 0, which also keeps NULL types)::
#
#     id   lat    lon     acquired_at (UTC)  sensor sat      D/N raw type frp  mir tir scan track
#     M1*  19.0  -99.0   2024-04-15 19:42   MODIS  Terra    D   85  0    10   320 295 1.0  1.0
#     M2*  19.2  -99.2   2024-04-15 20:10   MODIS  Aqua     D   29  0    30   340 300 2.0  1.5
#     M3   18.6  -98.6   2024-04-16 05:00   MODIS  Terra    N   30  2    50   360 305 3.0  2.0
#     V1*  19.1  -99.1   2024-04-15 19:00   VIIRS  NOAA-20  D   h   NULL 5    330 290 0.4  0.4
#     V2*  18.4  -99.6   2024-04-15 08:00   VIIRS  SNPP     N   n   0    2    310 285 0.5  0.5
#     V3*  18.8  -98.9   2024-04-17 20:00   VIIRS  NOAA-20  D   l   0    NULL 300 280 0.6  0.4
#     O    25.0 -105.0   2024-04-15 17:00   MODIS  Terra    D   90  0    99   400 310 1.0  1.0  (outside)
#
# M2 is stored with the wrong ``confidence`` ("nominal") on purpose: the
# normalized view must recompute "low" from its raw value 29.


def _stats_row(
    name: str, lat: float, lon: float, when: str, instrument: str, satellite: str, daynight: str,
    raw: str, fire_type: int | None, frp: float | None, mir: float, tir: float, scan: float, track: float,
    stored_confidence: str = "nominal",
) -> dict[str, Any]:
    """Build one stats test row (``name`` is stored in ``version``)."""
    acquired_at = datetime.fromisoformat(when)
    return {
        "latitude": lat, "longitude": lon, "acquired_at": acquired_at, "acq_date": acquired_at.date(),
        "instrument": instrument, "satellite": satellite, "source": None, "daynight": daynight,
        "bright_mir": mir, "bright_tir": tir, "frp": frp, "pixel_scan": scan, "pixel_track": track,
        "confidence": stored_confidence, "confidence_raw": raw, "fire_type": fire_type, "version": name,
    }


STATS_ROWS: list[dict[str, Any]] = [
    _stats_row("M1", 19.0, -99.0, "2024-04-15 19:42", "MODIS", "Terra", "D", "85", 0, 10, 320, 295, 1.0, 1.0, "high"),
    _stats_row("M2", 19.2, -99.2, "2024-04-15 20:10", "MODIS", "Aqua", "D", "29", 0, 30, 340, 300, 2.0, 1.5),
    _stats_row("M3", 18.6, -98.6, "2024-04-16 05:00", "MODIS", "Terra", "N", "30", 2, 50, 360, 305, 3.0, 2.0),
    _stats_row("V1", 19.1, -99.1, "2024-04-15 19:00", "VIIRS", "NOAA-20", "D", "h", None, 5, 330, 290, 0.4, 0.4, "high"),
    _stats_row("V2", 18.4, -99.6, "2024-04-15 08:00", "VIIRS", "SNPP", "N", "n", 0, 2, 310, 285, 0.5, 0.5),
    _stats_row("V3", 18.8, -98.9, "2024-04-17 20:00", "VIIRS", "NOAA-20", "D", "l", 0, None, 300, 280, 0.6, 0.4, "low"),
    _stats_row("O", 25.0, -105.0, "2024-04-15 17:00", "MODIS", "Terra", "D", "90", 0, 99, 400, 310, 1.0, 1.0, "high"),
]


@pytest.fixture(scope="session")
def stats_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create the stats test database (with the ``hotspots_normalized`` view) once."""
    path = tmp_path_factory.mktemp("stats_db") / "stats_hotspots.duckdb"
    with duckdb.connect(str(path)) as connection:
        create_hotspots_table(connection)
        bulk_insert_hotspots(connection, STATS_ROWS)
    return path


@pytest.fixture()
def stats_client(stats_db_path: Path) -> Iterator[FlaskClient]:
    """Test client bound to the stats database (``MAX_LIMIT`` = 100 to test the bound)."""
    flask_app = create_app(make_settings(stats_db_path, max_limit=100))
    flask_app.config["TESTING"] = True
    yield flask_app.test_client()
    flask_app.extensions["hotspots_db"].close()


@pytest.fixture()
def get_stats(stats_client: FlaskClient) -> Callable[..., TestResponse]:
    """Call ``/api/v1/stats/<endpoint>`` with :data:`BASE_QUERY` plus overrides.

    Passing ``name=None`` removes a parameter from the query.
    """

    def _get(endpoint: str, **overrides: Any) -> TestResponse:
        params = {**BASE_QUERY, **overrides}
        params = {key: value for key, value in params.items() if value is not None}
        return stats_client.get(f"/api/v1/stats/{endpoint}", query_string=params)

    return _get
