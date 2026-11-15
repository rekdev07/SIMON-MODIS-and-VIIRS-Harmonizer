"""``GET /api/v1/calendar``: burning activity calendar (hotspots per month) of an area.

Flow of a request::

    query string ──► schemas.parse_calendar_query   (Pydantic + geo: 400 on error)
                 ──► repository.calendar_counts      (GROUP BY year, month in DuckDB)
                 ──► repository.data_coverage        (first/last loaded day)
                 ──► calendar.build_calendar         (zero filling, medians, year totals)
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from app.calendar import build_calendar
from app.db import get_cursor
from app.repository import calendar_counts, data_coverage
from app.schemas import parse_calendar_query

bp = Blueprint("calendar", __name__, url_prefix="/api/v1")


@bp.get("/calendar")
def get_calendar() -> Response:
    """Return hotspot counts per month for the requested rectangle.

    See ``docs/api.md`` for parameters and the response shape. Counts are raw
    (not harmonized between MODIS and VIIRS yet); ``harmonized`` says so.

    Returns:
        The calendar body built by :func:`app.calendar.build_calendar`.

    Raises:
        InvalidParameterError: If a parameter is missing or invalid (400).
        DatabaseUnavailableError: If the database cannot be opened (503).
    """
    query = parse_calendar_query(request.args.to_dict(flat=True))
    cursor = get_cursor()
    rows = calendar_counts(cursor, query)
    coverage = data_coverage(cursor, query.instrument)
    return jsonify(build_calendar(rows, coverage, query.bbox))
