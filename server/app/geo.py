"""Rectangle (bounding box) normalization and validation.

The user selects an area by giving two opposite corners of a rectangle,
``(lat1, lon1)`` and ``(lat2, lon2)``. They may click the corners in any order
(top-left then bottom-right, bottom-right then top-left, ...), so this module
turns any pair of corners into a canonical box with explicit minimum and
maximum values::

          lon1=-100                 lon2=-98
    lat1=20  A ─────────────────────┐
             │                      │      min_lat = min(20, 18) = 18
             │                      │      max_lat = max(20, 18) = 20
             │                      │      min_lon = min(-100, -98) = -100
    lat2=18  └───────────────────── B      max_lon = max(-100, -98) = -98

Swapping A and B gives exactly the same box, which is why the order of the
corners never changes the result of a query.

Assumption: the rectangle never crosses the antimeridian (longitude ±180°).
A box from lon 170 to lon -170 is interpreted as the wide box from -170 to 170,
not the narrow one across the Pacific. This keeps the SQL a single
``BETWEEN`` per axis.

The functions here are pure (no Flask, no database) so they are easy to test
and to read with ``python -m pydoc app.geo``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0


class RectangleError(ValueError):
    """A corner or the rectangle as a whole is invalid.

    Attributes:
        parameter: Name of the query parameter to blame (e.g. ``"lat2"``), so the
            API can tell the client exactly which value failed.
    """

    def __init__(self, parameter: str, message: str) -> None:
        """Create the error.

        Args:
            parameter: Query parameter that caused the error.
            message: Human-readable explanation.
        """
        super().__init__(message)
        self.parameter = parameter
        self.message = message


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned rectangle in WGS84 degrees with ``min <= max`` on both axes.

    Attributes:
        min_lat: Southern edge.
        min_lon: Western edge.
        max_lat: Northern edge.
        max_lon: Eastern edge.
    """

    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def contains(self, latitude: float, longitude: float) -> bool:
        """Tell whether a point lies inside the box, edges included.

        The comparison is inclusive (``<=``) on all four sides, exactly like
        SQL ``BETWEEN``: a hotspot lying exactly on an edge belongs to the box.
        Inclusive edges mean that two boxes sharing an edge both return a point
        on that edge, which is preferable to a point silently belonging to none.

        Args:
            latitude: Point latitude.
            longitude: Point longitude.

        Returns:
            True if ``min_lat <= latitude <= max_lat`` and
            ``min_lon <= longitude <= max_lon``.

        Example:
            >>> BoundingBox(18, -100, 20, -98).contains(20, -98)
            True
        """
        return (
            self.min_lat <= latitude <= self.max_lat
            and self.min_lon <= longitude <= self.max_lon
        )

    def as_geojson_bbox(self) -> list[float]:
        """Return the box in GeoJSON order ``[min_lon, min_lat, max_lon, max_lat]``.

        GeoJSON (RFC 7946) always puts longitude (x) before latitude (y).

        Returns:
            A list of four floats.
        """
        return [self.min_lon, self.min_lat, self.max_lon, self.max_lat]


def validate_latitude(value: float, parameter: str) -> float:
    """Check that a latitude is a finite number in ``[-90, 90]``.

    Args:
        value: Latitude in degrees.
        parameter: Query parameter name, used in the error.

    Returns:
        The same value, as float.

    Raises:
        RectangleError: If the value is NaN/infinite or out of range.
    """
    if not math.isfinite(value) or not MIN_LATITUDE <= value <= MAX_LATITUDE:
        raise RectangleError(parameter, f"'{parameter}' must be a latitude between -90 and 90")
    return float(value)


def validate_longitude(value: float, parameter: str) -> float:
    """Check that a longitude is a finite number in ``[-180, 180]``.

    Args:
        value: Longitude in degrees.
        parameter: Query parameter name, used in the error.

    Returns:
        The same value, as float.

    Raises:
        RectangleError: If the value is NaN/infinite or out of range.
    """
    if not math.isfinite(value) or not MIN_LONGITUDE <= value <= MAX_LONGITUDE:
        raise RectangleError(parameter, f"'{parameter}' must be a longitude between -180 and 180")
    return float(value)


def normalize_rectangle(lat1: float, lon1: float, lat2: float, lon2: float) -> BoundingBox:
    """Build a canonical :class:`BoundingBox` from two corners given in any order.

    How: each coordinate is range-checked, then
    ``min_lat = min(lat1, lat2)``, ``max_lat = max(lat1, lat2)`` and the same for
    longitude. Because ``min``/``max`` are symmetric, swapping the corners gives
    the same box.

    Why reject degenerate boxes: if ``lat1 == lat2`` (or ``lon1 == lon2``) the
    "rectangle" is a line or a point with zero area. That is almost always a
    double click or a bug in the client, so it is reported instead of silently
    returning hotspots that happen to lie exactly on that line.

    Args:
        lat1: Latitude of the first corner.
        lon1: Longitude of the first corner.
        lat2: Latitude of the opposite corner.
        lon2: Longitude of the opposite corner.

    Returns:
        The normalized box.

    Raises:
        RectangleError: If a coordinate is out of range or the box has zero
            width or height.

    Example:
        >>> normalize_rectangle(20, -98, 18, -100)
        BoundingBox(min_lat=18.0, min_lon=-100.0, max_lat=20.0, max_lon=-98.0)
    """
    lat1 = validate_latitude(lat1, "lat1")
    lon1 = validate_longitude(lon1, "lon1")
    lat2 = validate_latitude(lat2, "lat2")
    lon2 = validate_longitude(lon2, "lon2")

    box = BoundingBox(
        min_lat=min(lat1, lat2),
        min_lon=min(lon1, lon2),
        max_lat=max(lat1, lat2),
        max_lon=max(lon1, lon2),
    )
    if box.max_lat - box.min_lat <= 0:
        raise RectangleError("lat2", "The rectangle has zero height: 'lat1' and 'lat2' must differ")
    if box.max_lon - box.min_lon <= 0:
        raise RectangleError("lon2", "The rectangle has zero width: 'lon1' and 'lon2' must differ")
    return box
