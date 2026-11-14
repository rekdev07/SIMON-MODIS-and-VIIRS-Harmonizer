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
