"""Table definition and parameterized SQL queries for the ``hotspots`` table.

Every user-provided value travels to DuckDB as a ``?`` parameter, never as text
pasted into the SQL string. The only strings joined together are fixed SQL
fragments chosen by this module, so SQL injection is impossible.

This module has no Flask code: functions receive a DuckDB cursor/connection and
plain values, which keeps them reusable from the scripts and the tests.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb

from app.geo import BoundingBox
from app.schemas import CalendarQuery, HotspotQuery, confidence_categories_at_least

#: DDL of the ``hotspots`` table. The primary key is the natural identity of a
#: detection (same instrument, satellite, place and instant), which lets the
#: importer skip duplicates with ``ON CONFLICT DO NOTHING``.
HOTSPOTS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS hotspots (
    latitude       DOUBLE    NOT NULL,
    longitude      DOUBLE    NOT NULL,
    acquired_at    TIMESTAMP NOT NULL,
    acq_date       DATE      NOT NULL,
    instrument     VARCHAR   NOT NULL,
    satellite      VARCHAR   NOT NULL,
    source         VARCHAR,
    daynight       VARCHAR,
    bright_mir     DOUBLE,
    bright_tir     DOUBLE,
    frp            DOUBLE,
    pixel_scan     DOUBLE,
    pixel_track    DOUBLE,
    confidence     VARCHAR,
    confidence_raw VARCHAR,
    fire_type      INTEGER,
    version        VARCHAR,
    PRIMARY KEY (instrument, satellite, latitude, longitude, acquired_at)
)
"""

#: Column order used everywhere (DDL, inserts, ``format=json`` output).
HOTSPOT_COLUMNS: tuple[str, ...] = (
    "latitude",
    "longitude",
    "acquired_at",
    "acq_date",
    "instrument",
    "satellite",
    "source",
    "daynight",
    "bright_mir",
    "bright_tir",
    "frp",
    "pixel_scan",
    "pixel_track",
    "confidence",
    "confidence_raw",
    "fire_type",
    "version",
)

_SELECT_COLUMNS = ", ".join(HOTSPOT_COLUMNS)

#: Normalized projection of ``hotspots`` used by the statistics endpoints.
#:
#: It renames columns to the dashboard vocabulary and adds derived fields:
#:
#: * ``sensor`` = ``instrument`` (MODIS/VIIRS), ``timestamp_utc`` = ``acquired_at``,
#:   ``lat``/``lon``, ``type`` = ``fire_type``, ``scan``/``track`` in km.
#: * ``pixel_area_km2 = scan * track``: the ground footprint of the pixel. It
#:   grows towards the edge of the swath, which inflates FRP and brightness.
#: * ``confidence_level`` is recomputed from ``confidence_raw`` so the mapping
#:   lives in SQL too: MODIS numbers ``< 30`` low, ``30..79`` nominal, ``>= 80``
#:   high; VIIRS letters ``l``/``n``/``h``. Anything else falls back to the
#:   stored ``confidence``.
#:
#: The API embeds it as a subquery (it works on any database file, even one
#: imported before this view existed); :func:`create_hotspots_table` also
#: stores it as the view ``hotspots_normalized`` for ad-hoc analysis.
NORMALIZED_HOTSPOTS_SQL = """
SELECT
    instrument                     AS sensor,
    satellite,
    acquired_at                    AS timestamp_utc,
    acq_date,
    latitude                       AS lat,
    longitude                      AS lon,
    bright_mir,
    bright_tir,
    frp,
    CASE
        WHEN instrument = 'MODIS' AND TRY_CAST(confidence_raw AS DOUBLE) IS NOT NULL THEN
            CASE
                WHEN TRY_CAST(confidence_raw AS DOUBLE) < 30 THEN 'low'
                WHEN TRY_CAST(confidence_raw AS DOUBLE) < 80 THEN 'nominal'
                ELSE 'high'
            END
        WHEN lower(confidence_raw) IN ('l', 'low') THEN 'low'
        WHEN lower(confidence_raw) IN ('n', 'nominal') THEN 'nominal'
        WHEN lower(confidence_raw) IN ('h', 'high') THEN 'high'
        ELSE confidence
    END                            AS confidence_level,
    confidence_raw,
    daynight,
    fire_type                      AS "type",
    pixel_scan                     AS scan,
    pixel_track                    AS track,
    pixel_scan * pixel_track       AS pixel_area_km2
FROM hotspots
"""


def create_hotspots_table(connection: duckdb.DuckDBPyConnection) -> None:
    """Create the ``hotspots`` table (if missing), the date index and the normalized view.

    The ``acq_date`` index speeds up the date filter, which is the most
    selective condition in typical queries (a few days out of 25 years).

    Args:
        connection: A writable DuckDB connection.
    """
    connection.execute(HOTSPOTS_TABLE_DDL)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_hotspots_acq_date ON hotspots (acq_date)")
    connection.execute(f"CREATE OR REPLACE VIEW hotspots_normalized AS {NORMALIZED_HOTSPOTS_SQL}")


#: DuckDB type of each column, used to read the staging NDJSON file.
_COLUMN_TYPES: dict[str, str] = {
    "latitude": "DOUBLE",
    "longitude": "DOUBLE",
    "acquired_at": "TIMESTAMP",
    "acq_date": "DATE",
    "instrument": "VARCHAR",
    "satellite": "VARCHAR",
    "source": "VARCHAR",
    "daynight": "VARCHAR",
    "bright_mir": "DOUBLE",
    "bright_tir": "DOUBLE",
    "frp": "DOUBLE",
    "pixel_scan": "DOUBLE",
    "pixel_track": "DOUBLE",
    "confidence": "VARCHAR",
    "confidence_raw": "VARCHAR",
    "fire_type": "INTEGER",
    "version": "VARCHAR",
}


def _staging_value(value: Any) -> Any:
    """Convert a Python value into something ``json.dumps`` and DuckDB agree on.

    Args:
        value: Column value (datetime, date, number, string or None).

    Returns:
        ``"YYYY-MM-DD HH:MM:SS"`` for datetimes, ISO for dates, the value otherwise.
    """
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return value


def count_hotspots(connection: duckdb.DuckDBPyConnection) -> int:
    """Count the rows of the ``hotspots`` table.

    Args:
        connection: DuckDB connection or cursor.

    Returns:
        Number of rows.
    """
    return int(connection.execute("SELECT count(*) FROM hotspots").fetchone()[0])


def bulk_insert_hotspots(
    connection: duckdb.DuckDBPyConnection, records: Iterable[dict[str, Any]]
) -> int:
    """Insert normalized records, silently skipping primary-key duplicates.

    How: the records are written to a temporary newline-delimited JSON file and
    loaded with a single ``INSERT ... SELECT FROM read_json(?) ON CONFLICT DO
    NOTHING``. Why: ``executemany`` in DuckDB inserts row by row and takes
    minutes for hundreds of thousands of rows, while ``read_json`` loads them in
    one vectorized pass (seconds) and needs no extra dependency such as pandas.
    Python floats survive the JSON round trip exactly, so primary-key values do
    not change.

    The number of inserted rows is ``count after - count before``; anything
    else was a duplicate of a row already in the table. Callers should remove
    duplicates *within* ``records`` beforehand.

    Args:
        connection: A writable DuckDB connection with the table already created.
        records: Dicts with the keys of :data:`HOTSPOT_COLUMNS`.

    Returns:
        Number of rows actually inserted.
    """
    columns_struct = ", ".join(f"'{name}': '{kind}'" for name, kind in _COLUMN_TYPES.items())
    before = count_hotspots(connection)
    with tempfile.TemporaryDirectory(prefix="hotspots_import_") as tmp_dir:
        staging = Path(tmp_dir) / "hotspots.ndjson"
        with staging.open("w", encoding="utf-8") as handle:
            for record in records:
                row = {name: _staging_value(record.get(name)) for name in HOTSPOT_COLUMNS}
                handle.write(json.dumps(row) + "\n")
        connection.execute(
            f"INSERT INTO hotspots ({_SELECT_COLUMNS}) "
            f"SELECT {_SELECT_COLUMNS} FROM read_json(?, format = 'newline_delimited', "
            f"columns = {{{columns_struct}}}) "
            "ON CONFLICT DO NOTHING",
            [str(staging)],
        )
    return count_hotspots(connection) - before


def _rows_to_dicts(cursor: duckdb.DuckDBPyConnection, rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Zip result rows with the column names of the last executed query.

    Args:
        cursor: Cursor that executed the query.
        rows: Rows returned by ``fetchall()``.

    Returns:
        One dict per row.
    """
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in rows]


def _filter_conditions(query: HotspotQuery | CalendarQuery) -> tuple[list[str], list[Any]]:
    """Build the WHERE conditions shared by the hotspot list and the calendar.

    Covers the rectangle and the optional filters (confidence, day/night,
    instrument, vegetation); dates are added by the caller because the
    calendar has none. See :func:`build_hotspots_sql` for how each filter
    becomes SQL.

    Args:
        query: Validated hotspot or calendar query.

    Returns:
        ``(conditions, params)``: SQL fragments to join with ``AND`` and their
        ``?`` values in the same order.
    """
    bbox: BoundingBox = query.bbox
    conditions = ["latitude BETWEEN ? AND ?", "longitude BETWEEN ? AND ?"]
    params: list[Any] = [bbox.min_lat, bbox.max_lat, bbox.min_lon, bbox.max_lon]

    if query.confidence_min != "low":
        categories = confidence_categories_at_least(query.confidence_min)
        # Only the number of "?" placeholders depends on input; values are parameters.
        conditions.append(f"confidence IN ({', '.join('?' for _ in categories)})")
        params.extend(categories)
    if query.daynight is not None:
        conditions.append("daynight = ?")
        params.append(query.daynight)
    if query.instrument is not None:
        conditions.append("instrument = ?")
        params.append(query.instrument)
    if query.vegetation_only:
        conditions.append("(fire_type IS NULL OR fire_type NOT IN (1, 2, 3))")
    return conditions, params


def build_hotspots_sql(query: HotspotQuery) -> tuple[str, list[Any]]:
    """Build the SQL text and parameter list for a hotspot search.

    How each filter becomes SQL (all comparisons inclusive):

    * Rectangle: ``latitude BETWEEN min_lat AND max_lat`` and
      ``longitude BETWEEN min_lon AND max_lon``. ``BETWEEN`` includes both ends,
      so points exactly on an edge are returned.
    * Dates: ``acq_date BETWEEN start_date AND end_date``. ``acq_date`` is the
      UTC calendar day of the detection, so this selects every detection from
      ``start_date 00:00:00Z`` up to ``end_date 23:59:59.999Z``.
    * ``confidence_min``: ``confidence IN (...)`` with the categories at or
      above the minimum; ``low`` means no filter at all (so NULL confidences
      are kept too).
    * ``daynight`` / ``instrument``: simple equality when provided.
    * ``vegetation_only``: ``fire_type IS NULL OR fire_type NOT IN (1, 2, 3)``.
      NULL means "type unknown" (most NRT data has no type), not "not
      vegetation", so unknown detections are kept.
    * Order: ``acquired_at`` then the rest of the primary key, so that rows
      with the same timestamp always come in the same order and pagination with
      ``offset`` never skips or repeats rows.
    * Truncation: ``LIMIT limit + 1``. If the database returns more than
      ``limit`` rows, there is at least one more page.

    Args:
        query: Validated query.

    Returns:
        ``(sql, params)`` ready for ``cursor.execute``.
    """
    conditions, params = _filter_conditions(query)
    conditions.append("acq_date BETWEEN ? AND ?")
    params.extend([query.start_date, query.end_date])

    sql = (
        f"SELECT {_SELECT_COLUMNS} FROM hotspots "
        f"WHERE {' AND '.join(conditions)} "
        "ORDER BY acquired_at, instrument, satellite, latitude, longitude "
        "LIMIT ? OFFSET ?"
    )
    params.extend([query.limit + 1, query.offset])
    return sql, params


def find_hotspots(
    cursor: duckdb.DuckDBPyConnection, query: HotspotQuery
) -> tuple[list[dict[str, Any]], bool]:
    """Run a hotspot search and detect whether the result was truncated.

    How: requests ``limit + 1`` rows (see :func:`build_hotspots_sql`). If
    ``limit + 1`` rows come back, there is more data than the page can hold:
    ``truncated`` is True and the extra row is dropped. This costs one extra
    row instead of a separate ``COUNT(*)`` over the whole selection.

    Args:
        cursor: Per-request DuckDB cursor.
        query: Validated query.

    Returns:
        ``(rows, truncated)``: at most ``query.limit`` rows as dicts, and the flag.
    """
    sql, params = build_hotspots_sql(query)
    rows = cursor.execute(sql, params).fetchall()
    truncated = len(rows) > query.limit
    return _rows_to_dicts(cursor, rows[: query.limit]), truncated


def dataset_summary(cursor: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Summarize the whole table for the frontend (date pickers, initial map view).

    Args:
        cursor: Per-request DuckDB cursor.

    Returns:
        A dict with ``total_records``, ``min_date``, ``max_date``,
        ``instruments`` (count per instrument) and ``bbox``
        (``[min_lon, min_lat, max_lon, max_lat]`` or None when empty).
    """
    total, min_date, max_date, min_lon, min_lat, max_lon, max_lat = cursor.execute(
        "SELECT count(*), min(acq_date), max(acq_date), "
        "min(longitude), min(latitude), max(longitude), max(latitude) FROM hotspots"
    ).fetchone()
    instruments = dict(
        cursor.execute(
            "SELECT instrument, count(*) FROM hotspots GROUP BY instrument ORDER BY instrument"
        ).fetchall()
    )
    return {
        "total_records": int(total),
        "min_date": _iso_or_none(min_date),
        "max_date": _iso_or_none(max_date),
        "instruments": {name: int(count) for name, count in instruments.items()},
        "bbox": None if total == 0 else [min_lon, min_lat, max_lon, max_lat],
    }


def calendar_counts(
    cursor: duckdb.DuckDBPyConnection, query: CalendarQuery
) -> list[tuple[int, int, int, int, int]]:
    """Count the hotspots of an area per calendar month, split by instrument.

    How: one ``GROUP BY year, month`` over ``acq_date`` (UTC day), so DuckDB
    returns at most 12 rows per year no matter how many detections exist.
    Why: a 25-year history can hold millions of points, far more than the
    hotspot list can send; the calendar only needs the totals.
    ``count(*) FILTER (WHERE ...)`` gives the MODIS and VIIRS shares in the
    same pass. Months with no detections are absent (the caller fills zeros).

    Args:
        cursor: Per-request DuckDB cursor.
        query: Validated calendar query (rectangle + optional filters).

    Returns:
        ``(year, month, total, modis, viirs)`` tuples ordered by year and month.
    """
    conditions, params = _filter_conditions(query)
    sql = (
        "SELECT year(acq_date) AS y, month(acq_date) AS m, count(*), "
        "count(*) FILTER (WHERE instrument = 'MODIS'), "
        "count(*) FILTER (WHERE instrument = 'VIIRS') "
        f"FROM hotspots WHERE {' AND '.join(conditions)} "
        "GROUP BY y, m ORDER BY y, m"
    )
    return [tuple(int(v) for v in row) for row in cursor.execute(sql, params).fetchall()]


def data_coverage(
    cursor: duckdb.DuckDBPyConnection, instrument: str | None = None
) -> tuple[date, date] | None:
    """Return the first and last ``acq_date`` held in the database.

    Why: the calendar must tell "no fires" (0, the area was observed) from
    "no data" (outside the loaded period). Coverage is the whole table's date
    span, not the area's, because an area with no fires is still covered.
    When the calendar is limited to one instrument, only that instrument's
    span counts.

    Args:
        cursor: Per-request DuckDB cursor.
        instrument: ``"MODIS"``, ``"VIIRS"`` or None for both.

    Returns:
        ``(first_day, last_day)`` or None when there is no matching data.
    """
    if instrument is None:
        row = cursor.execute("SELECT min(acq_date), max(acq_date) FROM hotspots").fetchone()
    else:
        row = cursor.execute(
            "SELECT min(acq_date), max(acq_date) FROM hotspots WHERE instrument = ?", [instrument]
        ).fetchone()
    if row is None or row[0] is None:
        return None
    return row[0], row[1]


def ping(cursor: duckdb.DuckDBPyConnection) -> None:
    """Run a trivial query against ``hotspots`` to prove the database answers.

    Args:
        cursor: Per-request DuckDB cursor.

    Raises:
        duckdb.Error: If the query fails.
    """
    cursor.execute("SELECT 1 FROM hotspots LIMIT 1").fetchall()


def _iso_or_none(value: date | None) -> str | None:
    """Format a date as ``YYYY-MM-DD`` or return None.

    Args:
        value: A date or None.

    Returns:
        The ISO string or None.
    """
    return value.isoformat() if value is not None else None
