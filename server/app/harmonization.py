"""Harmonized burning activity calendar: one continuous series in MODIS Terra+Aqua units.

Flow of ``GET /api/v1/calendar?harmonized=true``::

    params ── harmonizer.params.load_params (table harmonization_params, cached)
              └─ missing table → fitted in memory once per process
    counts ── harmonizer.data.monthly_counts(bbox)      Terra/Aqua/SNPP × day/night per month
    series ── harmonizer.method.continuous_series         Terra×factor / MODIS / average / VIIRS eq
    grid   ── app.calendar.build_calendar                 zero months, partial months, medians

The math lives in :mod:`harmonizer`; this module only glues it to the API and
adds the reliability block that the client uses for its small-area warning.
"""

from __future__ import annotations

import threading
from datetime import date, timedelta
from typing import Any

import duckdb

from app.calendar import build_calendar
from app.schemas import CalendarQuery
from harmonizer.config import SMALL_AREA_DEG2, HarmonizationConfig
from harmonizer.data import monthly_counts, sensor_coverage
from harmonizer.method import Cutoffs, MonthCounts, continuous_series
from harmonizer.params import HarmonizationParams, fit_params, load_params

_cache: dict[tuple[str, float], HarmonizationParams] = {}
_lock = threading.Lock()


def get_params(
    cursor: duckdb.DuckDBPyConnection, config: HarmonizationConfig, cache_key: tuple[str, float]
) -> HarmonizationParams:
    """Return the harmonization parameters, loading or fitting them only once.

    Args:
        cursor: Request cursor.
        config: Fit periods (used only when the table is missing).
        cache_key: ``(database path, file modification time)``, so a new import
            or a new ``fit`` invalidates the cache after an API restart.

    Returns:
        The parameters.
    """
    with _lock:
        if cache_key not in _cache:
            _cache[cache_key] = load_params(cursor) or fit_params(cursor, config)
        return _cache[cache_key]


def _covers(sensor: tuple[date, date] | None, union: tuple[date, date], month: date) -> bool:
    """Whether a sensor's data covers every loaded day of ``month``.

    Why "every loaded day": near the end of the data the sensors stop on
    different days (e.g. VIIRS NRT on the 2nd, MODIS on the 15th). Averaging
    a 2-day VIIRS count with a 15-day MODIS count would drag the month down,
    so a sensor only takes part when it covers the same days as the other.

    Args:
        sensor: ``(first, last)`` loaded day of the sensor, or None.
        union: ``(first, last)`` loaded day of both sensors together.
        month: First day of the month.

    Returns:
        True when the sensor covers ``[max(month start, union first),
        min(month end, union last)]``.
    """
    if sensor is None:
        return False
    month_end = date(month.year + (month.month == 12), month.month % 12 + 1, 1) - timedelta(days=1)
    return sensor[0] <= max(month, union[0]) and sensor[1] >= min(month_end, union[1])


def _month_starts(first: date, last: date) -> list[date]:
    """Every first-of-month from ``first``'s month to ``last``'s."""
    out, y, m = [], first.year, first.month
    while (y, m) <= (last.year, last.month):
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def build_harmonized_calendar(
    cursor: duckdb.DuckDBPyConnection,
    query: CalendarQuery,
    config: HarmonizationConfig,
    cache_key: tuple[str, float],
) -> dict[str, Any]:
    """Build the harmonized calendar body for the query's rectangle.

    Each month gets ``count`` = harmonized value (one decimal, MODIS Terra+Aqua
    units), ``source`` (``terra_scaled``, ``modis``, ``average``, ``viirs_eq``),
    the raw counts (``modis``, ``viirs``, ``terra``, ``aqua``, ``viirs_day``,
    ``viirs_night``), ``modis_eq`` and ``low_count`` (below the reliable count).

    Args:
        cursor: Request cursor.
        query: Validated calendar query (``harmonized`` is True).
        config: Harmonization settings.
        cache_key: See :func:`get_params`.

    Returns:
        The response body: the usual calendar fields plus ``harmonization``.
    """
    params = get_params(cursor, config, cache_key)
    coverage_by_sensor = sensor_coverage(cursor)
    spans = [c for c in coverage_by_sensor.values() if c is not None]
    coverage = (min(c[0] for c in spans), max(c[1] for c in spans)) if spans else None

    bbox = query.bbox
    points = []
    if coverage is not None:
        rows = monthly_counts(
            cursor, coverage[0], coverage[1],
            bbox=(bbox.min_lat, bbox.max_lat, bbox.min_lon, bbox.max_lon),
            strict_vegetation=False,
        )
        by_month = {r.month: r for r in rows}
        months = [by_month.get(m, MonthCounts(m)) for m in _month_starts(*coverage)]
        cutoffs = Cutoffs(config.aqua_start, config.viirs_start, config.modis_end)
        points = continuous_series(
            months, params.ratios, params.terra_factor, cutoffs,
            availability=lambda m: (_covers(coverage_by_sensor["MODIS"], coverage, m),
                                    _covers(coverage_by_sensor["VIIRS"], coverage, m)),
        )

    body = build_calendar(
        [(p.month.year, p.month.month, round(p.value, 1), p.counts.modis, p.counts.viirs) for p in points],
        coverage,
        bbox,
    )
    threshold = params.min_reliable_count
    for cell, point in zip(body["months"], points):
        c = point.counts
        cell.update({
            "source": point.source,
            "modis_eq": None if point.modis_eq is None else round(point.modis_eq, 1),
            "terra": c.terra, "aqua": c.aqua, "viirs_day": c.viirs_day, "viirs_night": c.viirs_night,
            "low_count": point.value < threshold,
        })
    body["harmonized"] = True
    body["total"] = round(body["total"], 1)
    for year in body["years"]:
        year["count"] = round(year["count"], 1)
    body["monthly_median"] = [None if v is None else round(v, 1) for v in body["monthly_median"]]

    full = [cell["count"] for cell in body["months"] if not cell["partial"]]
    typical = sum(full) / len(full) if full else 0.0
    area = (bbox.max_lat - bbox.min_lat) * (bbox.max_lon - bbox.min_lon)
    body["harmonization"] = {
        "units": "MODIS Terra+Aqua detections per month (vegetation fires)",
        "method": "MODIS_eq = VIIRS_day / r_day + VIIRS_night / r_night",
        **params.as_dict(),
        "cutoffs": {
            "aqua_start": config.aqua_start.isoformat(),
            "viirs_start": config.viirs_start.isoformat(),
            "modis_end": None if config.modis_end is None else config.modis_end.isoformat(),
        },
        "reliability": {
            "area_deg2": round(area, 4),
            "small_area": area < SMALL_AREA_DEG2,
            "small_area_threshold_deg2": SMALL_AREA_DEG2,
            "typical_month": round(typical, 1),
            "low_count": typical < threshold,
            "low_count_months": sum(1 for cell in body["months"] if cell["low_count"]),
        },
    }
    return body
