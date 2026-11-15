"""Bulk-import large FIRMS JSON files (hundreds of MB to GB) into DuckDB, in SQL.

Usage (from ``server/``)::

    python scripts/import_bulk.py ../test/MODIS/*.json ../test/VIIRS_SNPP/*.json \\
        --db data/hotspots.duckdb --replace

Why a second importer: :mod:`scripts.import_json` parses the whole file with
Python's ``json`` module and normalizes record by record. That is easy to read
and test, but a 1.8 GB FIRMS archive becomes ~10 GB of Python objects and does
not fit in memory. This script applies **the same normalization rules** (see
``AGENTS.md`` §6 and ``docs/data-import.md``) as one vectorized DuckDB query per
file: ``read_json`` streams the JSON array, and every rule is a SQL expression.

Rules, as SQL:

* ``acquired_at = acq_date + lpad(acq_time, 4, '0')`` (UTC); invalid → rejected.
* Satellite codes mapped with :data:`scripts.import_json.SATELLITE_CODES`
  (shared dict, so both importers agree); unknown codes kept as-is.
* Confidence: MODIS numbers ``< 30`` low, ``< 80`` nominal, else high; VIIRS
  letters ``l``/``n``/``h``. The original goes to ``confidence_raw``.
* Instrument deduced from the satellite, then from the confidence format;
  the raw ``instrument`` field is a last resort (it says ``"SNPP"`` in VIIRS files).
* ``brightness``/``bright_ti4`` → ``bright_mir``; ``bright_t31``/``bright_ti5`` →
  ``bright_tir``; ``scan``/``track`` → ``pixel_scan``/``pixel_track``;
  ``type`` → ``fire_type`` (missing → NULL, never 0).
* ``source`` = ``<instrument>_<satellite>_NRT`` when the FIRMS ``version`` ends
  in ``NRT`` (near-real-time) and ``..._SP`` (standard processing, the archive)
  otherwise, so archive and NRT rows can be told apart.
* Rows without coordinates, with out-of-range coordinates, or with an invalid
  date/time are rejected (counted, not stored).
* Duplicates of the primary key are dropped inside the file (``DISTINCT ON``)
  and against existing rows (``ON CONFLICT DO NOTHING``).

``--replace`` builds a brand-new database next to the target and swaps it in
at the end, so the old data is only removed once the new import succeeded.
Stop the API first: DuckDB does not let another process write a file it has open.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import duckdb  # noqa: E402

from app.repository import HOTSPOT_COLUMNS, count_hotspots, create_hotspots_table  # noqa: E402
from scripts.import_json import SATELLITE_CODES  # noqa: E402

#: Raw FIRMS fields read from each file (all as text; SQL converts them).
RAW_FIELDS = (
    "latitude", "longitude", "acq_date", "acq_time", "satellite", "instrument",
    "confidence", "version", "bright_ti4", "bright_ti5", "brightness", "bright_t31",
    "scan", "track", "frp", "daynight", "type",
)


def _satellite_case() -> str:
    """Build the fixed ``CASE`` expression that maps satellite codes.

    The keys come from :data:`SATELLITE_CODES` (code constants, never user
    input), so joining them into SQL is safe.

    Returns:
        A SQL expression over the column ``sat_raw``.
    """
    whens = " ".join(
        f"WHEN upper(trim(sat_raw)) = '{code}' THEN '{name}'" for code, name in SATELLITE_CODES.items()
    )
    return f"CASE {whens} ELSE trim(sat_raw) END"


def normalize_sql(path: str) -> str:
    """Return the SELECT that reads one FIRMS JSON file and normalizes it.

    Args:
        path: JSON file; bound later as a parameter is not possible for
            ``read_json`` options, so the caller passes it as ``?``.

    Returns:
        SQL text with one ``?`` placeholder (the file path). The result has the
        columns of :data:`HOTSPOT_COLUMNS` plus ``reject_reason`` (NULL when valid).
    """
    columns = ", ".join(f"{name}: 'VARCHAR'" for name in RAW_FIELDS)
    return f"""
    WITH raw AS (
        SELECT * FROM read_json(?, format = 'array', columns = {{{columns}}},
                                maximum_object_size = 1048576)
    ),
    typed AS (
        SELECT
            TRY_CAST(latitude AS DOUBLE)  AS lat,
            TRY_CAST(longitude AS DOUBLE) AS lon,
            TRY_STRPTIME(trim(acq_date)[1:10] || lpad(replace(trim(acq_time), ':', ''), 4, '0'),
                         '%Y-%m-%d%H%M') AS ts,
            satellite AS sat_raw,
            trim(confidence) AS conf_raw,
            TRY_CAST(trim(confidence) AS DOUBLE) AS conf_num,
            upper(trim(instrument)) AS instrument_raw,
            *
        FROM raw
    ),
    named AS (
        SELECT {_satellite_case()} AS sat, * FROM typed
    ),
    normalized AS (
        SELECT
            lat AS latitude,
            lon AS longitude,
            ts AS acquired_at,
            CAST(ts AS DATE) AS acq_date,
            CASE
                WHEN sat IN ('Terra', 'Aqua') THEN 'MODIS'
                WHEN sat IN ('SNPP', 'NOAA-20', 'NOAA-21') THEN 'VIIRS'
                WHEN conf_num BETWEEN 0 AND 100 THEN 'MODIS'
                WHEN lower(conf_raw) IN ('l', 'n', 'h') THEN 'VIIRS'
                WHEN instrument_raw IN ('MODIS', 'VIIRS') THEN instrument_raw
            END AS instrument,
            sat AS satellite,
            version,
            CASE WHEN upper(trim(daynight)) IN ('D', 'N') THEN upper(trim(daynight)) END AS daynight,
            TRY_CAST(coalesce(nullif(trim(brightness), ''), nullif(trim(bright_ti4), '')) AS DOUBLE)
                AS bright_mir,
            TRY_CAST(coalesce(nullif(trim(bright_t31), ''), nullif(trim(bright_ti5), '')) AS DOUBLE)
                AS bright_tir,
            TRY_CAST(frp AS DOUBLE) AS frp,
            TRY_CAST(scan AS DOUBLE) AS pixel_scan,
            TRY_CAST(track AS DOUBLE) AS pixel_track,
            CASE
                WHEN lower(conf_raw) IN ('l', 'low') THEN 'low'
                WHEN lower(conf_raw) IN ('n', 'nominal') THEN 'nominal'
                WHEN lower(conf_raw) IN ('h', 'high') THEN 'high'
                WHEN conf_num >= 0 AND conf_num < 30 THEN 'low'
                WHEN conf_num >= 30 AND conf_num < 80 THEN 'nominal'
                WHEN conf_num >= 80 AND conf_num <= 100 THEN 'high'
            END AS confidence,
            nullif(conf_raw, '') AS confidence_raw,
            TRY_CAST(TRY_CAST(nullif(trim("type"), '') AS DOUBLE) AS INTEGER) AS fire_type,
            CASE
                WHEN lat IS NULL OR lon IS NULL THEN 'missing_or_invalid_coordinates'
                WHEN lat NOT BETWEEN -90 AND 90 OR lon NOT BETWEEN -180 AND 180
                    THEN 'out_of_range_coordinates'
                WHEN ts IS NULL THEN 'missing_or_invalid_datetime'
                WHEN sat IS NULL OR sat = '' THEN 'missing_satellite'
            END AS reject_reason
        FROM named
    )
    SELECT
        *,
        instrument || '_' || replace(satellite, '-', '') ||
            CASE WHEN upper(coalesce(version, '')) LIKE '%NRT' THEN '_NRT' ELSE '_SP' END AS source
    FROM normalized
    """


def import_file(connection: duckdb.DuckDBPyConnection, path: Path) -> dict[str, int]:
    """Normalize one file into a temp table and insert its valid, unique rows.

    Args:
        connection: Writable connection with the ``hotspots`` table created.
        path: FIRMS JSON file (a JSON array of records).

    Returns:
        Counters: ``read``, ``rejected`` (+ one key per reason), ``inserted``,
        ``duplicates``.
    """
    connection.execute(f"CREATE OR REPLACE TEMP TABLE staging AS {normalize_sql(str(path))}", [str(path)])
    stats: dict[str, int] = {"read": connection.execute("SELECT count(*) FROM staging").fetchone()[0]}
    reasons = connection.execute(
        "SELECT coalesce(reject_reason, CASE WHEN instrument IS NULL THEN 'unknown_instrument' END) r, "
        "count(*) FROM staging GROUP BY r HAVING r IS NOT NULL"
    ).fetchall()
    stats["rejected"] = sum(n for _, n in reasons)
    stats.update({f"rejected:{r}": n for r, n in reasons})

    columns = ", ".join(HOTSPOT_COLUMNS)
    before = count_hotspots(connection)
    connection.execute(
        f"INSERT INTO hotspots ({columns}) "
        f"SELECT DISTINCT ON (instrument, satellite, latitude, longitude, acquired_at) {columns} "
        "FROM staging WHERE reject_reason IS NULL AND instrument IS NOT NULL "
        "ON CONFLICT DO NOTHING"
    )
    stats["inserted"] = count_hotspots(connection) - before
    stats["duplicates"] = stats["read"] - stats["rejected"] - stats["inserted"]
    connection.execute("DROP TABLE staging")
    return stats


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point.

    Args:
        argv: Arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description="Bulk-import FIRMS JSON files into DuckDB (SQL).")
    parser.add_argument("json_files", type=Path, nargs="+", help="FIRMS JSON files (JSON arrays)")
    parser.add_argument("--db", type=Path, default=Path("data/hotspots.duckdb"))
    parser.add_argument("--replace", action="store_true",
                        help="Replace the database contents (built aside, swapped at the end)")
    parser.add_argument("--memory-limit", default="4GB", help="DuckDB memory limit (default 4GB)")
    args = parser.parse_args(argv)

    for path in args.json_files:
        if not path.is_file():
            parser.error(f"File not found: {path}")

    target = args.db
    target.parent.mkdir(parents=True, exist_ok=True)
    work = target.with_name(target.stem + ".importing.duckdb") if args.replace else target
    if args.replace and work.exists():
        work.unlink()

    started = time.monotonic()
    with duckdb.connect(str(work)) as connection:
        connection.execute(f"SET memory_limit = '{args.memory_limit}'")
        connection.execute("SET preserve_insertion_order = false")
        create_hotspots_table(connection)
        for path in args.json_files:
            print(f"Importing {path} ...", flush=True)
            stats = import_file(connection, path)
            for key, value in stats.items():
                print(f"  {key:<40} {value:>10}")
        print("\nRows per instrument/satellite/source:")
        for row in connection.execute(
            "SELECT instrument, satellite, source, count(*), min(acq_date), max(acq_date) "
            "FROM hotspots GROUP BY ALL ORDER BY ALL"
        ).fetchall():
            print("  ", *row)
        connection.execute("CHECKPOINT")

    if args.replace:
        if target.exists():
            target.unlink()
        work.rename(target)
    print(f"\nDone in {time.monotonic() - started:.0f} s -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
