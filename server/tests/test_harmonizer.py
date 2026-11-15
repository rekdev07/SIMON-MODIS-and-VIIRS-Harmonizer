"""Tests of the harmonization math (``harmonizer.method``) with synthetic data of known ratios.

The synthetic world: every month has a true fire activity ``A``. MODIS Terra
sees ``0.45 · A`` and Aqua ``0.55 · A`` (so the Terra factor is 1 / 0.45);
VIIRS sees ``r_day`` times the MODIS daytime count and ``r_night`` times the
nighttime count. Counts are drawn as Poisson numbers, so the fit must recover
the ratios through the noise.
"""

from __future__ import annotations

import math
import random
from datetime import date

import pytest

from harmonizer.method import (
    SOURCE_AVERAGE,
    SOURCE_MODIS,
    SOURCE_TERRA_SCALED,
    SOURCE_VIIRS_EQ,
    Cutoffs,
    MonthCounts,
    aggregate_by_month,
    choose_source,
    continuous_series,
    cross_validate,
    error_metrics,
    fit_ratios,
    modis_eq,
    seasonal_check,
    terra_factor,
)

R_DAY, R_NIGHT = 3.7, 8.0
TERRA_SHARE = 0.45
NIGHT_SHARE = 0.17
CUTOFFS = Cutoffs(aqua_start=date(2002, 8, 1), viirs_start=date(2012, 2, 1), modis_end=date(2027, 12, 1))


def _poisson(rng: random.Random, lam: float) -> int:
    """Poisson draw (normal approximation for large means, Knuth for small ones)."""
    if lam > 50:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _months(first: date, last: date) -> list[date]:
    out, y, m = [], first.year, first.month
    while (y, m) <= (last.year, last.month):
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def synthetic(month: date, activity: float, rng: random.Random, box: tuple[int, int] | None = None,
              terra: bool = True, aqua: bool = True, viirs: bool = True) -> MonthCounts:
    """One month of synthetic counts for a true activity (in MODIS Terra+Aqua units)."""
    day, night = activity * (1 - NIGHT_SHARE), activity * NIGHT_SHARE
    return MonthCounts(
        month=month,
        terra_day=_poisson(rng, TERRA_SHARE * day) if terra else 0,
        terra_night=_poisson(rng, TERRA_SHARE * night) if terra else 0,
        aqua_day=_poisson(rng, (1 - TERRA_SHARE) * day) if aqua else 0,
        aqua_night=_poisson(rng, (1 - TERRA_SHARE) * night) if aqua else 0,
        viirs_day=_poisson(rng, R_DAY * day) if viirs else 0,
        viirs_night=_poisson(rng, R_NIGHT * night) if viirs else 0,
        box=box,
    )


def seasonal_activity(month: date, peak: float = 3000.0) -> float:
    """A smooth fire season peaking in April-May, as in Mexico."""
    return peak * (0.1 + 0.9 * math.exp(-((month.month - 4.5) ** 2) / 2))


def test_fit_recovers_known_ratios() -> None:
    rng = random.Random(1)
    rows = [synthetic(m, seasonal_activity(m), rng) for m in _months(date(2013, 1, 1), date(2015, 12, 1))]
    ratios = fit_ratios(rows)
    assert ratios.day == pytest.approx(R_DAY, rel=0.02)
    assert ratios.night == pytest.approx(R_NIGHT, rel=0.03)
    expected_total = (R_DAY * (1 - NIGHT_SHARE) + R_NIGHT * NIGHT_SHARE)
    assert ratios.total == pytest.approx(expected_total, rel=0.02)
    assert ratios.months == 36


def test_ratio_of_sums_is_not_mean_of_ratios() -> None:
    rows = [
        MonthCounts(date(2013, 1, 1), terra_day=1, viirs_day=3),      # ratio 3
        MonthCounts(date(2013, 2, 1), terra_day=100, viirs_day=400),  # ratio 4
    ]
    assert fit_ratios(rows).day == pytest.approx(403 / 101)  # dominated by the big month, not (3 + 4) / 2


def test_modis_eq_divides_day_and_night_separately() -> None:
    ratios = fit_ratios([MonthCounts(date(2013, 1, 1), terra_day=10, terra_night=2, viirs_day=40, viirs_night=16)])
    assert (ratios.day, ratios.night) == (4.0, 8.0)
    assert modis_eq(80, 8, ratios) == pytest.approx(80 / 4 + 8 / 8)


def test_terra_factor_recovers_known_share() -> None:
    rng = random.Random(2)
    rows = [synthetic(m, seasonal_activity(m), rng, viirs=False) for m in _months(date(2003, 1, 1), date(2011, 12, 1))]
    factor, terra, aqua = terra_factor(rows)
    assert factor == pytest.approx(1 / TERRA_SHARE, rel=0.01)
    assert terra > 0 and aqua > terra


def test_cross_validation_is_perfect_without_noise() -> None:
    rows = [MonthCounts(date(2013, m, 1), terra_day=10 * m, terra_night=m, viirs_day=37 * m, viirs_night=8 * m)
            for m in range(1, 13)]
    metrics = cross_validate(rows)
    assert metrics.wape == pytest.approx(0, abs=1e-12)
    assert metrics.r2 == pytest.approx(1)


def test_cross_validation_boxes_has_larger_error_than_national() -> None:
    rng = random.Random(3)
    boxes = [synthetic(m, seasonal_activity(m, peak=60), rng, box=(b, 0))
             for m in _months(date(2013, 1, 1), date(2014, 12, 1)) for b in range(10)]
    national = aggregate_by_month(boxes)
    assert cross_validate(national).wape < cross_validate(boxes).wape
    assert fit_ratios(national).day == pytest.approx(fit_ratios(boxes).day)


def test_seasonal_check_finds_equal_ratios() -> None:
    rng = random.Random(4)
    rows = [synthetic(m, seasonal_activity(m), rng) for m in _months(date(2013, 1, 1), date(2016, 12, 1))]
    dry, rest = seasonal_check(rows, frozenset({1, 2, 3, 4, 5}))
    assert dry.total == pytest.approx(rest.total, rel=0.05)


def test_error_metrics_by_hand() -> None:
    m = error_metrics([(10, 12), (20, 18), (0, 1)])
    assert m.n == 3
    assert m.mape == pytest.approx((0.2 + 0.1) / 2)       # actual 0 is skipped
    assert m.wape == pytest.approx((2 + 2 + 1) / 30)
    assert m.bias == pytest.approx(31 / 30 - 1)
    # mean actual = 10 → SS_tot = 0 + 100 + 100; SS_res = 4 + 4 + 1
    assert m.r2 == pytest.approx(1 - 9 / 200)


@pytest.mark.parametrize(
    ("month", "has", "expected"),
    [
        (date(2001, 5, 1), (True, False), SOURCE_TERRA_SCALED),
        (date(2002, 7, 1), (True, False), SOURCE_TERRA_SCALED),
        (date(2002, 8, 1), (True, False), SOURCE_MODIS),
        (date(2012, 1, 1), (True, True), SOURCE_MODIS),
        (date(2012, 2, 1), (True, True), SOURCE_AVERAGE),
        (date(2020, 2, 1), (True, False), SOURCE_MODIS),      # VIIRS data missing that month
        (date(2020, 2, 1), (False, True), SOURCE_VIIRS_EQ),   # MODIS data missing that month
        (date(2028, 1, 1), (True, True), SOURCE_VIIRS_EQ),    # after the configured MODIS end
    ],
)
def test_choose_source(month: date, has: tuple[bool, bool], expected: str) -> None:
    assert choose_source(month, CUTOFFS, *has) == expected


def _year_mean(points: list, year: int, months: range) -> float:
    vals = [p.value for p in points if p.month.year == year and p.month.month in months]
    return sum(vals) / len(vals)


def test_series_has_no_artificial_jumps_in_2002_and_2012() -> None:
    """Constant true activity must give a flat harmonized series across both cutoffs."""
    rng = random.Random(5)
    activity = 2000.0
    months = []
    for m in _months(date(2000, 11, 1), date(2027, 12, 1)):
        months.append(synthetic(m, activity, rng, aqua=m >= date(2002, 7, 4), viirs=m >= date(2012, 2, 1)))
    fit = fit_ratios(r for r in months if date(2012, 2, 1) <= r.month <= date(2025, 12, 1))
    factor, _, _ = terra_factor(r for r in months if date(2003, 1, 1) <= r.month <= date(2011, 12, 1))
    points = continuous_series(months, fit, factor, CUTOFFS)

    # Every month, whatever its source, is close to the true activity...
    for p in points:
        assert p.value == pytest.approx(activity, rel=0.08), (p.month, p.source)
    # ...and the averages just before/after each cutoff match (no step).
    before_2002 = [p.value for p in points if date(2001, 8, 1) <= p.month < date(2002, 7, 1)]
    after_2002 = [p.value for p in points if date(2002, 8, 1) <= p.month < date(2003, 7, 1)]
    before_2012 = [p.value for p in points if date(2011, 2, 1) <= p.month < date(2012, 2, 1)]
    after_2012 = [p.value for p in points if date(2012, 2, 1) <= p.month < date(2013, 2, 1)]
    for a, b in ((before_2002, after_2002), (before_2012, after_2012)):
        assert sum(a) / len(a) == pytest.approx(sum(b) / len(b), rel=0.02)
    assert {p.source for p in points} == {SOURCE_TERRA_SCALED, SOURCE_MODIS, SOURCE_AVERAGE}


def test_series_after_modis_end_uses_viirs_eq_without_jump() -> None:
    rng = random.Random(6)
    cutoffs = Cutoffs(date(2002, 8, 1), date(2012, 2, 1), modis_end=date(2020, 12, 1))
    months = [synthetic(m, 1500.0, rng) for m in _months(date(2019, 1, 1), date(2022, 12, 1))]
    fit = fit_ratios(r for r in months if r.month.year < 2021)
    points = continuous_series(months, fit, 2.2, cutoffs)
    assert points[-1].source == SOURCE_VIIRS_EQ
    assert _year_mean(points, 2020, range(1, 13)) == pytest.approx(_year_mean(points, 2021, range(1, 13)), rel=0.02)
