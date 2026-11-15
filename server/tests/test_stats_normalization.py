"""Tests for the normalized projection used by the stats endpoints (``NORMALIZED_HOTSPOTS_SQL``)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from app.repository import NORMALIZED_HOTSPOTS_SQL, bulk_insert_hotspots, create_hotspots_table
from scripts.import_json import normalize_record
from tests.test_import import RAW_MODIS


def _normalized(connection: duckdb.DuckDBPyConnection, where: str = "") -> list[dict]:
    """Return the rows of the normalized projection as dicts."""
    result = connection.execute(f"SELECT * FROM ({NORMALIZED_HOTSPOTS_SQL}) AS h {where}")
    names = [column[0] for column in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


@pytest.fixture()
def memory_db() -> duckdb.DuckDBPyConnection:
    """Empty in-memory database with the table and the view."""
    connection = duckdb.connect()
    create_hotspots_table(connection)
    yield connection
    connection.close()


def test_view_columns_and_types(stats_db_path: Path) -> None:
    with duckdb.connect(str(stats_db_path), read_only=True) as connection:
        result = connection.execute("SELECT * FROM hotspots_normalized LIMIT 0")
        types = {column[0]: str(column[1]) for column in result.description}
    assert types == {
        "sensor": "VARCHAR",
        "satellite": "VARCHAR",
        "timestamp_utc": "TIMESTAMP",
        "acq_date": "DATE",
        "lat": "DOUBLE",
        "lon": "DOUBLE",
        "bright_mir": "DOUBLE",
        "bright_tir": "DOUBLE",
        "frp": "DOUBLE",
        "confidence_level": "VARCHAR",
        "confidence_raw": "VARCHAR",
        "daynight": "VARCHAR",
        "type": "INTEGER",
        "scan": "DOUBLE",
        "track": "DOUBLE",
        "pixel_area_km2": "DOUBLE",
    }


def test_view_values(stats_db_path: Path) -> None:
    with duckdb.connect(str(stats_db_path), read_only=True) as connection:
        rows = {row["frp"]: row for row in _normalized(connection, "WHERE sensor = 'MODIS'")}
    m2 = rows[30]
    assert m2["sensor"] == "MODIS"
    assert m2["timestamp_utc"] == datetime(2024, 4, 15, 20, 10)
    assert m2["pixel_area_km2"] == pytest.approx(3.0)  # scan 2.0 * track 1.5
    # Stored as "nominal" on purpose: the view recomputes it from the raw value 29.
    assert m2["confidence_level"] == "low"
    assert rows[50]["type"] == 2


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0", "low"), ("29", "low"), ("30", "nominal"), ("79", "nominal"), ("80", "high"), ("100", "high")],
)
def test_modis_confidence_mapping(memory_db: duckdb.DuckDBPyConnection, raw: str, expected: str) -> None:
    record, _ = normalize_record({**RAW_MODIS, "confidence": raw})
    record["confidence"] = None  # prove the level comes from the raw value
    bulk_insert_hotspots(memory_db, [record])
    assert _normalized(memory_db)[0]["confidence_level"] == expected


@pytest.mark.parametrize(("raw", "expected"), [("l", "low"), ("n", "nominal"), ("h", "high")])
def test_viirs_confidence_mapping(memory_db: duckdb.DuckDBPyConnection, raw: str, expected: str) -> None:
    record, _ = normalize_record({**_raw_viirs(), "confidence": raw})
    record["confidence"] = None
    bulk_insert_hotspots(memory_db, [record])
    assert _normalized(memory_db)[0]["confidence_level"] == expected


def _raw_viirs() -> dict:
    """A raw FIRMS VIIRS record (375 m product: ``bright_ti4``/``bright_ti5``)."""
    return {
        "latitude": 24.1,
        "longitude": -104.6,
        "acq_date": "2023-03-05",
        "acq_time": "757",
        "satellite": "N20",
        "instrument": "VIIRS",
        "daynight": "N",
        "bright_ti4": 340.5,
        "bright_ti5": 290.25,
        "frp": 7.5,
        "scan": 0.39,
        "track": 0.36,
        "confidence": "n",
        "version": "2.0NRT",
    }


def test_raw_viirs_record_through_view(memory_db: duckdb.DuckDBPyConnection) -> None:
    record, _ = normalize_record(_raw_viirs())
    bulk_insert_hotspots(memory_db, [record])
    row = _normalized(memory_db)[0]
    assert row["sensor"] == "VIIRS"
    assert row["satellite"] == "NOAA-20"
    assert row["bright_mir"] == 340.5  # bright_ti4
    assert row["bright_tir"] == 290.25  # bright_ti5
    # acq_time "757" is zero-padded to 07:57 UTC.
    assert row["timestamp_utc"] == datetime(2023, 3, 5, 7, 57)
    assert row["confidence_level"] == "nominal"
    assert row["type"] is None  # missing type stays unknown, never 0
    assert row["pixel_area_km2"] == pytest.approx(0.39 * 0.36)


def test_raw_modis_record_through_view(memory_db: duckdb.DuckDBPyConnection) -> None:
    record, _ = normalize_record({**RAW_MODIS, "type": "0"})
    bulk_insert_hotspots(memory_db, [record])
    row = _normalized(memory_db)[0]
    assert (row["sensor"], row["satellite"]) == ("MODIS", "Terra")
    assert (row["bright_mir"], row["bright_tir"]) == (330.1, 300.2)  # brightness, bright_t31
    assert row["timestamp_utc"] == datetime(2010, 4, 20, 19, 30)
    assert row["type"] == 0
    assert row["confidence_raw"] == "67"
    assert row["confidence_level"] == "nominal"
