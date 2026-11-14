"""Convert database rows into the API response bodies (GeoJSON or plain JSON).

Two output formats exist:

* ``geojson`` (default): a GeoJSON ``FeatureCollection`` that map libraries
  (Leaflet, MapLibre, OpenLayers) can draw directly. Following RFC 7946,
  coordinates are ``[longitude, latitude]``: x before y, the opposite of how
  people usually say coordinates aloud.
* ``json``: ``{"data": [...], "metadata": {...}}`` with every column of each row.

Timestamps are written as ISO-8601 with a trailing ``Z`` (``2024-04-15T19:42:00Z``)
to make it explicit that they are UTC.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.schemas import HotspotQuery, ResponseMetadata

#: Exact message returned when a valid query finds nothing.
NO_DATA_MESSAGE = "No data found in the selected area"

#: Columns copied into each GeoJSON feature's ``properties``.
GEOJSON_PROPERTIES: tuple[str, ...] = (
    "acquired_at",
    "instrument",
    "satellite",
    "daynight",
    "frp",
    "confidence",
    "fire_type",
)


def format_timestamp(value: datetime) -> str:
    """Format a naive UTC timestamp as ISO-8601 with a ``Z`` suffix.

    The database stores ``acquired_at`` as a naive ``TIMESTAMP`` that is UTC by
    convention, so no time-zone conversion is needed; we just mark it as UTC.

    Args:
        value: Timestamp from DuckDB.

    Returns:
        E.g. ``"2024-04-15T19:42:00Z"``.
    """
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_value(value: Any) -> Any:
    """Make a single database value JSON-friendly.

    Args:
        value: Any value returned by DuckDB.

    Returns:
        ISO strings for datetimes/dates, the value unchanged otherwise.
    """
    if isinstance(value, datetime):
        return format_timestamp(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def build_metadata(query: HotspotQuery, returned: int, truncated: bool) -> dict[str, Any]:
    """Build the ``metadata`` block shared by both formats.

    Args:
        query: The validated query (bbox, dates, limit, offset).
        returned: Number of rows in this response.
        truncated: Whether more rows exist after this page.

    Returns:
        The metadata as a dict.
    """
    return ResponseMetadata(
        bbox=query.bbox.as_geojson_bbox(),
        start_date=query.start_date.isoformat(),
        end_date=query.end_date.isoformat(),
        returned=returned,
        limit=query.limit,
        offset=query.offset,
        truncated=truncated,
    ).model_dump()


def row_to_feature(row: dict[str, Any]) -> dict[str, Any]:
    """Convert one row into a GeoJSON ``Feature`` with a ``Point`` geometry.

    Args:
        row: Row dict with at least latitude, longitude and the property columns.

    Returns:
        The feature; coordinates are ``[longitude, latitude]``.
    """
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
        "properties": {name: _json_value(row.get(name)) for name in GEOJSON_PROPERTIES},
    }


def to_geojson(rows: list[dict[str, Any]], query: HotspotQuery, truncated: bool) -> dict[str, Any]:
    """Build the GeoJSON ``FeatureCollection`` response.

    Args:
        rows: Rows returned by the repository.
        query: The validated query.
        truncated: Whether more rows exist.

    Returns:
        The response body. ``message`` is added only when ``rows`` is empty.
    """
    body: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": [row_to_feature(row) for row in rows],
        "metadata": build_metadata(query, len(rows), truncated),
    }
    if not rows:
        body["message"] = NO_DATA_MESSAGE
    return body


def to_json(rows: list[dict[str, Any]], query: HotspotQuery, truncated: bool) -> dict[str, Any]:
    """Build the plain JSON response with full records.

    Args:
        rows: Rows returned by the repository.
        query: The validated query.
        truncated: Whether more rows exist.

    Returns:
        ``{"data": [...], "metadata": {...}}``, plus ``message`` only when empty.
    """
    body: dict[str, Any] = {
        "data": [{key: _json_value(value) for key, value in row.items()} for row in rows],
        "metadata": build_metadata(query, len(rows), truncated),
    }
    if not rows:
        body["message"] = NO_DATA_MESSAGE
    return body
