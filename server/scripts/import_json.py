"""Import a FIRMS hotspots JSON file into the DuckDB ``hotspots`` table.

Usage (from ``server/``)::

    python scripts/import_json.py data/raw/fire_archive_SV-C2_849193.json --db data/hotspots.duckdb

What it does:

1. **Inspects** the file: detects its structure (JSON list, object wrapping a
   list, GeoJSON FeatureCollection or newline-delimited JSON) and prints the
   field names found and how often each appears.
2. **Normalizes** each record to the API schema (see :func:`normalize_record`
   and ``docs/data-import.md``). Records may come in raw FIRMS format or
   already normalized.
3. **Rejects** records that cannot be placed in space and time (missing or
   out-of-range coordinates, missing or invalid date/time), logs them and does
   not store them.
4. **Inserts** valid records, skipping duplicates of the primary key
   ``(instrument, satellite, latitude, longitude, acquired_at)``.
5. Prints a **summary**: read, inserted, rejected per reason, duplicates,
   date range and count per instrument.

Stop the API before importing: DuckDB does not allow another process to write
to a file that the API has open.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# Allow "python scripts/import_json.py" from server/ to import the app package.
SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import duckdb  # noqa: E402

from app.repository import bulk_insert_hotspots, create_hotspots_table  # noqa: E402

logger = logging.getLogger("import_json")

#: Satellite codes found in FIRMS files → canonical names.
#: Keys are upper-case; lookup is case-insensitive.
SATELLITE_CODES: dict[str, str] = {
    "T": "Terra",
    "TERRA": "Terra",
    "A": "Aqua",
    "AQUA": "Aqua",
    "N": "SNPP",
    "SNPP": "SNPP",
    "NPP": "SNPP",
    "SUOMI-NPP": "SNPP",
    "N20": "NOAA-20",
    "1": "NOAA-20",
    "NOAA-20": "NOAA-20",
    "NOAA20": "NOAA-20",
    "J1": "NOAA-20",
    "N21": "NOAA-21",
    "NOAA-21": "NOAA-21",
    "NOAA21": "NOAA-21",
    "J2": "NOAA-21",
}

MODIS_SATELLITES = frozenset({"Terra", "Aqua"})
VIIRS_SATELLITES = frozenset({"SNPP", "NOAA-20", "NOAA-21"})

#: VIIRS confidence letters → categories.
VIIRS_CONFIDENCE: dict[str, str] = {"L": "low", "N": "nominal", "H": "high"}
CATEGORIES = frozenset({"low", "nominal", "high"})

#: Alternative field names, in order of preference, for each target column.
MIR_FIELDS = ("bright_mir", "brightness", "bright_ti4")
TIR_FIELDS = ("bright_tir", "bright_t31", "bright_ti5", "brightness_2")
SCAN_FIELDS = ("pixel_scan", "scan")
TRACK_FIELDS = ("pixel_track", "track")
TYPE_FIELDS = ("fire_type", "type")

#: Keys that may wrap the list of records in a JSON object.
WRAPPER_KEYS = ("data", "records", "hotspots", "features", "items", "results")

#: How many rejected records are logged individually per reason (the rest are only counted).
LOG_EXAMPLES_PER_REASON = 20


class RejectedRecord(ValueError):
    """A record cannot be stored.

    Attributes:
        reason: Short machine-friendly reason, used to group the summary.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        """Create the error.

        Args:
            reason: Short reason such as ``"missing_coordinates"``.
            detail: Optional human detail for the log.
        """
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


# --------------------------------------------------------------------------- #
# Small value helpers
# --------------------------------------------------------------------------- #


def _is_blank(value: Any) -> bool:
    """Tell whether a value is missing (None or an empty/whitespace string).

    Args:
        value: Raw value.

    Returns:
        True when the value should be treated as missing.
    """
    return value is None or (isinstance(value, str) and not value.strip())


def _first_present(record: dict[str, Any], names: tuple[str, ...]) -> Any:
    """Return the value of the first field in ``names`` that is present and not blank.

    Args:
        record: Raw record.
        names: Candidate field names, in priority order.

    Returns:
        The value, or None if none is present.
    """
    for name in names:
        value = record.get(name)
        if not _is_blank(value):
            return value
    return None


def to_float(value: Any) -> float | None:
    """Convert numbers and numeric strings to float (``"12.5"`` → ``12.5``).

    Args:
        value: Raw value.

    Returns:
        The float, or None if the value is missing or not numeric.
    """
    if _is_blank(value) or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and result not in (float("inf"), float("-inf")) else None


def to_int(value: Any) -> int | None:
    """Convert integers and integer-like strings (``"2"``, ``"2.0"``) to int.

    Args:
        value: Raw value.

    Returns:
        The integer, or None if missing or not a whole number.
    """
    number = to_float(value)
    if number is None or not number.is_integer():
        return None
    return int(number)


def _to_text(value: Any) -> str | None:
    """Convert a value to a stripped string (``2`` → ``"2"``), or None if blank.

    Args:
        value: Raw value.

    Returns:
        The string or None.
    """
    if _is_blank(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


# --------------------------------------------------------------------------- #
# Field rules
# --------------------------------------------------------------------------- #


def pad_acq_time(raw_time: Any) -> str:
    """Normalize a FIRMS ``acq_time`` to four digits ``HHMM``.

    FIRMS stores the time as an integer-like ``HHMM`` value, so leading zeros
    are often lost: ``757`` means 07:57 and ``5`` means 00:05. Left-padding
    with zeros to 4 characters restores the ``HHMM`` layout. ``"07:57"`` is
    also accepted.

    Args:
        raw_time: Value such as ``"0757"``, ``"757"``, ``757`` or ``"07:57"``.

    Returns:
        The padded string, e.g. ``"0757"``.

    Raises:
        RejectedRecord: If the value is not a valid ``HHMM`` time.

    Example:
        >>> pad_acq_time(757)
        '0757'
    """
    text = _to_text(raw_time)
    if text is None:
        raise RejectedRecord("missing_time")
    text = text.replace(":", "")
    if not text.isdigit() or len(text) > 4:
        raise RejectedRecord("invalid_time", repr(raw_time))
    text = text.zfill(4)
    if int(text[:2]) > 23 or int(text[2:]) > 59:
        raise RejectedRecord("invalid_time", repr(raw_time))
    return text


def build_acquired_at(record: dict[str, Any]) -> datetime:
    """Compute the UTC acquisition timestamp of a record.

    How: if the record is already normalized and has ``acquired_at`` (ISO
    string, ``Z`` or offset allowed), it is parsed and converted to UTC.
    Otherwise ``acquired_at = acq_date + acq_time`` where ``acq_time`` is padded
    by :func:`pad_acq_time`. FIRMS dates and times are always UTC.

    The result is a naive ``datetime`` that is UTC by convention (DuckDB
    ``TIMESTAMP`` has no time zone).

    Args:
        record: Raw record.

    Returns:
        The naive UTC timestamp.

    Raises:
        RejectedRecord: If the date or time is missing or invalid.
    """
    raw_acquired = record.get("acquired_at")
    if not _is_blank(raw_acquired):
        try:
            parsed = datetime.fromisoformat(str(raw_acquired).strip())
        except ValueError:
            raise RejectedRecord("invalid_datetime", repr(raw_acquired)) from None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    raw_date = record.get("acq_date")
    if _is_blank(raw_date):
        raise RejectedRecord("missing_date")
    try:
        day = date.fromisoformat(str(raw_date).strip()[:10])
    except ValueError:
        raise RejectedRecord("invalid_date", repr(raw_date)) from None
    hhmm = pad_acq_time(record.get("acq_time"))
    return datetime(day.year, day.month, day.day, int(hhmm[:2]), int(hhmm[2:]))


def normalize_satellite(raw: Any) -> tuple[str, bool]:
    """Map a FIRMS satellite code to its canonical name.

    ``T`` → Terra, ``A`` → Aqua, ``N`` → SNPP, ``N20``/``1`` → NOAA-20,
    ``N21`` → NOAA-21 (full names are accepted too). Unknown codes are kept
    as-is so no information is lost; the caller logs them.

    Args:
        raw: Raw satellite value.

    Returns:
        ``(name, known)``: the canonical name (or the original text) and whether
        the code was recognized.

    Raises:
        RejectedRecord: If the satellite is missing (it is part of the primary key).
    """
    text = _to_text(raw)
    if text is None:
        raise RejectedRecord("missing_satellite")
    canonical = SATELLITE_CODES.get(text.upper())
    return (canonical, True) if canonical else (text, False)


def classify_confidence(raw: Any) -> tuple[str | None, str | None, str | None]:
    """Convert a raw confidence into a category and tell which sensor it looks like.

    Rules:

    * **MODIS** gives a number from 0 to 100:
      ``value < 30`` → ``low``; ``30 <= value < 80`` → ``nominal``;
      ``value >= 80`` → ``high``. These are the thresholds FIRMS documents for
      MODIS.
    * **VIIRS** gives a letter: ``l`` → ``low``, ``n`` → ``nominal``,
      ``h`` → ``high`` (case-insensitive).
    * Already-normalized words (``low``/``nominal``/``high``) are accepted.

    Args:
        raw: Raw confidence value (``67``, ``"67"``, ``"n"``, ...).

    Returns:
        ``(category, raw_text, sensor_hint)`` where ``sensor_hint`` is
        ``"MODIS"`` for numbers, ``"VIIRS"`` for letters and None otherwise.
        ``category`` is None when the value is missing or not understood.

    Example:
        >>> classify_confidence("67")
        ('nominal', '67', 'MODIS')
        >>> classify_confidence("h")
        ('high', 'h', 'VIIRS')
    """
    raw_text = _to_text(raw)
    if raw_text is None:
        return None, None, None
    letter = VIIRS_CONFIDENCE.get(raw_text.upper())
    if letter:
        return letter, raw_text, "VIIRS"
    if raw_text.lower() in CATEGORIES:
        return raw_text.lower(), raw_text, None
    number = to_float(raw_text)
    if number is None or not 0 <= number <= 100:
        return None, raw_text, None
    if number < 30:
        category = "low"
    elif number < 80:
        category = "nominal"
    else:
        category = "high"
    return category, raw_text, "MODIS"


def deduce_instrument(satellite: str, confidence_hint: str | None, raw_instrument: Any) -> str:
    """Decide whether a detection comes from MODIS or VIIRS.

    Why: the raw ``instrument`` field is not reliable (some FIRMS exports put
    the satellite there, e.g. ``"SNPP"``). The satellite and the confidence
    format are reliable fingerprints:

    1. Satellite Terra or Aqua → MODIS; SNPP, NOAA-20 or NOAA-21 → VIIRS.
    2. Otherwise numeric confidence → MODIS; ``l``/``n``/``h`` → VIIRS.
    3. Otherwise, only if the raw field literally says ``MODIS`` or ``VIIRS``, use it.

    Args:
        satellite: Canonical (or unknown) satellite name.
        confidence_hint: Sensor hint from :func:`classify_confidence`.
        raw_instrument: Raw ``instrument`` value, used only as a last resort.

    Returns:
        ``"MODIS"`` or ``"VIIRS"``.

    Raises:
        RejectedRecord: If none of the rules applies.
    """
    if satellite in MODIS_SATELLITES:
        return "MODIS"
    if satellite in VIIRS_SATELLITES:
        return "VIIRS"
    if confidence_hint:
        return confidence_hint
    raw_text = (_to_text(raw_instrument) or "").upper()
    if raw_text in {"MODIS", "VIIRS"}:
        return raw_text
    raise RejectedRecord("unknown_instrument", f"satellite={satellite!r}")


def normalize_record(record: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Convert one raw (or already normalized) record into the table schema.

    Field mapping: ``brightness``/``bright_ti4`` → ``bright_mir``;
    ``bright_t31``/``bright_ti5``/``brightness_2`` → ``bright_tir``;
    ``scan`` → ``pixel_scan``; ``track`` → ``pixel_track``; ``type`` →
    ``fire_type``. Numeric strings are converted. A missing ``type`` becomes
    None (never 0, because 0 means "vegetation fire").

    Args:
        record: One record from the input file.

    Returns:
        ``(normalized, satellite_known)``. ``satellite_known`` is False when the
        satellite code was not recognized (kept as-is), so the caller can log it.

    Raises:
        RejectedRecord: If coordinates, date, time, satellite or instrument are
            missing or invalid.
    """
    if not isinstance(record, dict):
        raise RejectedRecord("not_an_object")

    raw_lat, raw_lon = record.get("latitude"), record.get("longitude")
    if _is_blank(raw_lat) or _is_blank(raw_lon):
        raise RejectedRecord("missing_coordinates")
    latitude, longitude = to_float(raw_lat), to_float(raw_lon)
    if latitude is None or longitude is None:
        raise RejectedRecord("invalid_coordinates", f"({raw_lat!r}, {raw_lon!r})")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise RejectedRecord("out_of_range_coordinates", f"({latitude}, {longitude})")

    acquired_at = build_acquired_at(record)
    satellite, satellite_known = normalize_satellite(record.get("satellite"))
    raw_confidence = record.get("confidence_raw")
    if _is_blank(raw_confidence):
        raw_confidence = record.get("confidence")
    confidence, confidence_raw, hint = classify_confidence(raw_confidence)
    instrument = deduce_instrument(satellite, hint, record.get("instrument"))

    daynight = (_to_text(record.get("daynight")) or "").upper()

    normalized = {
        "latitude": latitude,
        "longitude": longitude,
        "acquired_at": acquired_at,
        "acq_date": acquired_at.date(),
        "instrument": instrument,
        "satellite": satellite,
        "source": _to_text(record.get("source")),
        "daynight": daynight if daynight in {"D", "N"} else None,
        "bright_mir": to_float(_first_present(record, MIR_FIELDS)),
        "bright_tir": to_float(_first_present(record, TIR_FIELDS)),
        "frp": to_float(record.get("frp")),
        "pixel_scan": to_float(_first_present(record, SCAN_FIELDS)),
        "pixel_track": to_float(_first_present(record, TRACK_FIELDS)),
        "confidence": confidence,
        "confidence_raw": confidence_raw,
        "fire_type": to_int(_first_present(record, TYPE_FIELDS)),
        "version": _to_text(record.get("version")),
    }
    return normalized, satellite_known


def record_key(record: dict[str, Any]) -> tuple[Any, ...]:
    """Return the primary-key tuple of a normalized record.

    Args:
        record: Normalized record.

    Returns:
        ``(instrument, satellite, latitude, longitude, acquired_at)``.
    """
    return (
        record["instrument"],
        record["satellite"],
        record["latitude"],
        record["longitude"],
        record["acquired_at"],
    )


# --------------------------------------------------------------------------- #
# File loading and inspection
# --------------------------------------------------------------------------- #


def _feature_to_record(feature: dict[str, Any]) -> dict[str, Any]:
    """Flatten a GeoJSON feature into a flat record (properties + coordinates).

    Args:
        feature: GeoJSON ``Feature`` with a ``Point`` geometry.

    Returns:
        The properties plus ``longitude``/``latitude`` taken from the geometry
        when they are not already in the properties.
    """
    record = dict(feature.get("properties") or {})
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coordinates) >= 2:
        record.setdefault("longitude", coordinates[0])
        record.setdefault("latitude", coordinates[1])
    return record


def load_records(path: Path) -> tuple[list[Any], str]:
    """Read the input file and return its records, adapting to its structure.

    Supported layouts:

    * ``[ {...}, {...} ]``: a list of records (FIRMS JSON export).
    * ``{"data": [...]}`` (or ``records``, ``hotspots``, ``items``, ``results``).
    * GeoJSON ``FeatureCollection``: features are flattened.
    * Newline-delimited JSON (one object per line).

    Args:
        path: Input file.

    Returns:
        ``(records, description)`` where ``description`` says which layout was found.

    Raises:
        ValueError: If the file is not in any supported layout.
    """
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
        return records, "newline-delimited JSON"

    if isinstance(payload, list):
        return payload, "JSON list of records"
    if isinstance(payload, dict):
        if payload.get("type") == "FeatureCollection":
            features = payload.get("features") or []
            return [_feature_to_record(f) for f in features], "GeoJSON FeatureCollection"
        for key in WRAPPER_KEYS:
            if isinstance(payload.get(key), list):
                return payload[key], f"JSON object wrapping a list under '{key}'"
        if "latitude" in payload:
            return [payload], "single JSON record"
    raise ValueError("Unsupported JSON structure: expected a list of hotspot records")


def describe_fields(records: list[Any]) -> Counter[str]:
    """Count how many records contain each field name.

    Args:
        records: Raw records.

    Returns:
        A counter ``field name → number of records containing it``.
    """
    fields: Counter[str] = Counter()
    for record in records:
        if isinstance(record, dict):
            fields.update(record.keys())
    return fields


# --------------------------------------------------------------------------- #
# Import pipeline
# --------------------------------------------------------------------------- #


@dataclass
class ImportStats:
    """Counters collected during an import.

    Attributes:
        read: Records read from the file.
        valid: Records that passed normalization.
        inserted: Rows actually inserted.
        rejected: Rejected records per reason.
        duplicates_in_file: Repeated keys inside the input file.
        duplicates_in_db: Keys that already existed in the database.
        unknown_satellites: Unrecognized satellite codes (kept as-is) and counts.
        instruments: Valid records per instrument.
        min_date: Earliest ``acq_date`` among valid records.
        max_date: Latest ``acq_date`` among valid records.
    """

    read: int = 0
    valid: int = 0
    inserted: int = 0
    rejected: Counter[str] = field(default_factory=Counter)
    duplicates_in_file: int = 0
    duplicates_in_db: int = 0
    unknown_satellites: Counter[str] = field(default_factory=Counter)
    instruments: Counter[str] = field(default_factory=Counter)
    min_date: date | None = None
    max_date: date | None = None

    @property
    def duplicates(self) -> int:
        """Total duplicates skipped (inside the file plus already in the database)."""
        return self.duplicates_in_file + self.duplicates_in_db


def normalize_all(records: list[Any], stats: ImportStats) -> list[dict[str, Any]]:
    """Normalize every record, collecting rejections and in-file duplicates.

    Args:
        records: Raw records.
        stats: Counters to update.

    Returns:
        Unique normalized records (first occurrence of each key wins).
    """
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for index, raw in enumerate(records):
        stats.read += 1
        try:
            normalized, satellite_known = normalize_record(raw)
        except RejectedRecord as exc:
            stats.rejected[exc.reason] += 1
            level = logging.WARNING if stats.rejected[exc.reason] <= LOG_EXAMPLES_PER_REASON else logging.DEBUG
            logger.log(level, "Rejected record #%d (%s): %s", index, exc, raw)
            continue
        if not satellite_known:
            if stats.unknown_satellites[normalized["satellite"]] == 0:
                logger.warning("Unknown satellite code kept as-is: %r", normalized["satellite"])
            stats.unknown_satellites[normalized["satellite"]] += 1

        key = record_key(normalized)
        if key in seen:
            stats.duplicates_in_file += 1
            continue
        seen.add(key)
        unique.append(normalized)

        stats.valid += 1
        stats.instruments[normalized["instrument"]] += 1
        day = normalized["acq_date"]
        stats.min_date = day if stats.min_date is None else min(stats.min_date, day)
        stats.max_date = day if stats.max_date is None else max(stats.max_date, day)
    return unique


def import_records(records: list[Any], db_path: Path) -> ImportStats:
    """Normalize ``records`` and insert them into the database at ``db_path``.

    The database file and the table are created if they do not exist.

    Args:
        records: Raw records.
        db_path: DuckDB file to write.

    Returns:
        The import statistics.
    """
    stats = ImportStats()
    unique = normalize_all(records, stats)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db_path)) as connection:
        create_hotspots_table(connection)
        stats.inserted = bulk_insert_hotspots(connection, unique)
    stats.duplicates_in_db = len(unique) - stats.inserted
    return stats


def print_summary(stats: ImportStats, db_path: Path) -> None:
    """Print a human-readable summary of the import.

    Args:
        stats: Import statistics.
        db_path: Database written.
    """
    print("\n=== Import summary ===")
    print(f"Database:            {db_path}")
    print(f"Records read:        {stats.read}")
    print(f"Inserted:            {stats.inserted}")
    print(f"Rejected:            {sum(stats.rejected.values())}")
    for reason, count in stats.rejected.most_common():
        print(f"  - {reason}: {count}")
    print(f"Duplicates skipped:  {stats.duplicates} "
          f"(in file: {stats.duplicates_in_file}, already in DB: {stats.duplicates_in_db})")
    if stats.min_date:
        print(f"Date range (UTC):    {stats.min_date} -> {stats.max_date}")
    print("Valid records per instrument:")
    for instrument, count in sorted(stats.instruments.items()):
        print(f"  - {instrument}: {count}")
    if stats.unknown_satellites:
        print("Unknown satellite codes (kept as-is):")
        for code, count in stats.unknown_satellites.most_common():
            print(f"  - {code!r}: {count}")


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point.

    Args:
        argv: Arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(description="Import FIRMS hotspots JSON into DuckDB.")
    parser.add_argument("json_file", type=Path, help="Input JSON file")
    parser.add_argument("--db", type=Path, default=Path("data/hotspots.duckdb"),
                        help="DuckDB file to create or update (default: data/hotspots.duckdb)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Log every rejected record")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")

    if not args.json_file.is_file():
        parser.error(f"File not found: {args.json_file}")

    print(f"Reading {args.json_file} ...")
    records, layout = load_records(args.json_file)
    print(f"Structure: {layout}, {len(records)} records")
    print("Fields found (records containing each field):")
    for name, count in sorted(describe_fields(records).items()):
        print(f"  - {name}: {count}")

    stats = import_records(records, args.db)
    print_summary(stats, args.db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
