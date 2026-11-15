"""Pydantic models for query parameters and response pieces.

Validation happens in two steps, both called explicitly from the endpoint
through :func:`parse_hotspot_query`:

1. **Per-field validation** with Pydantic (:class:`HotspotQueryParams`): types,
   allowed values, date format, ``limit``/``offset`` ranges.
2. **Cross-field validation**: ``start_date <= end_date`` and the rectangle
   built from the four corners (delegated to :mod:`app.geo`).

Every failure is turned into :class:`app.errors.InvalidParameterError`, which
names the parameter that failed so the client can highlight it.

Response features themselves are built as plain dicts in
:mod:`app.serializers` (running tens of thousands of rows through Pydantic
would be slow and adds nothing); only the small metadata blocks are models.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, ValidationInfo, field_validator

from app.errors import InvalidParameterError
from app.geo import BoundingBox, RectangleError, normalize_rectangle

#: First day with MODIS data in FIRMS (Terra started in late 2000).
EARLIEST_DATE = date(2000, 11, 1)

#: Ordered confidence categories. Position = rank, so ``confidence_min=nominal``
#: keeps every category whose rank is >= rank("nominal").
CONFIDENCE_LEVELS: tuple[str, ...] = ("low", "nominal", "high")

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

Confidence = Literal["low", "nominal", "high"]
DayNight = Literal["D", "N"]
Instrument = Literal["MODIS", "VIIRS"]
OutputFormat = Literal["geojson", "json"]


def utc_today() -> date:
    """Return today's date in UTC.

    The API compares dates against UTC (not the server's local time zone), so
    "today" must be the UTC calendar day as well.

    Returns:
        The current UTC date.
    """
    return datetime.now(timezone.utc).date()


def confidence_categories_at_least(minimum: str) -> list[str]:
    """List the confidence categories that are ``>= minimum``.

    How: categories are ordered ``low < nominal < high``; the result is the
    slice of :data:`CONFIDENCE_LEVELS` starting at ``minimum``.

    Args:
        minimum: ``"low"``, ``"nominal"`` or ``"high"``.

    Returns:
        E.g. ``["nominal", "high"]`` for ``"nominal"``.

    Example:
        >>> confidence_categories_at_least("nominal")
        ['nominal', 'high']
    """
    return list(CONFIDENCE_LEVELS[CONFIDENCE_LEVELS.index(minimum):])


class AreaQueryParams(BaseModel):
    """Query parameters shared by every area endpoint (hotspots and stats).

    Holds the rectangle corners, the inclusive UTC date range and the common
    filters, so ``/api/v1/hotspots`` and ``/api/v1/stats/*`` accept exactly the
    same names and rules. Strings coming from the URL are coerced by Pydantic
    (``"20.5"`` → ``20.5``). Enum-like values are case-insensitive
    (``instrument=viirs`` works). Unknown parameters are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    lat1: float = Field(allow_inf_nan=False)
    lon1: float = Field(allow_inf_nan=False)
    lat2: float = Field(allow_inf_nan=False)
    lon2: float = Field(allow_inf_nan=False)
    start_date: date
    end_date: date
    confidence_min: Confidence = "low"
    daynight: DayNight | None = None
    instrument: Instrument | None = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _strict_iso_date(cls, value: Any) -> Any:
        """Accept only ``YYYY-MM-DD`` strings and enforce the allowed date window.

        Pydantic alone would also accept timestamps such as ``"1700000000"``;
        a strict pattern keeps the API contract unambiguous.

        Raises:
            ValueError: If the format is wrong, the date is impossible, or it is
                outside ``[2000-11-01, today UTC]``.
        """
        if isinstance(value, date):
            parsed = value
        else:
            if not isinstance(value, str) or not _DATE_PATTERN.match(value):
                raise ValueError("must be a date in YYYY-MM-DD format")
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("must be a valid calendar date in YYYY-MM-DD format") from exc
        today = utc_today()
        if not EARLIEST_DATE <= parsed <= today:
            raise ValueError(f"must be between {EARLIEST_DATE.isoformat()} and {today.isoformat()} (UTC)")
        return parsed

    @field_validator("confidence_min", mode="before")
    @classmethod
    def _lowercase(cls, value: Any) -> Any:
        """Lower-case enum-like strings so ``HIGH`` and ``high`` are equivalent."""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("daynight", "instrument", mode="before")
    @classmethod
    def _uppercase(cls, value: Any) -> Any:
        """Upper-case enum-like strings; an empty string means "not provided"."""
        if isinstance(value, str):
            value = value.strip().upper()
            return value or None
        return value


class HotspotQueryParams(AreaQueryParams):
    """Raw query parameters of ``GET /api/v1/hotspots``, validated field by field.

    Adds paging and output format to :class:`AreaQueryParams`. The maximum
    ``limit`` comes from the validation context so it stays configurable.
    """

    vegetation_only: bool = False
    limit: int | None = None
    offset: int = Field(default=0, ge=0)
    format: OutputFormat = "geojson"

    @field_validator("format", mode="before")
    @classmethod
    def _lowercase_format(cls, value: Any) -> Any:
        """Lower-case the format so ``GEOJSON`` and ``geojson`` are equivalent."""
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("limit")
    @classmethod
    def _limit_range(cls, value: int | None, info: ValidationInfo) -> int | None:
        """Check ``1 <= limit <= max_limit`` (``max_limit`` from the context).

        Raises:
            ValueError: If the limit is outside the allowed range.
        """
        max_limit = (info.context or {}).get("max_limit", 50_000)
        if value is not None and not 1 <= value <= max_limit:
            raise ValueError(f"must be between 1 and {max_limit}")
        return value


class HotspotQuery(BaseModel):
    """Fully validated query, ready for the repository.

    Attributes:
        bbox: Normalized rectangle.
        start_date: First UTC day, inclusive.
        end_date: Last UTC day, inclusive.
        confidence_min: Lowest confidence category to include.
        daynight: ``"D"``, ``"N"`` or None for both.
        instrument: ``"MODIS"``, ``"VIIRS"`` or None for both.
        vegetation_only: Exclude ``fire_type`` 1, 2 and 3 (keeping NULL).
        limit: Maximum number of rows to return.
        offset: Number of rows to skip.
        format: ``"geojson"`` or ``"json"``.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    bbox: BoundingBox
    start_date: date
    end_date: date
    confidence_min: Confidence
    daynight: DayNight | None
    instrument: Instrument | None
    vegetation_only: bool
    limit: int
    offset: int
    format: OutputFormat


class ResponseMetadata(BaseModel):
    """``metadata`` block of a hotspots response.

    Attributes:
        bbox: ``[min_lon, min_lat, max_lon, max_lat]`` actually used for the query.
        start_date: Inclusive first day (ISO string).
        end_date: Inclusive last day (ISO string).
        returned: Number of hotspots in this response.
        limit: Limit applied.
        offset: Offset applied.
        truncated: True when more hotspots exist after this page.
    """

    bbox: list[float]
    start_date: str
    end_date: str
    returned: int
    limit: int
    offset: int
    truncated: bool


class DatasetSummary(BaseModel):
    """Body of ``GET /api/v1/dataset``.

    Attributes:
        total_records: Number of rows in ``hotspots``.
        min_date: Earliest ``acq_date`` (ISO) or None if the table is empty.
        max_date: Latest ``acq_date`` (ISO) or None if the table is empty.
        instruments: Row count per instrument, e.g. ``{"MODIS": 10, "VIIRS": 20}``.
        bbox: ``[min_lon, min_lat, max_lon, max_lat]`` covering all data, or None.
    """

    total_records: int
    min_date: str | None
    max_date: str | None
    instruments: dict[str, int]
    bbox: list[float] | None


def first_error(error: ValidationError) -> InvalidParameterError:
    """Convert the first Pydantic error into an :class:`InvalidParameterError`.

    Only the first error is reported to keep messages short and predictable.

    Args:
        error: The Pydantic validation error.

    Returns:
        An API error naming the parameter and the problem in English.
    """
    detail = error.errors(include_url=False)[0]
    parameter = str(detail["loc"][0]) if detail.get("loc") else "query"
    if detail["type"] == "missing":
        return InvalidParameterError(parameter, f"Missing required parameter '{parameter}'")
    reason = str(detail["msg"]).removeprefix("Value error, ")
    return InvalidParameterError(parameter, f"Invalid value for '{parameter}': {reason}")


def validate_area(params: AreaQueryParams) -> BoundingBox:
    """Run the cross-field checks shared by every area endpoint.

    How: ``start_date <= end_date`` (both inclusive, so equal dates select one
    day), then the corners are normalized with :func:`app.geo.normalize_rectangle`.

    Args:
        params: Parameters already validated field by field.

    Returns:
        The normalized rectangle.

    Raises:
        InvalidParameterError: If the dates are inverted or the rectangle is invalid.
    """
    if params.start_date > params.end_date:
        raise InvalidParameterError(
            "end_date", "'end_date' must be the same as or later than 'start_date'"
        )
    try:
        return normalize_rectangle(params.lat1, params.lon1, params.lat2, params.lon2)
    except RectangleError as exc:
        raise InvalidParameterError(exc.parameter, exc.message) from None


def parse_hotspot_query(
    args: dict[str, Any], *, default_limit: int, max_limit: int
) -> HotspotQuery:
    """Validate the query string of ``GET /api/v1/hotspots``.

    How: per-field validation with :class:`HotspotQueryParams`, then
    ``start_date <= end_date`` and rectangle normalization with
    :func:`app.geo.normalize_rectangle`.

    Args:
        args: Query parameters (first value of each key).
        default_limit: ``limit`` used when the client sends none.
        max_limit: Largest accepted ``limit``.

    Returns:
        The validated query.

    Raises:
        InvalidParameterError: On the first invalid or missing parameter.
    """
    try:
        params = HotspotQueryParams.model_validate(args, context={"max_limit": max_limit})
    except ValidationError as exc:
        raise first_error(exc) from None

    bbox = validate_area(params)
    return HotspotQuery(
        bbox=bbox,
        start_date=params.start_date,
        end_date=params.end_date,
        confidence_min=params.confidence_min,
        daynight=params.daynight,
        instrument=params.instrument,
        vegetation_only=params.vegetation_only,
        limit=params.limit if params.limit is not None else default_limit,
        offset=params.offset,
        format=params.format,
    )
