"""DuckDB queries that feed the harmonization math (counts per month, per box).

Every query is one ``GROUP BY`` in DuckDB, so millions of detections become a
few thousand rows before Python sees them. Values travel as ``?`` parameters.

Which detections count:

* Satellites: Terra, Aqua (MODIS) and SNPP (VIIRS). NOAA-20/21 are left out on
  purpose: adding them would inflate VIIRS counts (more overpasses), and a
  per-satellite ratio would be needed first.
* Vegetation fires only. When **fitting** ratios we require ``fire_type = 0``
  (archive data always has the type). When **building an area's series** we
  also keep ``fire_type IS NULL``, because near-real-time (NRT) files carry no
  type; this follows the API's ``vegetation_only`` rule and is documented as a
  limitation (NRT months may include a few industrial/volcano detections).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import duckdb

from harmonizer.method import MonthCounts

#: Fixed SQL fragments for the vegetation filter (chosen by code, never by users).
VEGETATION_STRICT = "fire_type = 0"
VEGETATION_WITH_UNKNOWN = "(fire_type = 0 OR fire_type IS NULL)"

_COUNTS = """
    count(*) FILTER (WHERE satellite = 'Terra' AND daynight = 'D') AS terra_day,
    count(*) FILTER (WHERE satellite = 'Terra' AND daynight = 'N') AS terra_night,
    count(*) FILTER (WHERE satellite = 'Aqua'  AND daynight = 'D') AS aqua_day,
    count(*) FILTER (WHERE satellite = 'Aqua'  AND daynight = 'N') AS aqua_night,
    count(*) FILTER (WHERE satellite = 'SNPP'  AND daynight = 'D') AS viirs_day,
    count(*) FILTER (WHERE satellite = 'SNPP'  AND daynight = 'N') AS viirs_night,
    coalesce(sum(frp) FILTER (WHERE satellite IN ('Terra', 'Aqua')), 0) AS frp_modis,
    coalesce(sum(frp) FILTER (WHERE satellite = 'SNPP'), 0) AS frp_viirs
"""


def _rows(cursor: duckdb.DuckDBPyConnection, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    """Run ``sql`` and return the rows as dicts."""
    result = cursor.execute(sql, params)
    names = [c[0] for c in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def _to_counts(record: dict[str, Any]) -> MonthCounts:
    """Convert one SQL row into :class:`MonthCounts`."""
    box = None
    if record.get("box_lat") is not None:
        box = (int(record["box_lat"]), int(record["box_lon"]))
    return MonthCounts(
        month=record["month"],
        terra_day=int(record["terra_day"]),
        terra_night=int(record["terra_night"]),
        aqua_day=int(record["aqua_day"]),
        aqua_night=int(record["aqua_night"]),
        viirs_day=int(record["viirs_day"]),
        viirs_night=int(record["viirs_night"]),
        box=box,
        frp_modis=float(record["frp_modis"]),
        frp_viirs=float(record["frp_viirs"]),
    )


def monthly_counts(
    cursor: duckdb.DuckDBPyConnection,
    start: date,
    end: date,
    bbox: tuple[float, float, float, float] | None = None,
    by_box: bool = False,
    box_size: float = 1.0,
    strict_vegetation: bool = True,
) -> list[MonthCounts]:
    """Count detections per month (and optionally per square box) in a period.

    How: ``date_trunc('month', acq_date)`` gives the month; ``floor(lat / size)``
    and ``floor(lon / size)`` give the box (a 1° box is about 110 km on a side).
    ``count(*) FILTER`` splits satellites and day/night in one pass.

    Args:
        cursor: DuckDB cursor.
        start: First day (inclusive, UTC).
        end: Last day (inclusive, UTC).
        bbox: Optional ``(min_lat, max_lat, min_lon, max_lon)``, inclusive edges.
        by_box: Group by box as well as month.
        box_size: Box side in degrees (only when ``by_box``).
        strict_vegetation: ``fire_type = 0`` (True) or also NULL (False).

    Returns:
        Rows ordered by month (then box). Months with no detections are absent.
    """
    conditions = ["acq_date BETWEEN ? AND ?", "satellite IN ('Terra', 'Aqua', 'SNPP')",
                  VEGETATION_STRICT if strict_vegetation else VEGETATION_WITH_UNKNOWN]
    params: list[Any] = [start, end]
    if bbox is not None:
        conditions += ["latitude BETWEEN ? AND ?", "longitude BETWEEN ? AND ?"]
        params += list(bbox)
    box_cols = ""
    if by_box:
        box_cols = "CAST(floor(latitude / ?) AS INTEGER) AS box_lat, CAST(floor(longitude / ?) AS INTEGER) AS box_lon,"
        params = [box_size, box_size, *params]
    sql = (
        f"SELECT CAST(date_trunc('month', acq_date) AS DATE) AS month, {box_cols} {_COUNTS} "
        f"FROM hotspots WHERE {' AND '.join(conditions)} GROUP BY ALL ORDER BY ALL"
    )
    return [_to_counts(r) for r in _rows(cursor, sql, params)]


def sensor_coverage(cursor: duckdb.DuckDBPyConnection) -> dict[str, tuple[date, date] | None]:
    """First and last loaded day of MODIS (Terra+Aqua) and VIIRS (SNPP).

    Args:
        cursor: DuckDB cursor.

    Returns:
        ``{"MODIS": (first, last) | None, "VIIRS": (first, last) | None}``.
    """
    coverage: dict[str, tuple[date, date] | None] = {"MODIS": None, "VIIRS": None}
    for name, first, last in cursor.execute(
        "SELECT CASE WHEN satellite = 'SNPP' THEN 'VIIRS' ELSE 'MODIS' END AS s, "
        "min(acq_date), max(acq_date) FROM hotspots "
        "WHERE satellite IN ('Terra', 'Aqua', 'SNPP') GROUP BY s"
    ).fetchall():
        coverage[name] = (first, last)
    return coverage
