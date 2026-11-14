"""Tests for the normalization and loading rules of ``scripts/import_json.py``."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest

from scripts.import_json import (
    RejectedRecord,
    classify_confidence,
    import_records,
    load_records,
    main,
    normalize_record,
    normalize_satellite,
    pad_acq_time,
)

RAW_VIIRS: dict[str, Any] = {
    "latitude": 20.94378,
    "longitude": -89.66471,
    "acq_date": "2013-01-01",
    "acq_time": "0757",
    "satellite": "SNPP",
    "daynight": "N",
    "brightness": 312.56,
    "type": "2",
    "bright_t31": 291.96,
    "version": "2",
    "confidence": "n",
    "scan": 0.41,
    "track": 0.45,
    "instrument": "SNPP",
    "frp": 1.19,
}

RAW_MODIS: dict[str, Any] = {
    "latitude": "19.5",
    "longitude": "-99.1",
    "acq_date": "2010-04-20",
    "acq_time": 1930,
    "satellite": "T",
    "daynight": "D",
    "brightness": "330.1",
    "bright_t31": "300.2",
    "confidence": 67,
    "scan": "1.2",
    "track": "1.1",
    "version": "6.1",
    "frp": "25.3",
}


def test_raw_viirs_record_normalized() -> None:
    record, known = normalize_record(RAW_VIIRS)
    assert known
    assert record == {
        "latitude": 20.94378,
        "longitude": -89.66471,
        "acquired_at": datetime(2013, 1, 1, 7, 57),
        "acq_date": datetime(2013, 1, 1).date(),
        "instrument": "VIIRS",  # not "SNPP" from the raw field
        "satellite": "SNPP",
        "source": None,
        "daynight": "N",
        "bright_mir": 312.56,
        "bright_tir": 291.96,
        "frp": 1.19,
        "pixel_scan": 0.41,
        "pixel_track": 0.45,
        "confidence": "nominal",
        "confidence_raw": "n",
        "fire_type": 2,  # "2" -> 2
        "version": "2",
    }


def test_raw_modis_record_normalized() -> None:
    record, _ = normalize_record(RAW_MODIS)
    assert record["instrument"] == "MODIS"
    assert record["satellite"] == "Terra"
    assert record["confidence"] == "nominal"
    assert record["confidence_raw"] == "67"
    assert record["latitude"] == 19.5 and record["bright_mir"] == 330.1
    assert record["fire_type"] is None  # missing type -> NULL, never 0


@pytest.mark.parametrize(("raw", "expected"), [("757", "0757"), (757, "0757"), ("5", "0005"),
                                                ("0000", "0000"), ("2359", "2359"), ("07:57", "0757")])
def test_acq_time_padding(raw: Any, expected: str) -> None:
    assert pad_acq_time(raw) == expected


def test_padded_time_used_in_timestamp() -> None:
    record, _ = normalize_record({**RAW_VIIRS, "acq_time": "757"})
    assert record["acquired_at"] == datetime(2013, 1, 1, 7, 57)


@pytest.mark.parametrize(
    ("raw", "category", "hint"),
    [
        (0, "low", "MODIS"),
        ("29", "low", "MODIS"),
        ("30", "nominal", "MODIS"),
        (79, "nominal", "MODIS"),
        ("80", "high", "MODIS"),
        (100, "high", "MODIS"),
        ("l", "low", "VIIRS"),
        ("n", "nominal", "VIIRS"),
        ("H", "high", "VIIRS"),
        ("nominal", "nominal", None),
        ("xyz", None, None),
        (None, None, None),
    ],
)
def test_confidence_classification(raw: Any, category: str | None, hint: str | None) -> None:
    result_category, _, result_hint = classify_confidence(raw)
    assert (result_category, result_hint) == (category, hint)


@pytest.mark.parametrize(
    ("code", "name", "known"),
    [("T", "Terra", True), ("A", "Aqua", True), ("N", "SNPP", True), ("N20", "NOAA-20", True),
     ("1", "NOAA-20", True), ("N21", "NOAA-21", True), ("snpp", "SNPP", True), ("X9", "X9", False)],
)
def test_satellite_codes(code: str, name: str, known: bool) -> None:
    assert normalize_satellite(code) == (name, known)


def test_unknown_satellite_kept_with_confidence_rule() -> None:
    record, known = normalize_record({**RAW_VIIRS, "satellite": "X9"})
    assert not known
    assert record["satellite"] == "X9"
    assert record["instrument"] == "VIIRS"  # deduced from "n" confidence


def test_instrument_from_satellite_overrides_raw_field() -> None:
    record, _ = normalize_record({**RAW_MODIS, "satellite": "A", "instrument": "VIIRS"})
    assert record["instrument"] == "MODIS"


def test_viirs_alternative_brightness_fields() -> None:
    raw = {**RAW_VIIRS, "bright_ti4": 340.0, "bright_ti5": 290.0}
    del raw["brightness"], raw["bright_t31"]
    record, _ = normalize_record(raw)
    assert (record["bright_mir"], record["bright_tir"]) == (340.0, 290.0)


def test_already_normalized_record_accepted() -> None:
    normalized = {
        "latitude": 19.0, "longitude": -99.0, "acquired_at": "2024-04-15T19:42:00Z",
        "instrument": "VIIRS", "satellite": "NOAA-20", "source": "VIIRS_NOAA20_NRT",
        "daynight": "D", "bright_mir": 330.0, "bright_tir": 295.0, "frp": None,
        "pixel_scan": 0.4, "pixel_track": 0.4, "confidence": "nominal",
        "confidence_raw": "n", "fire_type": None, "version": "2.0NRT",
    }
    record, _ = normalize_record(normalized)
    assert record["acquired_at"] == datetime(2024, 4, 15, 19, 42)
    assert record["source"] == "VIIRS_NOAA20_NRT"
    assert record["confidence"] == "nominal" and record["fire_type"] is None


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"latitude": None}, "missing_coordinates"),
        ({"longitude": ""}, "missing_coordinates"),
        ({"latitude": "abc"}, "invalid_coordinates"),
        ({"latitude": 95}, "out_of_range_coordinates"),
        ({"longitude": -190}, "out_of_range_coordinates"),
        ({"acq_date": None}, "missing_date"),
        ({"acq_date": "2013-13-01"}, "invalid_date"),
        ({"acq_time": None}, "missing_time"),
        ({"acq_time": "2575"}, "invalid_time"),
    ],
)
def test_incomplete_records_rejected(changes: dict[str, Any], reason: str) -> None:
    with pytest.raises(RejectedRecord) as error:
        normalize_record({**RAW_VIIRS, **changes})
    assert error.value.reason == reason


def test_import_skips_duplicates_and_rejects(tmp_path: Path) -> None:
    db_path = tmp_path / "import.duckdb"
    records = [RAW_VIIRS, dict(RAW_VIIRS), RAW_MODIS, {**RAW_VIIRS, "latitude": None}]

    stats = import_records(records, db_path)
    assert stats.read == 4
    assert stats.inserted == 2
    assert stats.duplicates_in_file == 1
    assert stats.rejected == {"missing_coordinates": 1}
    assert stats.instruments == {"VIIRS": 1, "MODIS": 1}

    again = import_records([RAW_VIIRS, RAW_MODIS], db_path)
    assert again.inserted == 0
    assert again.duplicates_in_db == 2

    with duckdb.connect(str(db_path), read_only=True) as connection:
        assert connection.execute("SELECT count(*) FROM hotspots").fetchone()[0] == 2
        assert connection.execute(
            "SELECT fire_type FROM hotspots WHERE instrument = 'MODIS'"
        ).fetchone()[0] is None


@pytest.mark.parametrize(
    "payload",
    [
        [RAW_VIIRS],
        {"data": [RAW_VIIRS]},
        {"type": "FeatureCollection", "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-89.66471, 20.94378]},
            "properties": {k: v for k, v in RAW_VIIRS.items() if k not in ("latitude", "longitude")},
        }]},
    ],
)
def test_load_records_layouts(tmp_path: Path, payload: Any) -> None:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload))
    records, _ = load_records(path)
    record, _ = normalize_record(records[0])
    assert (record["latitude"], record["longitude"]) == (20.94378, -89.66471)


def test_load_ndjson(tmp_path: Path) -> None:
    path = tmp_path / "input.ndjson"
    path.write_text(json.dumps(RAW_VIIRS) + "\n" + json.dumps(RAW_MODIS) + "\n")
    records, layout = load_records(path)
    assert len(records) == 2 and "newline" in layout


def test_cli_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "input.json"
    source.write_text(json.dumps([RAW_VIIRS, RAW_MODIS]))
    assert main([str(source), "--db", str(tmp_path / "cli.duckdb")]) == 0
    output = capsys.readouterr().out
    assert "Inserted:            2" in output
    assert "MODIS: 1" in output and "VIIRS: 1" in output
