"""Tests of ``GET /api/v1/calendar?harmonized=true`` and the stored parameters.

Synthetic database (area lat 19..20, lon -99..-98), built so every value is exact::

    month    rows                                                   expected
    2001-03  Terra D ×10                                            Terra × factor = 10 × 2.5 = 25
    2005-03  Terra D ×4, Aqua D ×6                                  MODIS = 10 (and factor = 10 / 4)
    2013-03  Terra D ×2, Aqua D ×3, Terra N ×1, SNPP D ×20, N ×8    r_day = 20/5 = 4, r_night = 8/1 = 8
                                                                    MODIS 6, MODIS_eq 20/4 + 8/8 = 6 → 6
             + Terra D type 2 (static source) and NOAA-20 D        both ignored
    2014-03  Terra D ×1, SNPP D ×4 with type NULL (like NRT)        (1 + 4/4) / 2 = 1

One SNPP row in 2012-03 starts the VIIRS coverage, so March 2013 is fully covered by both
sensors (a sensor only enters the average when it covers every loaded day of the month).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pytest
from flask.testing import FlaskClient

from app import create_app
from harmonizer.config import HarmonizationConfig
from harmonizer.params import fit_params, load_params, save_params
from tests.conftest import _row, make_settings

CONFIG = HarmonizationConfig(
    fit_start=date(2013, 1, 1), fit_end=date(2013, 12, 31),
    terra_fit_start=date(2005, 1, 1), terra_fit_end=date(2005, 12, 31),
    min_reliable_count=5,
)
AREA: dict[str, Any] = {"lat1": 19, "lon1": -99, "lat2": 20, "lon2": -98, "harmonized": "true"}


def _rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(month: str, n: int, instrument: str, sat: str, dn: str, fire_type: int | None = 0) -> None:
        for _ in range(n):
            when = datetime.fromisoformat(f"{month}-10 12:00") + timedelta(minutes=len(rows))
            conf = "n" if instrument == "VIIRS" else "70"
            rows.append(_row(f"r{len(rows)}", 19.5, -98.5, when.isoformat(" "), instrument, sat, dn,
                             "nominal", conf, fire_type))

    add("2001-03", 10, "MODIS", "Terra", "D")
    add("2005-03", 4, "MODIS", "Terra", "D")
    add("2005-03", 6, "MODIS", "Aqua", "D")
    add("2012-03", 1, "VIIRS", "SNPP", "D")  # VIIRS coverage starts before the fit month
    add("2013-03", 2, "MODIS", "Terra", "D")
    add("2013-03", 3, "MODIS", "Aqua", "D")
    add("2013-03", 1, "MODIS", "Terra", "N")
    add("2013-03", 20, "VIIRS", "SNPP", "D")
    add("2013-03", 8, "VIIRS", "SNPP", "N")
    add("2013-03", 1, "MODIS", "Terra", "D", fire_type=2)
    add("2013-03", 1, "VIIRS", "NOAA-20", "D")
    add("2014-03", 1, "MODIS", "Terra", "D")
    add("2014-03", 4, "VIIRS", "SNPP", "D", fire_type=None)
    return rows


@pytest.fixture(scope="module")
def harm_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from app.repository import bulk_insert_hotspots, create_hotspots_table

    path = tmp_path_factory.mktemp("harm") / "harm.duckdb"
    with duckdb.connect(str(path)) as connection:
        create_hotspots_table(connection)
        bulk_insert_hotspots(connection, _rows())
    return path


@pytest.fixture()
def harm_client(harm_db: Path) -> Iterator[FlaskClient]:
    app = create_app(make_settings(harm_db, harmonization=CONFIG))
    app.config["TESTING"] = True
    yield app.test_client()
    app.extensions["hotspots_db"].close()


def _month(body: dict[str, Any], year: int, month: int) -> dict[str, Any]:
    return next(m for m in body["months"] if (m["year"], m["month"]) == (year, month))


def test_fit_params_from_synthetic_data(harm_db: Path) -> None:
    with duckdb.connect(str(harm_db), read_only=True) as c:
        params = fit_params(c, CONFIG)
    assert (params.ratios.day, params.ratios.night) == (4.0, 8.0)
    assert params.ratios.total == pytest.approx(28 / 6)
    assert params.terra_factor == 2.5
    assert params.min_reliable_count == 5


def test_params_round_trip_through_the_table(tmp_path: Path, harm_db: Path) -> None:
    copy = tmp_path / "copy.duckdb"
    copy.write_bytes(harm_db.read_bytes())
    with duckdb.connect(str(copy)) as c:
        save_params(c, fit_params(c, CONFIG))
        loaded = load_params(c)
    assert loaded is not None
    assert (loaded.ratios.day, loaded.ratios.night, loaded.terra_factor) == (4.0, 8.0, 2.5)
    assert loaded.fit_start == date(2013, 1, 1)
    assert loaded.ratios.modis_day == 5 and loaded.ratios.viirs_night == 8


def test_harmonized_values_and_sources(harm_client: FlaskClient) -> None:
    response = harm_client.get("/api/v1/calendar", query_string=AREA)
    assert response.status_code == 200
    body = response.get_json()
    assert body["harmonized"] is True
    assert body["coverage"] == {"start_date": "2001-03-10", "end_date": "2014-03-10"}

    terra_only = _month(body, 2001, 3)
    assert (terra_only["count"], terra_only["source"], terra_only["terra"]) == (25.0, "terra_scaled", 10)
    modis = _month(body, 2005, 3)
    assert (modis["count"], modis["source"]) == (10.0, "modis")
    blend = _month(body, 2013, 3)
    assert (blend["count"], blend["source"], blend["modis_eq"]) == (6.0, "average", 6.0)
    assert (blend["modis"], blend["viirs"], blend["viirs_day"], blend["viirs_night"]) == (6, 28, 20, 8)
    nrt_like = _month(body, 2014, 3)
    assert (nrt_like["count"], nrt_like["source"]) == (1.0, "average")
    zero = _month(body, 2008, 6)
    assert (zero["count"], zero["source"]) == (0.0, "modis")


def test_harmonization_block_and_reliability(harm_client: FlaskClient) -> None:
    h = harm_client.get("/api/v1/calendar", query_string=AREA).get_json()["harmonization"]
    assert (h["r_day"], h["r_night"], h["terra_factor"]) == (4.0, 8.0, 2.5)
    assert h["fit_period"] == {"start_date": "2013-01-01", "end_date": "2013-12-31"}
    assert h["fit_detections"] == {"modis": 6, "viirs": 28}
    assert h["cutoffs"] == {"aqua_start": "2002-08-01", "viirs_start": "2012-02-01", "modis_end": None}
    rel = h["reliability"]
    assert rel["area_deg2"] == 1.0 and rel["small_area"] is False
    assert rel["low_count"] is True  # typical month is far below 5


def test_small_area_is_flagged(harm_client: FlaskClient) -> None:
    body = harm_client.get("/api/v1/calendar", query_string={**AREA, "lat2": 19.6, "lon2": -98.4}).get_json()
    assert body["harmonization"]["reliability"]["small_area"] is True
    assert _month(body, 2013, 3)["low_count"] is False  # 6 ≥ 5
    assert _month(body, 2014, 3)["low_count"] is True


@pytest.mark.parametrize("param", [{"instrument": "MODIS"}, {"daynight": "D"}, {"confidence_min": "high"}])
def test_harmonized_rejects_sensor_filters(harm_client: FlaskClient, param: dict[str, str]) -> None:
    response = harm_client.get("/api/v1/calendar", query_string={**AREA, **param})
    assert response.status_code == 400
    assert response.get_json()["error"]["parameter"] == next(iter(param))


def test_raw_calendar_is_unchanged(harm_client: FlaskClient) -> None:
    body = harm_client.get("/api/v1/calendar", query_string={**AREA, "harmonized": "false"}).get_json()
    assert body["harmonized"] is False
    assert "harmonization" not in body
    assert _month(body, 2013, 3)["count"] == 36
