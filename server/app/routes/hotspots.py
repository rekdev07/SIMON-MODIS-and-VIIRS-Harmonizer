"""``GET /api/v1/hotspots``: hotspots inside a rectangle and a date range.

Flow of a request::

    query string ──► schemas.parse_hotspot_query  (Pydantic + geo: 400 on error)
                 ──► repository.find_hotspots      (parameterized SQL, limit + 1)
                 ──► serializers.to_geojson / to_json
"""

from __future__ import annotations

from flask import Blueprint, Response, current_app, jsonify, request

from app.db import get_cursor
from app.repository import find_hotspots
from app.schemas import parse_hotspot_query
from app.serializers import to_geojson, to_json

bp = Blueprint("hotspots", __name__, url_prefix="/api/v1")


@bp.get("/hotspots")
def list_hotspots() -> Response:
    """Return the hotspots in the requested rectangle and dates.

    See ``docs/api.md`` for every parameter. A valid query with no matches
    returns HTTP 200 with an empty list and ``"message": "No data found in the
    selected area"``.

    Returns:
        A GeoJSON ``FeatureCollection`` or ``{"data", "metadata"}`` JSON body.

    Raises:
        InvalidParameterError: If a parameter is missing or invalid (400).
        DatabaseUnavailableError: If the database cannot be opened (503).
    """
    settings = current_app.config["SETTINGS"]
    query = parse_hotspot_query(
        request.args.to_dict(flat=True),
        default_limit=settings.default_limit,
        max_limit=settings.max_limit,
    )
    rows, truncated = find_hotspots(get_cursor(), query)
    serialize = to_geojson if query.format == "geojson" else to_json
    return jsonify(serialize(rows, query, truncated))
