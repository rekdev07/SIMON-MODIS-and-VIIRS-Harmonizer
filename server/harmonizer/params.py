"""Fit, store and load the harmonization parameters (ratios, Terra factor, reliable count).

Why a table: fitting reads millions of rows (about one second in DuckDB); the
calendar endpoint is called on every map selection. ``scripts/harmonize.py fit``
fits once and writes the table ``harmonization_params``; the read-only API
loads it (and, if the table is missing, fits in memory once per process).

Table layout (one row per parameter, so new ones need no migration)::

    name                value   n_modis  n_viirs  fit_start   fit_end     computed_at  note
    r_day               3.85    590000   2270000  2012-02-01  2025-12-31  ...          Σ VIIRS_day / Σ MODIS_day
    r_night             7.10    ...
    r_total             4.33    ...
    terra_factor        2.22    623221   ...      2003-01-01  2011-12-31  ...          Σ (Terra+Aqua) / Σ Terra
    k_frp               0.91    ...
    min_reliable_count  10      ...                                                   monthly MODIS units
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import duckdb

from harmonizer.config import HarmonizationConfig
from harmonizer.data import monthly_counts
from harmonizer.method import Ratios, fit_ratios, terra_factor

TABLE = "harmonization_params"

#: Used when no reliable count was fitted (e.g. tiny test databases).
DEFAULT_MIN_RELIABLE_COUNT = 10.0


@dataclass(frozen=True)
class HarmonizationParams:
    """Everything the calendar needs to harmonize an area.

    Attributes:
        ratios: VIIRS/MODIS ratios fitted on ``fit_start..fit_end``.
        terra_factor: Terra → Terra+Aqua factor.
        terra_n: ``(terra_sum, aqua_sum)`` behind the factor.
        min_reliable_count: Monthly count (MODIS units) above which the box
            validation error stays acceptable (reliability test 3).
        fit_start, fit_end, terra_fit_start, terra_fit_end: Fit periods.
        computed_at: When the fit ran (UTC), or None.
    """

    ratios: Ratios
    terra_factor: float
    terra_n: tuple[int, int]
    min_reliable_count: float
    fit_start: date
    fit_end: date
    terra_fit_start: date
    terra_fit_end: date
    computed_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        """JSON-friendly summary (used by the API's ``harmonization`` block)."""
        r = self.ratios
        return {
            "r_day": _clean(r.day),
            "r_night": _clean(r.night),
            "r_total": _clean(r.total),
            "terra_factor": _clean(self.terra_factor),
            "k_frp": _clean(r.k_frp),
            "min_reliable_count": self.min_reliable_count,
            "fit_period": {"start_date": self.fit_start.isoformat(), "end_date": self.fit_end.isoformat()},
            "fit_detections": {"modis": r.modis_day + r.modis_night, "viirs": r.viirs_day + r.viirs_night},
            "terra_fit_period": {
                "start_date": self.terra_fit_start.isoformat(),
                "end_date": self.terra_fit_end.isoformat(),
            },
        }


def _clean(value: float | None) -> float | None:
    """Round to 4 decimals; NaN/None → None (JSON has no NaN)."""
    if value is None or math.isnan(value):
        return None
    return round(value, 4)


def fit_params(
    cursor: duckdb.DuckDBPyConnection, config: HarmonizationConfig, min_reliable_count: float | None = None
) -> HarmonizationParams:
    """Fit ratios and the Terra factor from the database.

    Args:
        cursor: DuckDB cursor.
        config: Fit periods.
        min_reliable_count: Reliable count from test 3 (None → config override
            or :data:`DEFAULT_MIN_RELIABLE_COUNT`).

    Returns:
        The fitted parameters.
    """
    ratios = fit_ratios(monthly_counts(cursor, config.fit_start, config.fit_end))
    factor, terra, aqua = terra_factor(monthly_counts(cursor, config.terra_fit_start, config.terra_fit_end))
    count = config.min_reliable_count or min_reliable_count or DEFAULT_MIN_RELIABLE_COUNT
    return HarmonizationParams(
        ratios=ratios,
        terra_factor=factor,
        terra_n=(terra, aqua),
        min_reliable_count=count,
        fit_start=config.fit_start,
        fit_end=config.fit_end,
        terra_fit_start=config.terra_fit_start,
        terra_fit_end=config.terra_fit_end,
        computed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


def save_params(connection: duckdb.DuckDBPyConnection, params: HarmonizationParams) -> None:
    """Replace the ``harmonization_params`` table with ``params``.

    Args:
        connection: Writable DuckDB connection.
        params: Fitted parameters.
    """
    r = params.ratios
    n_m, n_v = r.modis_day + r.modis_night, r.viirs_day + r.viirs_night
    fit = (params.fit_start, params.fit_end)
    terra_fit = (params.terra_fit_start, params.terra_fit_end)
    rows = [
        ("r_day", r.day, r.modis_day, r.viirs_day, *fit, "sum VIIRS_day / sum MODIS_day"),
        ("r_night", r.night, r.modis_night, r.viirs_night, *fit, "sum VIIRS_night / sum MODIS_night"),
        ("r_total", r.total, n_m, n_v, *fit, "sum VIIRS / sum MODIS (comparison only)"),
        ("k_frp", r.k_frp, n_m, n_v, *fit, "sum FRP_MODIS / sum FRP_VIIRS (check, ~1)"),
        ("terra_factor", params.terra_factor, params.terra_n[0], params.terra_n[1], *terra_fit,
         "sum (Terra+Aqua) / sum Terra; n_modis = Terra, n_viirs = Aqua"),
        ("min_reliable_count", params.min_reliable_count, None, None, *fit,
         "monthly count (MODIS units) from reliability test 3"),
    ]
    connection.execute(
        f"CREATE OR REPLACE TABLE {TABLE} (name VARCHAR PRIMARY KEY, value DOUBLE, n_modis BIGINT, "
        "n_viirs BIGINT, fit_start DATE, fit_end DATE, computed_at TIMESTAMP, note VARCHAR)"
    )
    connection.executemany(
        f"INSERT INTO {TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(n, v, a, b, s, e, params.computed_at, note) for n, v, a, b, s, e, note in rows],
    )


def load_params(cursor: duckdb.DuckDBPyConnection) -> HarmonizationParams | None:
    """Read the stored parameters, or None when the table does not exist.

    Args:
        cursor: DuckDB cursor (read-only is fine).

    Returns:
        The parameters or None.
    """
    exists = cursor.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [TABLE]
    ).fetchone()[0]
    if not exists:
        return None
    rows = {
        name: (value, n_m, n_v, start, end, computed)
        for name, value, n_m, n_v, start, end, computed in cursor.execute(
            f"SELECT name, value, n_modis, n_viirs, fit_start, fit_end, computed_at FROM {TABLE}"
        ).fetchall()
    }
    day, night, total = rows["r_day"], rows["r_night"], rows["r_total"]
    ratios = Ratios(
        day=day[0], night=night[0], total=total[0],
        modis_day=int(day[1]), modis_night=int(night[1]),
        viirs_day=int(day[2]), viirs_night=int(night[2]),
        months=0, k_frp=rows.get("k_frp", (None,))[0],
    )
    terra = rows["terra_factor"]
    return HarmonizationParams(
        ratios=ratios,
        terra_factor=terra[0],
        terra_n=(int(terra[1] or 0), int(terra[2] or 0)),
        min_reliable_count=rows.get("min_reliable_count", (DEFAULT_MIN_RELIABLE_COUNT,))[0],
        fit_start=day[3],
        fit_end=day[4],
        terra_fit_start=terra[3],
        terra_fit_end=terra[4],
        computed_at=day[5],
    )
