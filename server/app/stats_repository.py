"""Aggregation queries behind the dashboard statistics endpoints.

Every function receives a DuckDB cursor and a validated
:class:`app.stats_schemas.StatsQuery` and runs **all** the aggregation in
DuckDB; Python only reshapes the (small) results.

Each query starts from the same common table expression::

    WITH f AS (SELECT * FROM (<NORMALIZED_HOTSPOTS_SQL>) WHERE <area + filters>)

so the rectangle, date and filter rules are written once
(:func:`build_filtered_cte`). User values always travel as ``?`` parameters;
the only text joined into SQL comes from fixed dictionaries in this module,
looked up with keys that Pydantic already restricted to known values.

Detections from MODIS and VIIRS are never added together: every count or sum
is grouped by ``sensor``, because the two instruments have very different
pixel sizes and sensitivities (a VIIRS count is not comparable to a MODIS count).
"""

from __future__ import annotations

import math
from typing import Any

import duckdb

from app.repository import NORMALIZED_HOTSPOTS_SQL
from app.schemas import confidence_categories_at_least
from app.stats_schemas import StatsQuery

#: ``date_trunc`` part for each ``freq`` value of ``/stats/timeseries``.
_TRUNC_PARTS: dict[str, str] = {"day": "day", "week": "week", "month": "month"}

#: SQL expression for each ``field`` of ``/stats/distribution``. ``confidence_raw``
#: is numeric only for MODIS (VIIRS uses the letters l/n/h).
_DISTRIBUTION_FIELDS: dict[str, str] = {
    "frp": "frp",
    "bright_mir": "bright_mir",
    "bright_tir": "bright_tir",
    "confidence_raw": "CASE WHEN sensor = 'MODIS' THEN TRY_CAST(confidence_raw AS DOUBLE) END",
}

#: Columns allowed on the scatter axes.
_SCATTER_COLUMNS: dict[str, str] = {
    "bright_mir": "bright_mir",
    "pixel_area_km2": "pixel_area_km2",
    "bright_tir": "bright_tir",
    "frp": "frp",
}

#: Columns allowed by ``/stats/by-category``.
_CATEGORY_COLUMNS: dict[str, str] = {
    "daynight": "daynight",
    "satellite": "satellite",
    "type": '"type"',
    "confidence_level": "confidence_level",
}


def build_filtered_cte(query: StatsQuery) -> tuple[str, list[Any]]:
    """Build the ``WITH f AS (...)`` prefix that applies the area and filters.

    Rules (same as ``/api/v1/hotspots``, all comparisons inclusive):

    * Rectangle: ``lat BETWEEN min_lat AND max_lat`` and the same for ``lon``.
    * Dates: ``acq_date BETWEEN start_date AND end_date`` (UTC calendar days).
    * ``confidence_min``: ``confidence_level IN (...)`` for the categories at or
      above the minimum; ``low`` applies no filter.
    * ``daynight`` / ``instrument`` (as ``sensor``) / ``satellite``: equality.
    * ``fire_type``: ``0`` keeps type 0 **and** unknown (NULL); ``1``..``3`` are
      exact; ``None`` (``all``) applies no filter.

    Args:
        query: Validated stats query.

    Returns:
        ``(cte_sql, params)``; append a ``SELECT ... FROM f`` to the SQL.
    """
    bbox = query.bbox
    conditions = ["lat BETWEEN ? AND ?", "lon BETWEEN ? AND ?", "acq_date BETWEEN ? AND ?"]
    params: list[Any] = [
        bbox.min_lat,
        bbox.max_lat,
        bbox.min_lon,
        bbox.max_lon,
        query.start_date,
        query.end_date,
    ]
    if query.confidence_min != "low":
        categories = confidence_categories_at_least(query.confidence_min)
        conditions.append(f"confidence_level IN ({', '.join('?' for _ in categories)})")
        params.extend(categories)
    for column, value in (
        ("daynight", query.daynight),
        ("sensor", query.instrument),
        ("satellite", query.satellite),
    ):
        if value is not None:
            conditions.append(f"{column} = ?")
            params.append(value)
    if query.fire_type == 0:
        conditions.append('("type" IS NULL OR "type" = 0)')
    elif query.fire_type is not None:
        conditions.append('"type" = ?')
        params.append(query.fire_type)
    cte = f"WITH f AS (SELECT * FROM ({NORMALIZED_HOTSPOTS_SQL}) AS h WHERE {' AND '.join(conditions)}) "
    return cte, params


def _fetch(
    cursor: duckdb.DuckDBPyConnection, query: StatsQuery, select_sql: str, extra: list[Any] | None = None
) -> list[dict[str, Any]]:
    """Run ``WITH f AS (...) <select_sql>`` and return the rows as dicts.

    Args:
        cursor: Per-request DuckDB cursor.
        query: Validated stats query (builds the CTE).
        select_sql: The ``SELECT ... FROM f ...`` part.
        extra: Parameters for the ``?`` placeholders of ``select_sql``.

    Returns:
        One dict per row, keyed by column name.
    """
    cte, params = build_filtered_cte(query)
    result = cursor.execute(cte + select_sql, params + (extra or []))
    names = [column[0] for column in result.description]
    return [dict(zip(names, row)) for row in result.fetchall()]


def summary(cursor: duckdb.DuckDBPyConnection, query: StatsQuery) -> list[dict[str, Any]]:
    """KPIs per sensor: detection count, mean/max FRP and mean brightness temperatures.

    Returns:
        One row per sensor with data: ``sensor``, ``total_detections``,
        ``frp_mean``, ``frp_max`` (MW), ``bright_mir_mean``, ``bright_tir_mean`` (K).
    """
    return _fetch(
        cursor,
        query,
        "SELECT sensor, count(*) AS total_detections, avg(frp) AS frp_mean, max(frp) AS frp_max, "
        "avg(bright_mir) AS bright_mir_mean, avg(bright_tir) AS bright_tir_mean "
        "FROM f GROUP BY sensor ORDER BY sensor",
    )


def timeseries(cursor: duckdb.DuckDBPyConnection, query: StatsQuery, freq: str) -> list[dict[str, Any]]:
    """Detections and FRP per period and sensor.

    How: ``date_trunc(freq, acq_date)`` gives the first day of each period
    (weeks start on Monday, ISO 8601). Periods without detections are absent.

    Returns:
        Rows with ``period`` (date), ``sensor``, ``detections``, ``frp_total``,
        ``frp_mean`` (MW) and ``bright_mir_mean`` (K), ordered by period.
    """
    part = _TRUNC_PARTS[freq]
    return _fetch(
        cursor,
        query,
        f"SELECT CAST(date_trunc('{part}', acq_date) AS DATE) AS period, sensor, "
        "count(*) AS detections, sum(frp) AS frp_total, avg(frp) AS frp_mean, "
        "avg(bright_mir) AS bright_mir_mean "
        "FROM f GROUP BY period, sensor ORDER BY period, sensor",
    )


def distribution(
    cursor: duckdb.DuckDBPyConnection, query: StatsQuery, field: str, bins: int, log: bool
) -> tuple[list[dict[str, Any]], int]:
    """Histogram of one field with equal-width bins shared by both sensors.

    How: a first query finds ``min``/``max`` of the valid values (non-NULL, and
    ``> 0`` when ``log``). Bin edges are spread evenly between them (in
    ``log10`` space when ``log``) so MODIS and VIIRS share the same edges. A
    second query assigns ``bin = floor((value - lo) / width)``, clamped to
    ``bins - 1`` so the maximum lands in the last bin, and counts per sensor.
    Empty bins are filled with 0. ``confidence_raw`` always uses 0..100.
    If every value is equal the range is widened by 1 so the width is not 0.

    Returns:
        ``(rows, excluded)``: rows with ``bin_start``, ``bin_end``, ``sensor``,
        ``count``; ``excluded`` = detections left out (NULL value, or <= 0 with log).
    """
    expr = _DISTRIBUTION_FIELDS[field]
    valid = f"({expr}) IS NOT NULL" + (f" AND ({expr}) > 0" if log else "")
    if field == "confidence_raw":
        # Only MODIS has numeric confidence: VIIRS rows are not "excluded" values.
        population = "WHERE sensor = 'MODIS'"
    else:
        population = ""
    bounds = _fetch(
        cursor,
        query,
        f"SELECT count(*) AS total, count(*) FILTER (WHERE {valid}) AS n, "
        f"min({expr}) FILTER (WHERE {valid}) AS lo, max({expr}) FILTER (WHERE {valid}) AS hi "
        f"FROM f {population}",
    )[0]
    if not bounds["n"]:
        return [], int(bounds["total"])
    lo, hi = (0.0, 100.0) if field == "confidence_raw" and not log else (bounds["lo"], bounds["hi"])
    if log:
        lo, hi = math.log10(lo), math.log10(hi)
    if hi <= lo:
        hi = lo + 1.0
    width = (hi - lo) / bins
    value = f"log10({expr})" if log else expr
    counts = _fetch(
        cursor,
        query,
        f"SELECT sensor, CAST(least(greatest(floor(({value} - ?) / ?), 0), ?) AS INTEGER) AS bin, "
        f"count(*) AS count FROM f WHERE {valid} GROUP BY sensor, bin",
        [lo, width, bins - 1],
    )
    by_key = {(row["sensor"], row["bin"]): row["count"] for row in counts}
    sensors = sorted({row["sensor"] for row in counts})
    rows = []
    for index in range(bins):
        start, end = lo + index * width, lo + (index + 1) * width
        if log:
            start, end = 10**start, 10**end
        for sensor in sensors:
            rows.append(
                {"bin_start": start, "bin_end": end, "sensor": sensor, "count": by_key.get((sensor, index), 0)}
            )
    return rows, int(bounds["total"]) - int(bounds["n"])


def scatter(
    cursor: duckdb.DuckDBPyConnection, query: StatsQuery, x: str, y: str, limit: int
) -> tuple[list[dict[str, Any]], int]:
    """Deterministic pseudo-random sample of ``(x, y)`` pairs.

    How: rows with both values present are ordered by ``hash()`` of their
    identity (time, place, satellite) and the first ``limit`` are kept. A hash
    looks random but is stable, so the same request always draws the same
    sample (charts do not "jump" when the user reloads).

    Returns:
        ``(rows, available)``: rows with ``x``, ``y``, ``sensor``,
        ``confidence_level``; ``available`` = rows that could be sampled.
    """
    x_col, y_col = _SCATTER_COLUMNS[x], _SCATTER_COLUMNS[y]
    present = f"{x_col} IS NOT NULL AND {y_col} IS NOT NULL"
    available = _fetch(cursor, query, f"SELECT count(*) AS n FROM f WHERE {present}")[0]["n"]
    rows = _fetch(
        cursor,
        query,
        f"SELECT {x_col} AS x, {y_col} AS y, sensor, confidence_level FROM f WHERE {present} "
        "ORDER BY hash(timestamp_utc, lat, lon, satellite), timestamp_utc, lat, lon LIMIT ?",
        [limit],
    )
    return rows, int(available)


def calendar(
    cursor: duckdb.DuckDBPyConnection, query: StatsQuery, metric: str, granularity: str
) -> list[dict[str, Any]]:
    """Value per year and day of year (or ISO week) and sensor, for a calendar heat map.

    ``metric=detections`` counts detections; ``metric=frp`` sums FRP (MW).
    With ``granularity=week``, ``year``/``week`` are the ISO year and week
    (weeks start on Monday) and ``date`` is that Monday.

    Returns:
        Rows with ``year``, ``day_of_year`` or ``week``, ``date``, ``sensor``, ``value``.
    """
    value = "count(*)" if metric == "detections" else "sum(frp)"
    if granularity == "day":
        keys = "year(acq_date) AS year, dayofyear(acq_date) AS day_of_year, acq_date AS date"
        group = "year, day_of_year, date"
    else:
        keys = (
            "isoyear(acq_date) AS year, week(acq_date) AS week, "
            "CAST(date_trunc('week', acq_date) AS DATE) AS date"
        )
        group = "year, week, date"
    return _fetch(
        cursor,
        query,
        f"SELECT {keys}, sensor, {value} AS value FROM f GROUP BY {group}, sensor ORDER BY date, sensor",
    )


def by_hour(cursor: duckdb.DuckDBPyConnection, query: StatsQuery) -> list[dict[str, Any]]:
    """Detections per UTC hour of acquisition, sensor and satellite.

    Returns:
        Rows with ``hour_utc`` (0..23), ``sensor``, ``satellite``, ``detections``.
        Hours without detections are absent.
    """
    return _fetch(
        cursor,
        query,
        "SELECT hour(timestamp_utc) AS hour_utc, sensor, satellite, count(*) AS detections "
        "FROM f GROUP BY hour_utc, sensor, satellite ORDER BY hour_utc, sensor, satellite",
    )


def by_category(cursor: duckdb.DuckDBPyConnection, query: StatsQuery, field: str) -> list[dict[str, Any]]:
    """Detections and mean FRP per category of one column and sensor.

    Returns:
        Rows with ``category`` (NULL = unknown), ``sensor``, ``detections``, ``frp_mean``.
    """
    column = _CATEGORY_COLUMNS[field]
    return _fetch(
        cursor,
        query,
        f"SELECT {column} AS category, sensor, count(*) AS detections, avg(frp) AS frp_mean "
        "FROM f GROUP BY category, sensor ORDER BY sensor, category NULLS LAST",
    )


def by_scan(cursor: duckdb.DuckDBPyConnection, query: StatsQuery, bins: int) -> list[dict[str, Any]]:
    """FRP percentiles per scan-size range, to show the view-angle effect.

    How: for each sensor separately (MODIS scan is 1..4.8 km, VIIRS 0.32..0.8 km,
    so shared ranges would put all VIIRS in one bin) the ``[min, max]`` scan
    range is split into ``bins`` equal parts;
    ``bin = least(floor((scan - lo) / width), bins - 1)``. Per range it returns
    the 5th percentile and the median of FRP (``quantile_cont``, linear
    interpolation). Ranges without detections are absent.

    Returns:
        Rows with ``sensor``, ``scan_start``, ``scan_end`` (km), ``detections``,
        ``frp_p5``, ``frp_median`` (MW).
    """
    return _fetch(
        cursor,
        query,
        "SELECT sensor, lo + bin * w AS scan_start, lo + (bin + 1) * w AS scan_end, "
        "count(*) AS detections, quantile_cont(frp, 0.05) AS frp_p5, quantile_cont(frp, 0.5) AS frp_median "
        "FROM ("
        "  SELECT f.sensor, f.frp, b.lo, b.w, "
        "         CAST(least(floor((f.scan - b.lo) / b.w), ?) AS INTEGER) AS bin "
        "  FROM f JOIN ("
        "    SELECT sensor, min(scan) AS lo, "
        "           CASE WHEN max(scan) > min(scan) THEN (max(scan) - min(scan)) / ? ELSE 1.0 END AS w "
        "    FROM f WHERE scan IS NOT NULL GROUP BY sensor"
        "  ) AS b USING (sensor) WHERE f.scan IS NOT NULL"
        ") GROUP BY sensor, bin, lo, w ORDER BY sensor, bin",
        [bins - 1, bins],
    )


def top_events(cursor: duckdb.DuckDBPyConnection, query: StatsQuery, n: int) -> list[dict[str, Any]]:
    """The ``n`` detections with the highest FRP (ties broken by time and place).

    Returns:
        Rows with ``timestamp_utc``, ``lat``, ``lon``, ``frp``, ``bright_mir``,
        ``bright_tir``, ``sensor``, ``satellite``.
    """
    return _fetch(
        cursor,
        query,
        "SELECT timestamp_utc, lat, lon, frp, bright_mir, bright_tir, sensor, satellite FROM f "
        "WHERE frp IS NOT NULL ORDER BY frp DESC, timestamp_utc, sensor, satellite, lat, lon LIMIT ?",
        [n],
    )


def points(cursor: duckdb.DuckDBPyConnection, query: StatsQuery, limit: int) -> tuple[list[dict[str, Any]], bool]:
    """Light-weight points for a map, strongest FRP first.

    How: ``limit + 1`` rows are requested (same truncation trick as
    ``/api/v1/hotspots``); ordering by FRP descending means that, when the
    area holds more points than ``limit``, the most intense ones are kept.

    Returns:
        ``(rows, truncated)``: rows with ``lat``, ``lon``, ``frp``, ``sensor``.
    """
    rows = _fetch(
        cursor,
        query,
        "SELECT lat, lon, frp, sensor FROM f "
        "ORDER BY frp DESC NULLS LAST, timestamp_utc, sensor, satellite, lat, lon LIMIT ?",
        [limit + 1],
    )
    return rows[:limit], len(rows) > limit


def grid(cursor: duckdb.DuckDBPyConnection, query: StatsQuery, cell: float) -> list[dict[str, Any]]:
    """Detections and total FRP per square grid cell and sensor (heat map).

    How: the cell of a point is ``(floor(lat / cell), floor(lon / cell))``;
    its center is ``(index + 0.5) * cell``. The grid is anchored at 0°, so the
    same cell always has the same center whatever rectangle is requested.

    Returns:
        Rows with ``lat``, ``lon`` (cell center), ``sensor``, ``detections``, ``frp_total``.
    """
    return _fetch(
        cursor,
        query,
        "SELECT round((ilat + 0.5) * ?, 6) AS lat, round((ilon + 0.5) * ?, 6) AS lon, sensor, "
        "count(*) AS detections, sum(frp) AS frp_total "
        "FROM (SELECT floor(lat / ?) AS ilat, floor(lon / ?) AS ilon, sensor, frp FROM f) "
        "GROUP BY ilat, ilon, sensor ORDER BY lat, lon, sensor",
        [cell, cell, cell, cell],
    )


def sensor_comparison(
    cursor: duckdb.DuckDBPyConnection, query: StatsQuery
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Daily detections and FRP per sensor, plus the VIIRS/MODIS ratio.

    How: one ``GROUP BY acq_date, sensor`` query; the ratio is computed only on
    days where **both** sensors have at least one detection
    (``viirs / modis``). ``frp_ratio`` is NULL when the MODIS FRP total is 0 or
    unknown. With MODIS-only data the ratio list is empty.

    Returns:
        ``(daily, ratio)``: daily rows ``date``, ``sensor``, ``detections``,
        ``frp_total``; ratio rows ``date``, ``modis_detections``,
        ``viirs_detections``, ``detections_ratio``, ``frp_ratio``.
    """
    daily = _fetch(
        cursor,
        query,
        "SELECT acq_date AS date, sensor, count(*) AS detections, sum(frp) AS frp_total "
        "FROM f GROUP BY date, sensor ORDER BY date, sensor",
    )
    per_day: dict[Any, dict[str, dict[str, Any]]] = {}
    for row in daily:
        per_day.setdefault(row["date"], {})[row["sensor"]] = row
    ratio = []
    for day, sensors in per_day.items():
        modis, viirs = sensors.get("MODIS"), sensors.get("VIIRS")
        if modis is None or viirs is None:
            continue
        frp_ratio = None
        if modis["frp_total"] and viirs["frp_total"] is not None:
            frp_ratio = viirs["frp_total"] / modis["frp_total"]
        ratio.append(
            {
                "date": day,
                "modis_detections": modis["detections"],
                "viirs_detections": viirs["detections"],
                "detections_ratio": viirs["detections"] / modis["detections"],
                "frp_ratio": frp_ratio,
            }
        )
    return daily, ratio


def monthly(cursor: duckdb.DuckDBPyConnection, query: StatsQuery) -> list[dict[str, Any]]:
    """Seasonal profile: detections per calendar month (1..12) and sensor, all years together.

    ``years_with_data`` tells how many distinct years contributed to each
    month, so a client can show an average per year
    (``detections / years_with_data``). For a month-by-month timeline use
    ``/stats/timeseries?freq=month`` instead.

    Returns:
        Rows with ``month`` (1..12), ``sensor``, ``detections``, ``years_with_data``.
    """
    return _fetch(
        cursor,
        query,
        "SELECT month(acq_date) AS month, sensor, count(*) AS detections, "
        "count(DISTINCT year(acq_date)) AS years_with_data "
        "FROM f GROUP BY month, sensor ORDER BY month, sensor",
    )
