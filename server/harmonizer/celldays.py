"""Cell-day harmonization: MODIS extrapolated to VIIRS SNPP on a 5 km grid.

Metric
------
A **cell-day** is one 5 km × 5 km grid cell with at least one detection on one
UTC day. Ten detections in the same cell on the same day count once. It is an
indirect measure of how much of the area burns each day, and it is far less
sensitive to pixel size than raw detection counts.

How the series is built (one value per UTC day)::

    VIIRS SNPP has data that day?   yes → SNPP cell-days                  (source "SNPP")
                                    no  → Aqua cell-days  × 18376 / 2391   (source "Aqua")
                                          or, without Aqua,
                                          Terra cell-days × 18376 / 1944   (source "Terra")

"Has data that day" means the satellite has **at least one detection anywhere
in the database** on that day, not only inside the rectangle: a quiet day in a
small area is a real zero, while a day with no SNPP detection in the whole
country is a gap in the VIIRS record (before 2012-01-20, or an outage). Aqua is
preferred over Terra because it crosses at ~13:30 local time, like SNPP.

The factors come from the Durango pilot calibration (SNPP cell-days divided by
the MODIS satellite's cell-days over the same days, rectangle
:data:`PILOT_BOUNDS`, 5 km grid). They are applied to any rectangle, but the
API flags every area that is not the pilot one (:func:`is_pilot_area`).

Grid (same as the original pilot function): anchored at the rectangle's
south-west corner, ``dy = cell_km / 111.32`` degrees and
``dx = dy / cos(mean latitude)``, so cells are ~5 km wide at the middle of the
rectangle. Points on the east or north edge go to the last column or row.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

import duckdb

#: Durango pilot rectangle ``(west, east, south, north)`` in degrees.
PILOT_BOUNDS: tuple[float, float, float, float] = (-107.210278, -102.472778, 22.345000, 26.845000)

#: Cell size of the calibration grid, in km.
CELL_KM = 5.0

#: Kilometres per degree of latitude used by the grid.
KM_PER_DEGREE = 111.32

#: Proportional factors to VIIRS SNPP-equivalent cell-days (Durango pilot calibration).
FACTORS: dict[str, float] = {
    "Aqua": 18376 / 2391,
    "Terra": 18376 / 1944,
    "SNPP": 1.0,
}

#: Satellites in order of preference for a day: VIIRS first, then the MODIS fallbacks.
PRIORITY: tuple[str, ...] = ("SNPP", "Aqua", "Terra")

#: How far (degrees) each edge may be from :data:`PILOT_BOUNDS` and still be "the pilot area".
PILOT_TOLERANCE_DEG = 0.01

#: Unit of every value of the series.
UNITS = "VIIRS SNPP-equivalent cell-days (5 km cells with at least one detection per UTC day)"

#: Shown with every cell-day chart.
DISCLAIMER = (
    "Cell-days are an indirect metric of the average fire activity level in the region. They count "
    "how many 5 km × 5 km cells had at least one satellite fire detection on each UTC day; they are "
    "not a count of fires, burned area or fire intensity. Periods without VIIRS SNPP data are "
    "extrapolated from MODIS (Aqua, or Terra when Aqua is missing) with fixed proportional factors "
    "calibrated for the Durango pilot area, so they are estimates."
)

#: Shown when the rectangle is not the pilot area.
OUTSIDE_PILOT_WARNING = (
    "The MODIS-to-VIIRS factors were calibrated only for the Durango pilot area "
    "(22.345°N–26.845°N, 107.210°W–102.473°W). For this area the extrapolated values are "
    "indicative only."
)

Freq = Literal["day", "week", "month", "year"]
Source = Literal["SNPP", "Aqua", "Terra"]


@dataclass(frozen=True)
class Grid:
    """Regular grid over a rectangle, anchored at its south-west corner.

    Attributes:
        west: Western edge (degrees).
        south: Southern edge (degrees).
        dx: Cell width in degrees of longitude.
        dy: Cell height in degrees of latitude.
        nx: Number of columns.
        ny: Number of rows.
    """

    west: float
    south: float
    dx: float
    dy: float
    nx: int
    ny: int


def build_grid(west: float, east: float, south: float, north: float, cell_km: float = CELL_KM) -> Grid:
    """Build the cell-day grid exactly like the pilot function.

    Args:
        west: Western edge (degrees).
        east: Eastern edge (degrees).
        south: Southern edge (degrees).
        north: Northern edge (degrees).
        cell_km: Cell size in km.

    Returns:
        The grid. A degenerate rectangle (zero width or height) gets one
        column or row, so every point still has a cell.
    """
    dy = cell_km / KM_PER_DEGREE
    dx = dy / math.cos(math.radians((south + north) / 2))
    nx = max(1, math.ceil((east - west) / dx))
    ny = max(1, math.ceil((north - south) / dy))
    return Grid(west=west, south=south, dx=dx, dy=dy, nx=nx, ny=ny)


def is_pilot_area(west: float, east: float, south: float, north: float) -> bool:
    """Whether a rectangle is the Durango pilot one (each edge within :data:`PILOT_TOLERANCE_DEG`)."""
    return all(abs(a - b) <= PILOT_TOLERANCE_DEG for a, b in zip((west, east, south, north), PILOT_BOUNDS))


# --- Database -------------------------------------------------------------------------

_SATELLITES_SQL = "satellite IN ('SNPP', 'Aqua', 'Terra')"


def cell_day_counts(
    cursor: duckdb.DuckDBPyConnection,
    bounds: tuple[float, float, float, float],
    start: date,
    end: date,
    cell_km: float = CELL_KM,
) -> dict[date, dict[str, tuple[int, int]]]:
    """Count occupied cells per UTC day and satellite inside a rectangle.

    How: each detection gets ``(floor((lon - west) / dx), floor((lat - south) / dy))``
    clipped to the grid; the inner query keeps one row per day, satellite and
    cell; the outer one counts those rows. Every detection is used (no
    confidence or type filter), as in the pilot calibration.

    Args:
        cursor: DuckDB cursor.
        bounds: ``(west, east, south, north)``, inclusive.
        start: First UTC day, inclusive.
        end: Last UTC day, inclusive.
        cell_km: Cell size in km.

    Returns:
        ``{day: {satellite: (cell_days, detections)}}`` for days with detections.
    """
    west, east, south, north = bounds
    grid = build_grid(west, east, south, north, cell_km)
    sql = (
        "SELECT acq_date, satellite, count(*) AS cell_days, sum(n) AS detections FROM ("
        "  SELECT acq_date, satellite,"
        "    least(greatest(CAST(floor((longitude - ?) / ?) AS BIGINT), 0), ?) AS gx,"
        "    least(greatest(CAST(floor((latitude - ?) / ?) AS BIGINT), 0), ?) AS gy,"
        "    count(*) AS n"
        f"  FROM hotspots WHERE {_SATELLITES_SQL} AND acq_date BETWEEN ? AND ?"
        "    AND longitude BETWEEN ? AND ? AND latitude BETWEEN ? AND ?"
        "  GROUP BY acq_date, satellite, gx, gy"
        ") GROUP BY acq_date, satellite"
    )
    params = [
        grid.west, grid.dx, grid.nx - 1,
        grid.south, grid.dy, grid.ny - 1,
        start, end, west, east, south, north,
    ]
    counts: dict[date, dict[str, tuple[int, int]]] = {}
    for day, satellite, cells, detections in cursor.execute(sql, params).fetchall():
        counts.setdefault(day, {})[satellite] = (int(cells), int(detections))
    return counts


def available_days(cursor: duckdb.DuckDBPyConnection, start: date, end: date) -> dict[str, set[date]]:
    """Days on which each satellite has at least one detection anywhere in the database.

    Args:
        cursor: DuckDB cursor.
        start: First UTC day, inclusive.
        end: Last UTC day, inclusive.

    Returns:
        ``{"SNPP": {...}, "Aqua": {...}, "Terra": {...}}``.
    """
    days: dict[str, set[date]] = {name: set() for name in PRIORITY}
    for satellite, day in cursor.execute(
        f"SELECT DISTINCT satellite, acq_date FROM hotspots WHERE {_SATELLITES_SQL} AND acq_date BETWEEN ? AND ?",
        [start, end],
    ).fetchall():
        days[satellite].add(day)
    return days


# --- Daily series ---------------------------------------------------------------------


@dataclass(frozen=True)
class DayValue:
    """Harmonized value of one UTC day.

    Attributes:
        day: The day.
        source: Satellite the value comes from, or None when no satellite has data.
        cell_days: Observed cell-days of ``source`` in the rectangle (0 when none).
        detections: Detections of ``source`` in the rectangle.
        value: ``cell_days × FACTORS[source]``, or None without a source.
    """

    day: date
    source: Source | None
    cell_days: int
    detections: int
    value: float | None


def daily_series(
    counts: dict[date, dict[str, tuple[int, int]]],
    available: dict[str, set[date]],
    start: date,
    end: date,
) -> list[DayValue]:
    """One value per day from ``start`` to ``end``, choosing the satellite by :data:`PRIORITY`.

    Args:
        counts: Output of :func:`cell_day_counts`.
        available: Output of :func:`available_days`.
        start: First day, inclusive.
        end: Last day, inclusive.

    Returns:
        Every day of the range, in order.
    """
    series = []
    day = start
    while day <= end:
        source = next((s for s in PRIORITY if day in available.get(s, ())), None)
        if source is None:
            series.append(DayValue(day, None, 0, 0, None))
        else:
            cells, detections = counts.get(day, {}).get(source, (0, 0))
            series.append(DayValue(day, source, cells, detections, cells * FACTORS[source]))
        day += timedelta(days=1)
    return series


# --- Aggregation ----------------------------------------------------------------------


def _month_end(day: date) -> date:
    """Last day of ``day``'s month."""
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1) - timedelta(days=1)


def period_bounds(freq: Freq, anchor: date) -> Callable[[date], tuple[date, date]]:
    """Return a function mapping a day to its full period ``(first, last)``.

    Weeks are 7-day blocks counted from ``anchor`` (the first selected day), as
    in the pilot function; months and years are calendar ones.

    Args:
        freq: ``day``, ``week``, ``month`` or ``year``.
        anchor: First day of the selection.

    Returns:
        The mapping.
    """
    if freq == "day":
        return lambda d: (d, d)
    if freq == "week":
        def week(d: date) -> tuple[date, date]:
            first = anchor + timedelta(days=(d - anchor).days // 7 * 7)
            return first, first + timedelta(days=6)
        return week
    if freq == "month":
        return lambda d: (d.replace(day=1), _month_end(d))
    return lambda d: (date(d.year, 1, 1), date(d.year, 12, 31))


@dataclass
class Period:
    """Sum of the daily values of one period.

    Attributes:
        start: First day of the period inside the selection.
        end: Last day of the period inside the selection.
        partial: The selection cuts the period (its first or last days are left out).
        value: Total harmonized cell-days, or None when no day had data.
        viirs: Part of ``value`` observed by VIIRS SNPP.
        extrapolated: Part of ``value`` extrapolated from MODIS.
        days: Number of days per source (``SNPP``, ``Aqua``, ``Terra``, ``none``).
    """

    start: date
    end: date
    partial: bool
    value: float | None = None
    viirs: float = 0.0
    extrapolated: float = 0.0
    days: dict[str, int] = field(default_factory=lambda: {"SNPP": 0, "Aqua": 0, "Terra": 0, "none": 0})

    @property
    def source(self) -> str:
        """``viirs``, ``extrapolated``, ``mixed`` or ``none`` (no day with data)."""
        observed = self.days["SNPP"] > 0
        modelled = self.days["Aqua"] + self.days["Terra"] > 0
        if observed and modelled:
            return "mixed"
        if observed:
            return "viirs"
        return "extrapolated" if modelled else "none"

    def as_dict(self) -> dict[str, Any]:
        """JSON-ready row."""
        return {
            "start": self.start,
            "end": self.end,
            "partial": self.partial,
            "value": self.value,
            "viirs": self.viirs,
            "extrapolated": self.extrapolated,
            "source": self.source,
            "days_viirs": self.days["SNPP"],
            "days_aqua": self.days["Aqua"],
            "days_terra": self.days["Terra"],
            "days_missing": self.days["none"],
        }


def aggregate(days: Sequence[DayValue], freq: Freq, start: date, end: date) -> list[Period]:
    """Add the daily values up per period.

    Args:
        days: Output of :func:`daily_series`.
        freq: Period length.
        start: First selected day (anchors the weeks, clips the first period).
        end: Last selected day (clips the last period).

    Returns:
        One :class:`Period` per period touched by the selection, in order.
    """
    bounds_of = period_bounds(freq, start)
    periods: dict[date, Period] = {}
    for item in days:
        first, last = bounds_of(item.day)
        period = periods.get(first)
        if period is None:
            period = periods[first] = Period(
                start=max(first, start), end=min(last, end), partial=first < start or last > end
            )
        period.days[item.source or "none"] += 1
        if item.value is None:
            continue
        period.value = (period.value or 0.0) + item.value
        if item.source == "SNPP":
            period.viirs += item.value
        else:
            period.extrapolated += item.value
    return list(periods.values())


def monthly_profile(months: Iterable[Period]) -> list[dict[str, Any]]:
    """Average of each calendar month over the years of the selection.

    Only full months with data take part: a month cut by the selection would
    pull its average down.

    Args:
        months: Output of :func:`aggregate` with ``freq="month"``.

    Returns:
        Twelve rows ``month`` (1-12), ``mean``, ``min``, ``max`` and ``years``
        (how many years contributed; 0 with ``None`` statistics).
    """
    values: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for period in months:
        if not period.partial and period.value is not None:
            values[period.start.month].append(period.value)
    return [
        {
            "month": month,
            "mean": sum(v) / len(v) if v else None,
            "min": min(v) if v else None,
            "max": max(v) if v else None,
            "years": len(v),
        }
        for month, v in values.items()
    ]


def source_runs(days: Sequence[DayValue]) -> list[dict[str, Any]]:
    """Consecutive days with the same source, so the UI can name each period.

    Args:
        days: Output of :func:`daily_series`.

    Returns:
        Rows ``source`` (``viirs``, ``aqua``, ``terra``, ``none``), ``start``,
        ``end`` and ``days``.
    """
    runs: list[dict[str, Any]] = []
    for item in days:
        source = {"SNPP": "viirs", "Aqua": "aqua", "Terra": "terra"}.get(item.source or "", "none")
        if runs and runs[-1]["source"] == source:
            runs[-1]["end"] = item.day
            runs[-1]["days"] += 1
        else:
            runs.append({"source": source, "start": item.day, "end": item.day, "days": 1})
    return runs


#: A phase shorter than this (days) is a short gap, not a period of its own.
MIN_PHASE_DAYS = 30


def phases(runs: Sequence[dict[str, Any]], min_days: int = MIN_PHASE_DAYS) -> list[dict[str, Any]]:
    """Merge source runs into the periods a person would name: "VIIRS" or "extrapolated".

    How, in two passes:

    1. Consecutive runs of the same category are joined (Aqua and Terra are
       both ``extrapolated``); days without any data (``none``) join the phase
       they interrupt. Only days before the first data form a ``none`` phase.
    2. A phase shorter than ``min_days`` (e.g. a 5-day VIIRS outage filled with
       Aqua) is folded into the phase before it, and equal neighbours are
       joined again.

    The per-source day counts are kept, so a VIIRS phase still tells how many
    of its days were filled from MODIS (``days_aqua + days_terra``). Why: the
    raw runs (:func:`source_runs`) are exact but can be dozens of rows; the UI
    needs "extrapolated from A to B, observed by VIIRS from C to D".

    Args:
        runs: Output of :func:`source_runs`.
        min_days: Shortest phase shown on its own.

    Returns:
        Rows ``category`` (``viirs``, ``extrapolated``, ``none``), ``start``,
        ``end``, ``days``, ``days_viirs``, ``days_aqua``, ``days_terra`` and
        ``days_missing``.
    """
    counters = ("days", "days_viirs", "days_aqua", "days_terra", "days_missing")

    def absorb(target: dict[str, Any], other: dict[str, Any]) -> None:
        target["end"] = other["end"]
        for key in counters:
            target[key] += other[key]

    blocks: list[dict[str, Any]] = []
    for run in runs:
        category = {"viirs": "viirs", "aqua": "extrapolated", "terra": "extrapolated"}.get(run["source"], "none")
        block = {"category": category, "start": run["start"], "end": run["end"], **{k: 0 for k in counters}}
        block["days"] = run["days"]
        block[{"viirs": "days_viirs", "aqua": "days_aqua", "terra": "days_terra"}.get(run["source"], "days_missing")] = run["days"]
        if blocks and (category == "none" or blocks[-1]["category"] == category):
            absorb(blocks[-1], block)
        else:
            blocks.append(block)

    merged: list[dict[str, Any]] = []
    for block in blocks:
        if merged and (block["days"] < min_days or merged[-1]["category"] == block["category"]):
            absorb(merged[-1], block)
        else:
            merged.append(block)
    return merged


def summarize(days: Sequence[DayValue]) -> dict[str, Any]:
    """Totals over the whole selection.

    Returns:
        Days per source, total, observed and extrapolated cell-days.
    """
    total = Period(start=days[0].day, end=days[-1].day, partial=False) if days else None
    if total is None:
        return {"days_viirs": 0, "days_aqua": 0, "days_terra": 0, "days_missing": 0,
                "value": None, "viirs": 0.0, "extrapolated": 0.0, "source": "none"}
    for item in days:
        total.days[item.source or "none"] += 1
        if item.value is not None:
            total.value = (total.value or 0.0) + item.value
            if item.source == "SNPP":
                total.viirs += item.value
            else:
                total.extrapolated += item.value
    row = total.as_dict()
    del row["start"], row["end"], row["partial"]
    return row


def build_cell_days(
    cursor: duckdb.DuckDBPyConnection,
    bounds: tuple[float, float, float, float],
    start: date,
    end: date,
    freq: Freq,
) -> tuple[dict[str, Any], bool]:
    """Everything the cell-day panel shows, for one rectangle and date range.

    Args:
        cursor: DuckDB cursor.
        bounds: ``(west, east, south, north)``.
        start: First UTC day, inclusive.
        end: Last UTC day, inclusive.
        freq: Period of ``series``.

    Returns:
        ``(data, empty)``. ``data`` holds ``series`` (per ``freq``), ``months``
        (calendar grid), ``profile`` (average per calendar month), ``periods``
        (runs of the same source), ``phases`` (VIIRS vs extrapolated periods)
        and ``summary``. ``empty`` is True when the
        rectangle has no detection of SNPP, Aqua or Terra in the range.
    """
    counts = cell_day_counts(cursor, bounds, start, end)
    days = daily_series(counts, available_days(cursor, start, end), start, end)
    months = aggregate(days, "month", start, end)
    runs = source_runs(days)
    data = {
        "series": [p.as_dict() for p in (months if freq == "month" else aggregate(days, freq, start, end))],
        "months": [p.as_dict() for p in months],
        "profile": monthly_profile(months),
        "periods": runs,
        "phases": phases(runs),
        "summary": summarize(days),
    }
    return data, not counts
