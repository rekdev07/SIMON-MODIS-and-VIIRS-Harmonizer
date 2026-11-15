"""``GET /api/v1/calendar``: burning activity calendar (hotspots per month) of an area.

Flow of a request::

    query string ──► schemas.parse_calendar_query   (Pydantic + geo: 400 on error)
                 ──► repository.calendar_counts      (GROUP BY year, month in DuckDB)
                 ──► repository.data_coverage        (first/last loaded day)
                 ──► calendar.build_calendar         (zero filling, medians, year totals)

With ``harmonized=true`` the counts come from :mod:`app.harmonization`
instead: one continuous series in MODIS Terra+Aqua units (2000 → today).
"""

from __future__ import annotations

from flask import Blueprint, Response, current_app, jsonify, request

from app.calendar import build_calendar
from app.db import get_cursor, get_database
from app.harmonization import build_harmonized_calendar
from app.repository import calendar_counts, data_coverage
from app.schemas import parse_calendar_query

bp = Blueprint("calendar", __name__, url_prefix="/api/v1")


@bp.get("/calendar")
def get_calendar() -> Response:
    """Return hotspot counts per month for the requested rectangle.

    See ``docs/api.md`` for parameters and the response shape. By default the
    counts are raw per sensor (``harmonized: false``); ``harmonized=true``
    returns the continuous harmonized series (``harmonized: true``).

    Returns:
        The calendar body built by :func:`app.calendar.build_calendar`.

    Raises:
        InvalidParameterError: If a parameter is missing or invalid (400).
        DatabaseUnavailableError: If the database cannot be opened (503).
    """
    query = parse_calendar_query(request.args.to_dict(flat=True))
    cursor = get_cursor()
    if query.harmonized:
        path = get_database().path
        cache_key = (str(path), path.stat().st_mtime if path.is_file() else 0.0)
        config = current_app.config["SETTINGS"].harmonization
        return jsonify(build_harmonized_calendar(cursor, query, config, cache_key))
    rows = calendar_counts(cursor, query)
    coverage = data_coverage(cursor, query.instrument)
    return jsonify(build_calendar(rows, coverage, query.bbox))
