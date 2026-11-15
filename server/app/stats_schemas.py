"""Query parameters of the dashboard statistics endpoints (``/api/v1/stats/*``).

Every stats endpoint accepts the same area parameters as ``/api/v1/hotspots``
(``lat1``, ``lon1``, ``lat2``, ``lon2``, ``start_date``, ``end_date``,
``confidence_min``, ``daynight``, ``instrument``) plus two extra filters:

* ``satellite``: ``Terra``, ``Aqua``, ``SNPP``, ``NOAA-20`` or ``NOAA-21``
  (case-insensitive). Default: every satellite.
* ``fire_type``: ``0`` (default), ``1``, ``2``, ``3`` or ``all``. ``0`` keeps
  vegetation fires **and** detections with unknown type (NULL), exactly like
  ``vegetation_only=true`` on ``/api/v1/hotspots``: most near-real-time VIIRS
  data has no type, and dropping it would silently hide a whole sensor.

Validation reuses :class:`app.schemas.AreaQueryParams` and
:func:`app.schemas.validate_area`, so error messages and the 400 body are the
same as on ``/api/v1/hotspots``. Endpoint-specific options (``freq``, ``field``,
``bins``...) are small Pydantic models parsed with :func:`parse_options`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.geo import BoundingBox
from app.schemas import AreaQueryParams, first_error, validate_area

#: Canonical satellite names, keyed by their lower-case spelling.
SATELLITES: dict[str, str] = {
    name.lower(): name for name in ("Terra", "Aqua", "SNPP", "NOAA-20", "NOAA-21")
}

#: Largest sample returned by ``/stats/scatter`` (charts stay readable and fast).
MAX_SCATTER_LIMIT = 5000


class StatsQueryParams(AreaQueryParams):
    """Area parameters plus the stats-only filters ``satellite`` and ``fire_type``."""

    satellite: str | None = None
    fire_type: Literal["0", "1", "2", "3", "all"] = "0"

    @field_validator("satellite", mode="before")
    @classmethod
    def _canonical_satellite(cls, value: Any) -> Any:
        """Map any capitalization (``noaa-20``) to the stored name (``NOAA-20``).

        Raises:
            ValueError: If the satellite is not one of :data:`SATELLITES`.
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        name = SATELLITES.get(str(value).strip().lower())
        if name is None:
            raise ValueError(f"must be one of {', '.join(SATELLITES.values())}")
        return name

    @field_validator("fire_type", mode="before")
    @classmethod
    def _fire_type_text(cls, value: Any) -> Any:
        """Accept ``0``..``3`` as numbers or text and ``all`` in any case."""
        return str(value).strip().lower() if value is not None else value


@dataclass(frozen=True)
class StatsQuery:
    """Validated area and filters shared by every stats endpoint.

    Attributes:
        bbox: Normalized rectangle.
        start_date: First UTC day, inclusive.
        end_date: Last UTC day, inclusive.
        confidence_min: Lowest confidence category to include.
        daynight: ``"D"``, ``"N"`` or None for both.
        instrument: ``"MODIS"``, ``"VIIRS"`` or None for both.
        satellite: Canonical satellite name or None for all.
        fire_type: 0..3, or None for every type (``fire_type=all``).
    """

    bbox: BoundingBox
    start_date: date
    end_date: date
    confidence_min: str
    daynight: str | None
    instrument: str | None
    satellite: str | None
    fire_type: int | None

    def filters(self) -> dict[str, Any]:
        """Return the applied filters for the response ``metadata``.

        Returns:
            ``{"confidence_min", "daynight", "instrument", "satellite", "fire_type"}``,
            with ``fire_type`` as ``"all"`` when no type filter is applied.
        """
        return {
            "confidence_min": self.confidence_min,
            "daynight": self.daynight,
            "instrument": self.instrument,
            "satellite": self.satellite,
            "fire_type": "all" if self.fire_type is None else self.fire_type,
        }


def parse_stats_query(args: dict[str, Any]) -> StatsQuery:
    """Validate the area and filter parameters of a stats request.

    Args:
        args: Query parameters (first value of each key).

    Returns:
        The validated query.

    Raises:
        InvalidParameterError: On the first invalid or missing parameter.
    """
    try:
        params = StatsQueryParams.model_validate(args)
    except ValidationError as exc:
        raise first_error(exc) from None
    bbox = validate_area(params)
    return StatsQuery(
        bbox=bbox,
        start_date=params.start_date,
        end_date=params.end_date,
        confidence_min=params.confidence_min,
        daynight=params.daynight,
        instrument=params.instrument,
        satellite=params.satellite,
        fire_type=None if params.fire_type == "all" else int(params.fire_type),
    )


class _Options(BaseModel):
    """Base for endpoint options: ignore other parameters, lower-case enum strings."""

    model_config = ConfigDict(extra="ignore")

    @field_validator("*", mode="before")
    @classmethod
    def _lowercase(cls, value: Any) -> Any:
        """Lower-case text so ``freq=WEEK`` and ``freq=week`` are equivalent."""
        return value.strip().lower() if isinstance(value, str) else value


class TimeseriesOptions(_Options):
    """``/stats/timeseries``: ``freq`` is the period length (weeks start on Monday)."""

    freq: Literal["day", "week", "month"] = "day"


class DistributionOptions(_Options):
    """``/stats/distribution``: histogram of one field with ``bins`` equal-width bins.

    With ``log=true`` the bins are equal-width in ``log10`` space (only values > 0).
    """

    field: Literal["frp", "bright_mir", "bright_tir", "confidence_raw"] = "frp"
    bins: int = Field(default=20, ge=1, le=100)
    log: bool = False


class ScatterOptions(_Options):
    """``/stats/scatter``: deterministic random sample of ``(x, y)`` pairs."""

    x: Literal["bright_mir", "pixel_area_km2"] = "bright_mir"
    y: Literal["bright_tir", "frp"] = "bright_tir"
    limit: int = Field(default=2000, ge=1, le=MAX_SCATTER_LIMIT)


class CalendarOptions(_Options):
    """``/stats/calendar``: value per day of year (or ISO week) and year."""

    metric: Literal["detections", "frp"] = "detections"
    granularity: Literal["day", "week"] = "day"


class CategoryOptions(_Options):
    """``/stats/by-category``: which column to group by."""

    field: Literal["daynight", "satellite", "type", "confidence_level"]


class ScanOptions(_Options):
    """``/stats/by-scan``: number of equal-width scan ranges per sensor."""

    bins: int = Field(default=10, ge=1, le=50)


class TopEventsOptions(_Options):
    """``/stats/top-events``: how many detections to return."""

    n: int = Field(default=10, ge=1, le=100)


#: Default number of points of ``/stats/points`` (capped by ``MAX_LIMIT``).
DEFAULT_POINTS_LIMIT = 5000


class PointsOptions(_Options):
    """``/stats/points``: maximum number of points (upper bound from ``MAX_LIMIT``).

    ``None`` means "not sent"; the route then uses
    ``min(DEFAULT_POINTS_LIMIT, MAX_LIMIT)``.
    """

    limit: int | None = Field(default=None, ge=1)


class GridOptions(_Options):
    """``/stats/grid``: cell size in degrees."""

    cell: float = Field(default=0.25, gt=0, le=5, allow_inf_nan=False)


class CellDaysOptions(_Options):
    """``/stats/celldays``: ``freq`` of the ``series`` (weeks are 7-day blocks from ``start_date``)."""

    freq: Literal["day", "week", "month", "year"] = "month"


OptionsT = TypeVar("OptionsT", bound=BaseModel)


def parse_options(model: type[OptionsT], args: dict[str, Any]) -> OptionsT:
    """Validate the endpoint-specific options of a stats request.

    Args:
        model: Options model, e.g. :class:`TimeseriesOptions`.
        args: Query parameters (first value of each key).

    Returns:
        The validated options.

    Raises:
        InvalidParameterError: On the first invalid or missing option.
    """
    try:
        return model.model_validate(args)
    except ValidationError as exc:
        raise first_error(exc) from None
