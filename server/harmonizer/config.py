"""Harmonization settings (fit periods and source cutoffs) from environment variables.

Every date here is a *choice*, not a fact the data can reveal: a month with
zero detections may just mean "no fire". So they are configurable, with
defaults that match the FIRMS archive loaded for Mexico:

=================================  ============  ====================================================
Variable                           Default       Meaning
=================================  ============  ====================================================
``HARMONIZE_FIT_START``            2012-02-01    first day used to fit VIIRS/MODIS ratios
``HARMONIZE_FIT_END``              2025-12-31    last day used to fit the ratios
``HARMONIZE_TERRA_FIT_START``      2003-01-01    first day used to fit the Terra → Terra+Aqua factor
``HARMONIZE_TERRA_FIT_END``        2011-12-31    last day used for that factor (before VIIRS)
``HARMONIZE_AQUA_START``           2002-08-01    first month counted as full Terra + Aqua
``HARMONIZE_VIIRS_START``          2012-02-01    first month averaged with VIIRS (archive starts 2012-01-20)
``HARMONIZE_MODIS_END``            (empty)       last month with MODIS; empty = MODIS still flying
``HARMONIZE_DRY_MONTHS``           1,2,3,4,5     fire-season months, used by the seasonal check
``HARMONIZE_MIN_RELIABLE_COUNT``   (empty)       override of the fitted reliable monthly count
=================================  ============  ====================================================

The ratio fit period defaults to every full overlap year (see the reliability
report, test 1, for why the whole overlap is used instead of only 2013).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

#: Area (in square degrees) below which the calendar warns that the error grows.
#: 1 deg² is a box of ~110 km × ~105 km in Mexico, the size where the 1° box
#: validation was measured.
SMALL_AREA_DEG2 = 1.0

#: Side of the boxes used by the box-level validation, in degrees.
BOX_SIZE_DEG = 1.0


@dataclass(frozen=True)
class HarmonizationConfig:
    """Fit periods and cutoffs (see the module table).

    Attributes:
        fit_start, fit_end: Ratio fit period (inclusive).
        terra_fit_start, terra_fit_end: Terra factor fit period (inclusive).
        aqua_start, viirs_start: First month of each source (inclusive).
        modis_end: Last MODIS month, or None.
        dry_months: Calendar months of the fire season.
        min_reliable_count: Override for the reliable monthly count, or None
            to use the value fitted by ``scripts/harmonize.py fit``.
    """

    fit_start: date = date(2012, 2, 1)
    fit_end: date = date(2025, 12, 31)
    terra_fit_start: date = date(2003, 1, 1)
    terra_fit_end: date = date(2011, 12, 31)
    aqua_start: date = date(2002, 8, 1)
    viirs_start: date = date(2012, 2, 1)
    modis_end: date | None = None
    dry_months: frozenset[int] = frozenset({1, 2, 3, 4, 5})
    min_reliable_count: float | None = None


def _date(name: str, default: date | None) -> date | None:
    """Read an ISO date (``YYYY-MM-DD`` or ``YYYY-MM``) from the environment."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    if len(raw) == 7:
        raw += "-01"
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a date YYYY-MM-DD, got {raw!r}") from exc


def _month_start(value: date | None) -> date | None:
    """First day of ``value``'s month (cutoffs are whole months)."""
    return None if value is None else value.replace(day=1)


def load_config() -> HarmonizationConfig:
    """Build the configuration from ``HARMONIZE_*`` environment variables.

    Returns:
        The configuration (defaults for unset variables).

    Raises:
        ValueError: On a malformed value.
    """
    d = HarmonizationConfig()
    months_raw = os.getenv("HARMONIZE_DRY_MONTHS", "").strip()
    dry = frozenset(int(m) for m in months_raw.split(",") if m.strip()) if months_raw else d.dry_months
    if not dry or not all(1 <= m <= 12 for m in dry):
        raise ValueError("HARMONIZE_DRY_MONTHS must be a comma-separated list of months 1..12")
    min_count_raw = os.getenv("HARMONIZE_MIN_RELIABLE_COUNT", "").strip()
    return HarmonizationConfig(
        fit_start=_date("HARMONIZE_FIT_START", d.fit_start),  # type: ignore[arg-type]
        fit_end=_date("HARMONIZE_FIT_END", d.fit_end),  # type: ignore[arg-type]
        terra_fit_start=_date("HARMONIZE_TERRA_FIT_START", d.terra_fit_start),  # type: ignore[arg-type]
        terra_fit_end=_date("HARMONIZE_TERRA_FIT_END", d.terra_fit_end),  # type: ignore[arg-type]
        aqua_start=_month_start(_date("HARMONIZE_AQUA_START", d.aqua_start)),  # type: ignore[arg-type]
        viirs_start=_month_start(_date("HARMONIZE_VIIRS_START", d.viirs_start)),  # type: ignore[arg-type]
        modis_end=_month_start(_date("HARMONIZE_MODIS_END", None)),
        dry_months=dry,
        min_reliable_count=float(min_count_raw) if min_count_raw else None,
    )
