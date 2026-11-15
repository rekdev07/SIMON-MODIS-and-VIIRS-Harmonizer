"""``GET /api/v1/stats/*``: pre-computed aggregates for the dashboard charts.

Every endpoint accepts the area parameters of ``/api/v1/hotspots`` plus the
filters described in :mod:`app.stats_schemas`, and answers with the envelope
of :func:`app.serializers.to_stats_body`. Flow of a request::

    query string ──► stats_schemas.parse_stats_query + parse_options  (400 on error)
                 ──► stats_repository.<aggregate>                     (DuckDB SQL)
                 ──► serializers.to_stats_body

See ``docs/API.md`` for the contract of each endpoint.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request

from app import stats_repository as repo
from app.db import get_cursor
from app.errors import InvalidParameterError
from app.serializers import to_stats_body
from app.stats_schemas import (
    DEFAULT_POINTS_LIMIT,
    CalendarOptions,
    CategoryOptions,
    DistributionOptions,
    GridOptions,
    PointsOptions,
    ScanOptions,
    ScatterOptions,
    StatsQuery,
    TimeseriesOptions,
    TopEventsOptions,
    parse_options,
    parse_stats_query,
)

bp = Blueprint("stats", __name__, url_prefix="/api/v1/stats")

#: Unit of every numeric field a stats endpoint can return.
UNITS: dict[str, str] = {
    "frp": "MW",
    "frp_mean": "MW",
    "frp_max": "MW",
    "frp_total": "MW",
    "frp_p5": "MW",
    "frp_median": "MW",
    "bright_mir": "K",
    "bright_tir": "K",
    "bright_mir_mean": "K",
    "bright_tir_mean": "K",
    "scan": "km",
    "scan_start": "km",
    "scan_end": "km",
    "track": "km",
    "pixel_area_km2": "km2",
    "lat": "degrees",
    "lon": "degrees",
    "confidence_raw": "percent (MODIS only)",
}


def _units(*names: str) -> dict[str, str]:
    """Pick the units of the given fields from :data:`UNITS`."""
    return {name: UNITS[name] for name in names}


def _args() -> dict[str, Any]:
    """Return the query string as a flat dict (first value of each key)."""
    return request.args.to_dict(flat=True)


def _area() -> StatsQuery:
    """Validate the area and filter parameters of the current request."""
    return parse_stats_query(_args())


def _respond(
    data: Any, query: StatsQuery, units: dict[str, str], *, empty: bool | None = None, **extra: Any
) -> Response:
    """Wrap ``data`` in the stats envelope; ``empty`` defaults to ``not data``."""
    is_empty = (not data) if empty is None else empty
    return jsonify(to_stats_body(data, query, empty=is_empty, units=units, extra=extra))


@bp.get("/summary")
def summary() -> Response:
    """KPIs per sensor (chart 1)."""
    query = _area()
    rows = repo.summary(get_cursor(), query)
    return _respond(rows, query, _units("frp_mean", "frp_max", "bright_mir_mean", "bright_tir_mean"))


@bp.get("/timeseries")
def timeseries() -> Response:
    """Detections, FRP and mean MIR brightness per period and sensor (charts 2-5)."""
    query = _area()
    options = parse_options(TimeseriesOptions, _args())
    rows = repo.timeseries(get_cursor(), query, options.freq)
    units = _units("frp_total", "frp_mean", "bright_mir_mean")
    return _respond(rows, query, units, freq=options.freq)


@bp.get("/distribution")
def distribution() -> Response:
    """Histogram of one field per sensor (charts 6-8 and 17)."""
    query = _area()
    options = parse_options(DistributionOptions, _args())
    rows, excluded = repo.distribution(get_cursor(), query, options.field, options.bins, options.log)
    return _respond(
        rows,
        query,
        {"bin_start": UNITS[options.field], "bin_end": UNITS[options.field]},
        field=options.field,
        bins=options.bins,
        log=options.log,
        excluded=excluded,
    )


@bp.get("/scatter")
def scatter() -> Response:
    """Sample of (x, y) pairs with sensor and confidence (charts 9, 10 and 19)."""
    query = _area()
    options = parse_options(ScatterOptions, _args())
    rows, available = repo.scatter(get_cursor(), query, options.x, options.y, options.limit)
    return _respond(
        rows,
        query,
        {"x": UNITS[options.x], "y": UNITS[options.y]},
        x=options.x,
        y=options.y,
        limit=options.limit,
        available=available,
        returned=len(rows),
        sampled=available > len(rows),
    )


@bp.get("/calendar")
def calendar() -> Response:
    """Detections or FRP per year and day of year / ISO week (chart 11)."""
    query = _area()
    options = parse_options(CalendarOptions, _args())
    rows = repo.calendar(get_cursor(), query, options.metric, options.granularity)
    units = {"value": "detections" if options.metric == "detections" else "MW"}
    return _respond(rows, query, units, metric=options.metric, granularity=options.granularity)


@bp.get("/by-hour")
def by_hour() -> Response:
    """Detections per UTC hour and satellite (chart 12)."""
    query = _area()
    return _respond(repo.by_hour(get_cursor(), query), query, {"hour_utc": "hour (UTC)"})


@bp.get("/by-category")
def by_category() -> Response:
    """Detections and mean FRP per category and sensor (charts 13-16)."""
    query = _area()
    options = parse_options(CategoryOptions, _args())
    rows = repo.by_category(get_cursor(), query, options.field)
    return _respond(rows, query, _units("frp_mean"), field=options.field)


@bp.get("/by-scan")
def by_scan() -> Response:
    """FRP 5th percentile and median per scan range and sensor (chart 18)."""
    query = _area()
    options = parse_options(ScanOptions, _args())
    rows = repo.by_scan(get_cursor(), query, options.bins)
    units = _units("scan_start", "scan_end", "frp_p5", "frp_median")
    return _respond(rows, query, units, bins=options.bins)


@bp.get("/top-events")
def top_events() -> Response:
    """The detections with the highest FRP (chart 20)."""
    query = _area()
    options = parse_options(TopEventsOptions, _args())
    rows = repo.top_events(get_cursor(), query, options.n)
    units = _units("lat", "lon", "frp", "bright_mir", "bright_tir")
    return _respond(rows, query, units, n=options.n)


@bp.get("/points")
def points() -> Response:
    """Light-weight map points, strongest FRP first (chart 21)."""
    query = _area()
    options = parse_options(PointsOptions, _args())
    max_limit = current_app.config["SETTINGS"].max_limit
    limit = options.limit if options.limit is not None else min(DEFAULT_POINTS_LIMIT, max_limit)
    if limit > max_limit:
        raise InvalidParameterError("limit", f"Invalid value for 'limit': must be between 1 and {max_limit}")
    rows, truncated = repo.points(get_cursor(), query, limit)
    return _respond(rows, query, _units("lat", "lon", "frp"), limit=limit, returned=len(rows), truncated=truncated)


@bp.get("/grid")
def grid() -> Response:
    """Detections and total FRP per grid cell and sensor (chart 22)."""
    query = _area()
    options = parse_options(GridOptions, _args())
    rows = repo.grid(get_cursor(), query, options.cell)
    units = {"lat": "degrees (cell center)", "lon": "degrees (cell center)", "cell": "degrees", "frp_total": "MW"}
    return _respond(rows, query, units, cell=options.cell)


@bp.get("/sensor-comparison")
def sensor_comparison() -> Response:
    """Daily detections and FRP per sensor plus the VIIRS/MODIS ratio (charts 23-24)."""
    query = _area()
    daily, ratio = repo.sensor_comparison(get_cursor(), query)
    units = {"frp_total": "MW", "detections_ratio": "VIIRS / MODIS", "frp_ratio": "VIIRS / MODIS"}
    return _respond({"daily": daily, "ratio": ratio}, query, units, empty=not daily)


@bp.get("/monthly")
def monthly() -> Response:
    """Detections per calendar month (1-12) and sensor, all years together (chart 25)."""
    query = _area()
    return _respond(repo.monthly(get_cursor(), query), query, {})
