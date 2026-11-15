"""Build the burning activity calendar from monthly counts (pure functions).

The calendar is a year × month grid of hotspot counts for one area. This module
turns the sparse rows returned by :func:`app.repository.calendar_counts` into
the full response body::

    sparse rows from SQL             full grid (coverage 2013-01-01 .. 2014-01-01)
    (2013, 4, 812, 0, 812)    ──►    2013-01 … 2013-12   every month present, 0 when no fires
    (2013, 5, 1290, 0, 1290)         2014-01             partial (only 1 of 31 days loaded)

Three rules make the grid honest:

* **Zero vs no data.** Every month inside the database's coverage appears,
  with ``count = 0`` when nothing burned. Months outside the coverage are
  simply absent, so the client can draw them as "no data".
* **Partial months.** A month the coverage cuts (it starts after the 1st or
  ends before the last day) is flagged ``partial``. Its count is real but not
  comparable with full months.
* **Medians use full months only.** ``monthly_median[i]`` is the median count
  of month ``i + 1`` over every *complete* year-month in the coverage, so a
  half-loaded month never drags the reference down. The median (not the mean)
  is used because one extreme fire season would pull an average far away from
  a typical year.

No Flask and no database here, so the logic is easy to test.
"""

from __future__ import annotations

import calendar as stdlib_calendar
from collections.abc import Iterable
from datetime import date
from statistics import median
from typing import Any

from app.geo import BoundingBox

#: Exact message returned when an area has no hotspots at all (same as /hotspots).
NO_DATA_MESSAGE = "No data found in the selected area"


def _month_range(first: date, last: date) -> Iterable[tuple[int, int]]:
    """Yield every ``(year, month)`` from ``first``'s month to ``last``'s, inclusive.

    Args:
        first: Any day of the first month.
        last: Any day of the last month.

    Yields:
        ``(year, month)`` pairs in chronological order.

    Example:
        >>> list(_month_range(date(2013, 11, 5), date(2014, 1, 1)))
        [(2013, 11), (2013, 12), (2014, 1)]
    """
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        yield year, month
        month += 1
        if month == 13:
            year, month = year + 1, 1


def is_partial_month(year: int, month: int, first: date, last: date) -> bool:
    """Tell whether the coverage ``[first, last]`` misses some days of a month.

    Args:
        year: Calendar year.
        month: Calendar month (1–12).
        first: First covered day.
        last: Last covered day.

    Returns:
        True when the month starts before ``first`` or ends after ``last``.

    Example:
        >>> is_partial_month(2014, 1, date(2013, 1, 1), date(2014, 1, 1))
        True
    """
    month_start = date(year, month, 1)
    month_end = date(year, month, stdlib_calendar.monthrange(year, month)[1])
    return month_start < first or month_end > last


def build_calendar(
    rows: Iterable[tuple[int, int, int, int, int]],
    coverage: tuple[date, date] | None,
    bbox: BoundingBox,
) -> dict[str, Any]:
    """Assemble the ``GET /api/v1/calendar`` response body.

    Args:
        rows: ``(year, month, total, modis, viirs)`` from the repository; months
            without hotspots may be missing.
        coverage: ``(first_day, last_day)`` of the loaded data, or None if empty.
        bbox: Rectangle that was queried (echoed back).

    Returns:
        A dict with ``bbox``, ``coverage``, ``harmonized`` (always False until
        the harmonizer exists), ``total``, ``months``, ``years`` and
        ``monthly_median``; plus ``message`` only when ``total`` is 0.
    """
    counts = {(year, month): (total, modis, viirs) for year, month, total, modis, viirs in rows}

    months: list[dict[str, Any]] = []
    if coverage is not None:
        first, last = coverage
        for year, month in _month_range(first, last):
            total, modis, viirs = counts.get((year, month), (0, 0, 0))
            months.append(
                {
                    "year": year,
                    "month": month,
                    "count": total,
                    "modis": modis,
                    "viirs": viirs,
                    "partial": is_partial_month(year, month, first, last),
                }
            )

    by_month: dict[int, list[int]] = {m: [] for m in range(1, 13)}
    years: dict[int, dict[str, Any]] = {}
    for cell in months:
        if not cell["partial"]:
            by_month[cell["month"]].append(cell["count"])
        entry = years.setdefault(cell["year"], {"year": cell["year"], "count": 0, "partial": False})
        entry["count"] += cell["count"]
        # A year is partial if any of its 12 months is missing or partial.
        entry["partial"] = entry["partial"] or cell["partial"]
    for entry in years.values():
        months_of_year = sum(1 for cell in months if cell["year"] == entry["year"])
        if months_of_year < 12:
            entry["partial"] = True

    total = sum(cell["count"] for cell in months)
    body: dict[str, Any] = {
        "bbox": bbox.as_geojson_bbox(),
        "coverage": None
        if coverage is None
        else {"start_date": coverage[0].isoformat(), "end_date": coverage[1].isoformat()},
        "harmonized": False,
        "total": total,
        "months": months,
        "years": list(years.values()),
        "monthly_median": [
            float(median(values)) if values else None for values in by_month.values()
        ],
    }
    if total == 0:
        body["message"] = NO_DATA_MESSAGE
    return body
