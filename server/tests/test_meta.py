"""Tests for ``GET /health`` and ``GET /api/v1/dataset``."""

from __future__ import annotations

from pathlib import Path

import duckdb

from app import create_app
from tests.conftest import BASE_QUERY, make_settings


def test_health_ok(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "database": "connected"}


def test_health_without_database(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path / "missing.duckdb"))
    client = app.test_client()

    response = client.get("/health")
    assert response.status_code == 503
    assert response.get_json() == {"status": "error", "database": "unavailable"}

    response = client.get("/api/v1/hotspots", query_string=BASE_QUERY)
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "DATABASE_UNAVAILABLE"


def test_health_with_database_without_table(tmp_path: Path) -> None:
    path = tmp_path / "empty.duckdb"
    duckdb.connect(str(path)).close()
    response = create_app(make_settings(path)).test_client().get("/health")
    assert response.status_code == 503


def test_dataset_summary(client) -> None:
    response = client.get("/api/v1/dataset")
    assert response.status_code == 200
    assert response.get_json() == {
        "total_records": 7,
        "min_date": "2024-04-15",
        "max_date": "2024-05-10",
        "instruments": {"MODIS": 3, "VIIRS": 4},
        "bbox": [-105.0, 18.2, -98.0, 25.0],
    }
