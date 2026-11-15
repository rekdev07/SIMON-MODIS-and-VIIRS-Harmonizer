"""MODIS/VIIRS count harmonization: the math, as pure functions (no database, no Flask).

Problem: VIIRS (375 m pixels) reports about 4 times more hotspots than MODIS
(1 km pixels) over the same fires. It splits one fire into more detections and
sees small fires MODIS misses. Total fire radiative power is almost the same,
so it is the same fire activity seen with a finer grid.

Method (ratio estimator, stratified by day/night)::

    r_day   = Σ VIIRS_day   / Σ MODIS_day        (sums over the fit period)
    r_night = Σ VIIRS_night / Σ MODIS_night
    MODIS_eq = VIIRS_day / r_day + VIIRS_night / r_night

MODIS = Terra + Aqua, VIIRS = Suomi-NPP only, vegetation fires only. A *ratio of
sums* (not a mean of monthly ratios) is used because months with few
detections give wild ratios (3 / 1 = 3, 1 / 3 = 0.33) that would dominate a
plain average; the ratio of sums weighs each month by its size.

Continuous series, all in "MODIS Terra+Aqua units" (see :func:`continuous_series`):

* before Aqua:            Terra × factor, factor = Σ(Terra+Aqua) / Σ Terra
* Aqua … VIIRS start:     MODIS as counted
* VIIRS start … MODIS end: average of MODIS and MODIS_eq(VIIRS)
* after MODIS:            MODIS_eq(VIIRS)

Nothing here is hard-coded: ratios and the Terra factor are always computed
from data with :func:`fit_ratios` and :func:`terra_factor`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date

#: Labels of the series sources (stable API codes).
SOURCE_TERRA_SCALED = "terra_scaled"
SOURCE_MODIS = "modis"
SOURCE_AVERAGE = "average"
SOURCE_VIIRS_EQ = "viirs_eq"


@dataclass(frozen=True)
class MonthCounts:
    """Detections of one area (or one box) in one month, split as the method needs.

    Attributes:
        month: First day of the month.
        terra_day, terra_night, aqua_day, aqua_night: MODIS counts per satellite and D/N.
        viirs_day, viirs_night: Suomi-NPP counts.
        box: Optional ``(lat_floor, lon_floor)`` of a 1° box (None for a whole area).
        frp_modis, frp_viirs: Sum of FRP (MW), used only for the ``k_frp`` check.
    """

    month: date
    terra_day: int = 0
    terra_night: int = 0
    aqua_day: int = 0
    aqua_night: int = 0
    viirs_day: int = 0
    viirs_night: int = 0
    box: tuple[int, int] | None = None
    frp_modis: float = 0.0
    frp_viirs: float = 0.0

    @property
    def terra(self) -> int:
        """Terra detections (day + night)."""
        return self.terra_day + self.terra_night

    @property
    def aqua(self) -> int:
        """Aqua detections (day + night)."""
        return self.aqua_day + self.aqua_night

    @property
    def modis_day(self) -> int:
        """MODIS (Terra + Aqua) daytime detections."""
        return self.terra_day + self.aqua_day

    @property
    def modis_night(self) -> int:
        """MODIS (Terra + Aqua) nighttime detections."""
        return self.terra_night + self.aqua_night

    @property
    def modis(self) -> int:
        """MODIS (Terra + Aqua) detections."""
        return self.terra + self.aqua

    @property
    def viirs(self) -> int:
        """VIIRS (Suomi-NPP) detections."""
        return self.viirs_day + self.viirs_night


@dataclass(frozen=True)
class Ratios:
    """Fitted VIIRS/MODIS ratios with the data they come from.

    Attributes:
        day: Σ VIIRS_day / Σ MODIS_day.
        night: Σ VIIRS_night / Σ MODIS_night.
        total: Σ VIIRS / Σ MODIS (single ratio, used only for comparison).
        modis_day, modis_night, viirs_day, viirs_night: Sums behind the ratios.
        months: Number of months used.
        k_frp: Σ FRP_MODIS / Σ FRP_VIIRS (≈ 1 means "same fire energy"); None if no FRP.
    """

    day: float
    night: float
    total: float
    modis_day: int
    modis_night: int
    viirs_day: int
    viirs_night: int
    months: int
    k_frp: float | None = None

    def as_dict(self) -> dict[str, float | int | None]:
        """Return the fields as a plain dict (for JSON and reports)."""
        return asdict(self)


def _ratio(numerator: float, denominator: float) -> float:
    """``numerator / denominator``, or NaN when the denominator is 0."""
    return numerator / denominator if denominator else math.nan


def fit_ratios(rows: Iterable[MonthCounts]) -> Ratios:
    """Fit the day, night and total ratios as ratios of sums.

    How: add up every row's counts, then divide. Rows can be months of a whole
    area or box-months; the result is the same either way (sums are additive),
    which is why the leave-one-out validation can subtract one month from the
    totals instead of re-reading the data.

    Args:
        rows: Counts over the fit period (MODIS and VIIRS must both be present).

    Returns:
        The fitted :class:`Ratios`. A ratio is NaN when its MODIS sum is 0.

    Example:
        >>> r = fit_ratios([MonthCounts(date(2013, 1, 1), terra_day=10, aqua_day=10,
        ...                              terra_night=2, viirs_day=80, viirs_night=16)])
        >>> (r.day, r.night, r.total)
        (4.0, 8.0, 4.363636363636363)
    """
    md = mn = vd = vn = 0
    frp_m = frp_v = 0.0
    months: set[date] = set()
    for row in rows:
        md += row.modis_day
        mn += row.modis_night
        vd += row.viirs_day
        vn += row.viirs_night
        frp_m += row.frp_modis
        frp_v += row.frp_viirs
        months.add(row.month)
    return Ratios(
        day=_ratio(vd, md),
        night=_ratio(vn, mn),
        total=_ratio(vd + vn, md + mn),
        modis_day=md,
        modis_night=mn,
        viirs_day=vd,
        viirs_night=vn,
        months=len(months),
        k_frp=_ratio(frp_m, frp_v) if frp_v else None,
    )


def modis_eq(viirs_day: float, viirs_night: float, ratios: Ratios) -> float:
    """Convert VIIRS counts into "MODIS-equivalent" counts.

    ``MODIS_eq = VIIRS_day / r_day + VIIRS_night / r_night``. Day and night are
    converted separately because the ratio differs a lot between them (night
    fires are small and cool, so MODIS misses relatively more of them).

    Args:
        viirs_day: VIIRS daytime detections.
        viirs_night: VIIRS nighttime detections.
        ratios: Fitted ratios.

    Returns:
        The MODIS-equivalent count (a real number, not an integer).
    """
    return viirs_day / ratios.day + viirs_night / ratios.night


def modis_eq_single(viirs: float, ratios: Ratios) -> float:
    """MODIS-equivalent with one single ratio (no day/night split), for comparison.

    Args:
        viirs: VIIRS detections.
        ratios: Fitted ratios (uses ``total``).

    Returns:
        ``viirs / r_total``.
    """
    return viirs / ratios.total


def terra_factor(rows: Iterable[MonthCounts]) -> tuple[float, int, int]:
    """Factor that turns a Terra-only count into a Terra + Aqua count.

    ``factor = Σ (Terra + Aqua) / Σ Terra`` over years when both satellites flew.
    Used for the months before Aqua (2000 to mid-2002).

    Args:
        rows: Counts over full years with both satellites.

    Returns:
        ``(factor, terra_sum, aqua_sum)``.
    """
    terra = aqua = 0
    for row in rows:
        terra += row.terra
        aqua += row.aqua
    return _ratio(terra + aqua, terra), terra, aqua


# --------------------------------------------------------------------------- #
# Continuous series
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Cutoffs:
    """Dates where the series changes source (configurable, never guessed from data).

    Why configurable: a month with 0 detections may simply mean "no fire", so
    the data cannot tell when a satellite started or stopped.

    Attributes:
        aqua_start: First month counted as full Terra + Aqua (inclusive).
        viirs_start: First month where VIIRS is averaged in (inclusive).
        modis_end: Last month with MODIS (inclusive); None = MODIS still flying.
    """

    aqua_start: date
    viirs_start: date
    modis_end: date | None = None


@dataclass(frozen=True)
class SeriesPoint:
    """One month of the harmonized series.

    Attributes:
        month: First day of the month.
        value: Harmonized count in MODIS Terra+Aqua units.
        source: One of the ``SOURCE_*`` codes.
        modis_eq: VIIRS converted to MODIS units (None when VIIRS is not used).
        counts: The raw counts of the month.
    """

    month: date
    value: float
    source: str
    modis_eq: float | None
    counts: MonthCounts = field(repr=False)


def choose_source(month: date, cutoffs: Cutoffs, has_modis: bool = True, has_viirs: bool = True) -> str:
    """Pick the source of a month from the cutoffs and from sensor availability.

    Args:
        month: First day of the month.
        cutoffs: Configured cutoffs.
        has_modis: Whether MODIS data covers this month (False after its last loaded day).
        has_viirs: Whether VIIRS data covers this month.

    Returns:
        A ``SOURCE_*`` code.
    """
    modis_flies = (cutoffs.modis_end is None or month <= cutoffs.modis_end) and has_modis
    viirs_flies = month >= cutoffs.viirs_start and has_viirs
    if month < cutoffs.aqua_start:
        return SOURCE_TERRA_SCALED
    if modis_flies and viirs_flies:
        return SOURCE_AVERAGE
    if viirs_flies:
        return SOURCE_VIIRS_EQ
    return SOURCE_MODIS


def harmonize_month(
    counts: MonthCounts, source: str, ratios: Ratios, factor: float
) -> SeriesPoint:
    """Compute the harmonized value of one month for a given source.

    Args:
        counts: Raw counts of the month.
        source: ``SOURCE_*`` code from :func:`choose_source`.
        ratios: Fitted VIIRS/MODIS ratios.
        factor: Terra → Terra+Aqua factor.

    Returns:
        The :class:`SeriesPoint`.
    """
    eq = modis_eq(counts.viirs_day, counts.viirs_night, ratios)
    if source == SOURCE_TERRA_SCALED:
        return SeriesPoint(counts.month, counts.terra * factor, source, None, counts)
    if source == SOURCE_MODIS:
        return SeriesPoint(counts.month, float(counts.modis), source, None, counts)
    if source == SOURCE_AVERAGE:
        return SeriesPoint(counts.month, (counts.modis + eq) / 2, source, eq, counts)
    return SeriesPoint(counts.month, eq, source, eq, counts)


def continuous_series(
    months: Sequence[MonthCounts],
    ratios: Ratios,
    factor: float,
    cutoffs: Cutoffs,
    availability: Callable[[date], tuple[bool, bool]] | None = None,
) -> list[SeriesPoint]:
    """Build the continuous monthly series in MODIS Terra+Aqua units.

    Args:
        months: One :class:`MonthCounts` per month (zeros included), in order.
        ratios: Fitted ratios.
        factor: Terra factor.
        cutoffs: Source cutoffs.
        availability: Optional ``month -> (has_modis, has_viirs)``; by default
            both sensors are assumed available.

    Returns:
        One :class:`SeriesPoint` per input month.
    """
    points = []
    for counts in months:
        has_modis, has_viirs = availability(counts.month) if availability else (True, True)
        source = choose_source(counts.month, cutoffs, has_modis, has_viirs)
        points.append(harmonize_month(counts, source, ratios, factor))
    return points


# --------------------------------------------------------------------------- #
# Error metrics and validation
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ErrorMetrics:
    """Errors of predicted vs actual counts.

    Attributes:
        n: Number of pairs.
        mape: Mean of ``|pred - actual| / actual`` over pairs with actual > 0 (fraction).
        wape: ``Σ |pred - actual| / Σ actual`` (fraction). Robust to tiny counts.
        r2: Coefficient of determination ``1 - SS_res / SS_tot`` (1 = perfect).
        bias: ``Σ pred / Σ actual - 1`` (fraction; > 0 means over-prediction).
    """

    n: int
    mape: float
    wape: float
    r2: float
    bias: float

    def as_dict(self) -> dict[str, float | int]:
        """Plain dict (for JSON and reports)."""
        return asdict(self)


def error_metrics(pairs: Iterable[tuple[float, float]]) -> ErrorMetrics:
    """Compute MAPE, WAPE, r² and bias of ``(actual, predicted)`` pairs.

    * MAPE averages the percentage error of each pair, so a box with 1 actual
      and 3 predicted (200 %) weighs as much as one with 1000 vs 1100 (10 %).
      Pairs with actual = 0 are skipped (the percentage is undefined).
    * WAPE divides the total absolute error by the total actual count, so big
      months weigh more. It is the fairer summary for counts.
    * r² = 1 − Σ(actual − pred)² / Σ(actual − mean)²: the share of the
      month-to-month variation that the prediction explains.

    Args:
        pairs: ``(actual, predicted)`` values.

    Returns:
        The :class:`ErrorMetrics` (NaN fields when undefined).
    """
    data = [(float(a), float(p)) for a, p in pairs if not (math.isnan(a) or math.isnan(p))]
    n = len(data)
    if n == 0:
        return ErrorMetrics(0, math.nan, math.nan, math.nan, math.nan)
    sum_actual = sum(a for a, _ in data)
    sum_pred = sum(p for _, p in data)
    abs_err = sum(abs(p - a) for a, p in data)
    pct = [abs(p - a) / a for a, p in data if a > 0]
    mean = sum_actual / n
    ss_tot = sum((a - mean) ** 2 for a, _ in data)
    ss_res = sum((a - p) ** 2 for a, p in data)
    return ErrorMetrics(
        n=n,
        mape=sum(pct) / len(pct) if pct else math.nan,
        wape=_ratio(abs_err, sum_actual),
        r2=1 - ss_res / ss_tot if ss_tot else math.nan,
        bias=_ratio(sum_pred, sum_actual) - 1 if sum_actual else math.nan,
    )


def _subtract(total: Ratios, removed: Ratios) -> Ratios:
    """Ratios of ``total`` minus the counts of ``removed`` (leave-one-out helper)."""
    md = total.modis_day - removed.modis_day
    mn = total.modis_night - removed.modis_night
    vd = total.viirs_day - removed.viirs_day
    vn = total.viirs_night - removed.viirs_night
    return Ratios(_ratio(vd, md), _ratio(vn, mn), _ratio(vd + vn, md + mn), md, mn, vd, vn,
                  total.months - removed.months)


def _by_month(rows: Iterable[MonthCounts]) -> dict[date, list[MonthCounts]]:
    """Group rows by month."""
    grouped: dict[date, list[MonthCounts]] = {}
    for row in rows:
        grouped.setdefault(row.month, []).append(row)
    return grouped


def cross_validate(
    rows: Sequence[MonthCounts],
    single_ratio: bool = False,
    group_ratios: Callable[[MonthCounts], str] | None = None,
) -> ErrorMetrics:
    """Leave-one-month-out validation: predict MODIS from VIIRS for unseen months.

    How: for every month M, fit the ratios with all the *other* months, convert
    month M's VIIRS counts with them, and compare with month M's real MODIS
    count. Each row is predicted separately, so passing national month rows
    gives the national error and passing 1° box-month rows gives the error per
    box (with ratios fitted on all boxes, as the calendar does).

    Args:
        rows: Month (or box-month) counts over a period where both sensors fly.
        single_ratio: Use one total ratio instead of day/night ratios.
        group_ratios: Optional ``row -> group name`` to fit one set of ratios
            per group (e.g. per region) instead of one national set.

    Returns:
        Error metrics over every predicted row.
    """
    groups: dict[str, list[MonthCounts]] = {}
    for row in rows:
        groups.setdefault(group_ratios(row) if group_ratios else "", []).append(row)

    pairs: list[tuple[float, float]] = []
    for group_rows in groups.values():
        total = fit_ratios(group_rows)
        for month_rows in _by_month(group_rows).values():
            loo = _subtract(total, fit_ratios(month_rows))
            for row in month_rows:
                if single_ratio:
                    pred = modis_eq_single(row.viirs, loo)
                else:
                    pred = modis_eq(row.viirs_day, row.viirs_night, loo)
                pairs.append((row.modis, pred))
    return error_metrics(pairs)


def predict_errors(rows: Sequence[MonthCounts], ratios: Ratios) -> ErrorMetrics:
    """Errors of predicting each row's MODIS count from its VIIRS with fixed ratios.

    Used for "fit with one year, predict another year".

    Args:
        rows: Rows to predict.
        ratios: Ratios fitted elsewhere.

    Returns:
        Error metrics.
    """
    return error_metrics((r.modis, modis_eq(r.viirs_day, r.viirs_night, ratios)) for r in rows)


def seasonal_check(rows: Iterable[MonthCounts], dry_months: frozenset[int]) -> tuple[Ratios, Ratios]:
    """Fit ratios separately for the dry (fire) season and the rest of the year.

    If both total ratios are close, one ratio for the whole year is enough.

    Args:
        rows: Counts over the fit period.
        dry_months: Calendar months (1–12) of the dry season.

    Returns:
        ``(dry_season_ratios, rest_ratios)``.
    """
    rows = list(rows)
    dry = [r for r in rows if r.month.month in dry_months]
    rest = [r for r in rows if r.month.month not in dry_months]
    return fit_ratios(dry), fit_ratios(rest)


def aggregate_by_month(rows: Iterable[MonthCounts]) -> list[MonthCounts]:
    """Add box-month rows up into one row per month (national totals).

    Args:
        rows: Box-month rows.

    Returns:
        One row per month, ordered by month, with ``box = None``.
    """
    totals: dict[date, list[float]] = {}
    for r in rows:
        acc = totals.setdefault(r.month, [0] * 8)
        for i, value in enumerate((r.terra_day, r.terra_night, r.aqua_day, r.aqua_night,
                                   r.viirs_day, r.viirs_night, r.frp_modis, r.frp_viirs)):
            acc[i] += value
    return [
        MonthCounts(m, int(a[0]), int(a[1]), int(a[2]), int(a[3]), int(a[4]), int(a[5]),
                    None, a[6], a[7])
        for m, a in sorted(totals.items())
    ]


def relative_change(value: float, reference: float) -> float:
    """``value / reference - 1`` (e.g. 0.08 = 8 % above the reference)."""
    return _ratio(value, reference) - 1


def month_starts(first: date, last: date) -> list[date]:
    """Every first-of-month from ``first``'s month to ``last``'s month, inclusive.

    Args:
        first: Any day of the first month.
        last: Any day of the last month.

    Returns:
        First days of the months, in order.

    Example:
        >>> month_starts(date(2013, 11, 5), date(2014, 1, 1))
        [datetime.date(2013, 11, 1), datetime.date(2013, 12, 1), datetime.date(2014, 1, 1)]
    """
    out, y, m = [], first.year, first.month
    while (y, m) <= (last.year, last.month):
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out
