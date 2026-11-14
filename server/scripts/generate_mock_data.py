"""Generate a DuckDB database with fake but realistic hotspots over Mexico.

Usage (from ``server/``)::

    python scripts/generate_mock_data.py --db data/mock_hotspots.duckdb --count 200000
    # then point the API at it:
    HOTSPOTS_DB_PATH=data/mock_hotspots.duckdb python run.py

Why: lets the frontend team work with 25 years of plausible data without the
real FIRMS exports. The tests do **not** use this script; they build their own
tiny known dataset in ``tests/conftest.py``.

How the data is made realistic:

* **Where**: points are drawn around fire-prone regions of Mexico (Chiapas,
  Yucatán peninsula, Oaxaca, Guerrero, Michoacán, Jalisco, Sierra Madre
  Occidental, Tamaulipas, Veracruz, ...) with a Gaussian spread, then clipped
  to Mexico's bounding box.
* **When**: MODIS from 2001 to today (Aqua only from mid-2002), VIIRS from 2012
  (SNPP), NOAA-20 from 2018 and NOAA-21 from 2023. Months are weighted so
  April–June (the dry-season peak) has far more activity.
* **Time of day**: each satellite crosses at a fixed *local solar* time
  (e.g. Aqua and VIIRS ~13:30 and ~01:30). The UTC time is
  ``local_solar_hour - longitude / 15`` because the Sun moves 15° of longitude
  per hour; at -100° that is +6.7 h.
* **Values**: brightness temperatures higher during the day, log-normal FRP,
  MODIS numeric confidence, VIIRS ``l``/``n``/``h`` letters, ~3% NULL ``frp`` and
  ~3% NULL ``fire_type``.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import duckdb  # noqa: E402

from app.repository import bulk_insert_hotspots, count_hotspots, create_hotspots_table  # noqa: E402
from scripts.import_json import classify_confidence  # noqa: E402

#: Mexico's approximate bounding box (lat_min, lat_max, lon_min, lon_max).
MEXICO_BOUNDS = (14.5, 32.7, -118.4, -86.7)

#: Fire-prone regions: (name, center latitude, center longitude, spread in degrees, weight).
REGIONS: list[tuple[str, float, float, float, float]] = [
    ("Chiapas", 16.6, -92.8, 0.9, 14),
    ("Yucatan peninsula", 19.6, -89.2, 1.0, 14),
    ("Oaxaca", 16.9, -96.6, 0.9, 12),
    ("Guerrero", 17.6, -99.8, 0.8, 10),
    ("Michoacan", 19.2, -101.8, 0.8, 9),
    ("Jalisco", 20.3, -104.0, 0.9, 8),
    ("Sierra Madre Occidental", 25.5, -106.5, 1.3, 9),
    ("Tamaulipas", 23.8, -98.5, 0.9, 6),
    ("Veracruz", 19.5, -96.6, 0.8, 6),
    ("Tabasco", 17.9, -92.9, 0.6, 5),
    ("Sonora", 29.0, -110.5, 1.2, 3),
    ("Chihuahua", 28.5, -106.8, 1.2, 4),
]

#: Relative fire activity per month (index 0 = January); April–June peak.
MONTH_WEIGHTS = [4, 6, 10, 18, 20, 14, 5, 3, 2, 3, 3, 3]

#: (instrument, satellite, first day, product version, day local hour, night local hour, weight).
SATELLITES: list[tuple[str, str, date, str, float, float, float]] = [
    ("MODIS", "Terra", date(2001, 1, 1), "6.1", 10.5, 22.5, 1.0),
    ("MODIS", "Aqua", date(2002, 7, 4), "6.1", 13.5, 1.5, 1.0),
    ("VIIRS", "SNPP", date(2012, 1, 20), "2", 13.5, 1.5, 2.2),
    ("VIIRS", "NOAA-20", date(2018, 4, 1), "2", 13.5, 1.5, 2.2),
    ("VIIRS", "NOAA-21", date(2023, 3, 1), "2", 13.5, 1.5, 2.2),
]

#: ``fire_type`` distribution: value → weight (None = missing).
FIRE_TYPES: list[tuple[int | None, float]] = [(0, 90), (2, 4), (1, 1), (3, 2), (None, 3)]

#: Data newer than this many days is labelled near-real-time (NRT) instead of standard (SP).
NRT_DAYS = 90


def _random_point(rng: random.Random) -> tuple[float, float]:
    """Draw a coordinate around a weighted fire-prone region.

    Args:
        rng: Random generator.

    Returns:
        ``(latitude, longitude)`` rounded to 5 decimals (like FIRMS) inside Mexico's box.
    """
    _, lat, lon, spread, _ = rng.choices(REGIONS, weights=[r[4] for r in REGIONS])[0]
    lat_min, lat_max, lon_min, lon_max = MEXICO_BOUNDS
    latitude = min(max(rng.gauss(lat, spread), lat_min), lat_max)
    longitude = min(max(rng.gauss(lon, spread), lon_min), lon_max)
    return round(latitude, 5), round(longitude, 5)


def _random_day(rng: random.Random, first: date, last: date) -> date:
    """Draw a day between ``first`` and ``last`` with the seasonal month weights.

    How: choose a year uniformly, then a month with :data:`MONTH_WEIGHTS`, then
    a day of that month uniformly; retry if outside ``[first, last]``.

    Args:
        rng: Random generator.
        first: Earliest allowed day.
        last: Latest allowed day.

    Returns:
        The day.
    """
    while True:
        year = rng.randint(first.year, last.year)
        month = rng.choices(range(1, 13), weights=MONTH_WEIGHTS)[0]
        next_month = date(year + (month == 12), month % 12 + 1, 1)
        day = date(year, month, rng.randint(1, (next_month - timedelta(days=1)).day))
        if first <= day <= last:
            return day


def _utc_time(day: date, local_hour: float, longitude: float, rng: random.Random) -> datetime:
    """Convert a satellite's local solar overpass hour to a UTC timestamp.

    Formula: ``utc_hour = local_hour - longitude / 15`` (15° of longitude per
    hour), plus up to ±45 minutes of jitter for different orbits. The result
    may roll over into the next day, which is realistic: a 22:30 local
    overpass in Mexico happens after midnight UTC.

    Args:
        day: Local calendar day.
        local_hour: Local solar time of the overpass, in hours.
        longitude: Point longitude.
        rng: Random generator.

    Returns:
        Naive UTC timestamp rounded to the minute.
    """
    hours = local_hour - longitude / 15 + rng.uniform(-0.75, 0.75)
    moment = datetime(day.year, day.month, day.day) + timedelta(hours=hours)
    return moment.replace(second=0, microsecond=0)


def make_record(rng: random.Random, today: date) -> dict[str, Any]:
    """Create one normalized fake hotspot.

    Args:
        rng: Random generator.
        today: Last allowed day (UTC).

    Returns:
        A dict with every column of the ``hotspots`` table.
    """
    instrument, satellite, first, version, day_hour, night_hour, _ = rng.choices(
        SATELLITES, weights=[s[6] for s in SATELLITES]
    )[0]
    latitude, longitude = _random_point(rng)
    is_day = rng.random() < 0.72
    acquired_at = _utc_time(_random_day(rng, first, today), day_hour if is_day else night_hour, longitude, rng)
    if acquired_at.date() > today:  # night overpass rolled past "today"
        acquired_at -= timedelta(days=1)

    if instrument == "MODIS":
        raw_confidence = str(int(min(100, max(0, rng.gauss(68, 20)))))
        pixel_scan = round(rng.uniform(1.0, 4.8), 2)
        bright_mir = rng.uniform(305, 380) if is_day else rng.uniform(300, 335)
    else:
        raw_confidence = rng.choices(["l", "n", "h"], weights=[12, 80, 8])[0]
        pixel_scan = round(rng.uniform(0.32, 0.8), 2)
        bright_mir = rng.uniform(300, 367) if is_day else rng.uniform(295, 330)
    confidence, _, _ = classify_confidence(raw_confidence)

    is_nrt = (today - acquired_at.date()).days <= NRT_DAYS
    satellite_tag = {"Terra": "", "Aqua": "", "SNPP": "SNPP_", "NOAA-20": "NOAA20_", "NOAA-21": "NOAA21_"}[satellite]
    source = f"{instrument}_{satellite_tag}{'NRT' if is_nrt else 'SP'}"

    return {
        "latitude": latitude,
        "longitude": longitude,
        "acquired_at": acquired_at,
        "acq_date": acquired_at.date(),
        "instrument": instrument,
        "satellite": satellite,
        "source": source,
        "daynight": "D" if is_day else "N",
        "bright_mir": round(bright_mir, 2),
        "bright_tir": round(rng.uniform(285, 310) if is_day else rng.uniform(275, 295), 2),
        "frp": None if rng.random() < 0.03 else round(math.exp(rng.gauss(2.0, 1.1)), 2),
        "pixel_scan": pixel_scan,
        "pixel_track": round(pixel_scan * rng.uniform(0.75, 1.0), 2),
        "confidence": confidence,
        "confidence_raw": raw_confidence,
        "fire_type": rng.choices([t[0] for t in FIRE_TYPES], weights=[t[1] for t in FIRE_TYPES])[0],
        "version": version,
    }


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point.

    Args:
        argv: Arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description="Generate fake Mexico hotspots into DuckDB.")
    parser.add_argument("--db", type=Path, default=Path("data/mock_hotspots.duckdb"),
                        help="Output DuckDB file (default: data/mock_hotspots.duckdb)")
    parser.add_argument("--count", type=int, default=200_000, help="Number of hotspots (default 200000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible data")
    parser.add_argument("--overwrite", action="store_true", help="Delete the output file first if it exists")
    args = parser.parse_args(argv)

    if args.db.exists():
        if not args.overwrite:
            parser.error(f"{args.db} already exists; use --overwrite to replace it")
        args.db.unlink()

    rng = random.Random(args.seed)
    today = datetime.now(timezone.utc).date()
    records = [make_record(rng, today) for _ in range(args.count)]

    args.db.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(args.db)) as connection:
        create_hotspots_table(connection)
        inserted = bulk_insert_hotspots(connection, records)
        total = count_hotspots(connection)
        per_instrument = connection.execute(
            "SELECT instrument, count(*), min(acq_date), max(acq_date) FROM hotspots GROUP BY 1 ORDER BY 1"
        ).fetchall()

    print(f"Generated {args.count} records, inserted {inserted} (duplicates skipped: {args.count - inserted})")
    print(f"Database: {args.db} ({total} rows)")
    for instrument, count, first, last in per_instrument:
        print(f"  - {instrument}: {count} rows, {first} -> {last}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
