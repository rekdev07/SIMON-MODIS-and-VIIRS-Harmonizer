"""Validation report of the harmonization: ratios, cross-validation and 4 reliability tests.

Run it with ``python scripts/harmonize.py report`` (any period). It produces a
JSON-friendly dict; :func:`to_markdown` turns it into a readable report and
:func:`scatter_svg` draws the proportionality plot (test 3) without plotting
libraries.

Decision rule used everywhere: keep the simple method (one national set of
day/night ratios) unless a test shows a clear problem **and** the adjusted
version lowers the box-level cross-validation WAPE by at least
:data:`MIN_IMPROVEMENT` (3 percentage points).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

import duckdb

from harmonizer.config import BOX_SIZE_DEG, HarmonizationConfig
from harmonizer.data import monthly_counts
from harmonizer.method import (
    MonthCounts,
    Ratios,
    aggregate_by_month,
    cross_validate,
    error_metrics,
    fit_ratios,
    modis_eq,
    predict_errors,
    relative_change,
    seasonal_check,
    terra_factor,
)

#: Minimum drop in box-level WAPE (fraction) that justifies a more complex method.
MIN_IMPROVEMENT = 0.03
#: Tolerances of tests 1 and 2 (relative to the reference ratios).
YEAR_TOLERANCE = 0.10
REGION_TOLERANCE = 0.15
#: Box-month WAPE considered acceptable when choosing the reliable count (test 3).
RELIABLE_WAPE = 0.30
#: Largest |bias| of a size bin for the ratio to still hold there (test 3).
UNBIASED_TOLERANCE = 0.10
#: Size bins of test 3 (monthly count in MODIS units, lower edges).
SIZE_BINS = (0, 1, 3, 5, 10, 20, 50, 100, 300)
#: A box "normally has fire" in a calendar month when its median MODIS count is at least this.
NORMAL_FIRE_MEDIAN = 10


def region_of(row: MonthCounts) -> str:
    """Assign a 1° box to a broad region of Mexico (test 2).

    Boxes are labeled by their south-west corner: ``north`` (lat ≥ 24°),
    ``center`` (19°–24°), ``southeast`` (lat < 19°, lon ≥ −92°: Yucatán
    peninsula, Tabasco, eastern Chiapas) and ``south`` (the rest: Guerrero,
    Oaxaca, western Chiapas, Michoacán coast).

    Args:
        row: Box-month row.

    Returns:
        Region name.
    """
    lat, lon = row.box or (0, 0)
    if lat >= 24:
        return "north"
    if lat >= 19:
        return "center"
    return "southeast" if lon >= -92 else "south"


def _r(x: float | None, digits: int = 3) -> float | None:
    """Round for the report; NaN → None."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return round(x, digits)


def _ratios_dict(r: Ratios) -> dict[str, Any]:
    """Compact dict of a :class:`Ratios`."""
    return {
        "day": _r(r.day), "night": _r(r.night), "total": _r(r.total), "k_frp": _r(r.k_frp),
        "modis": r.modis_day + r.modis_night, "viirs": r.viirs_day + r.viirs_night,
        "night_share_modis": _r((r.modis_night / (r.modis_day + r.modis_night))
                                if r.modis_day + r.modis_night else math.nan),
        "months": r.months,
    }


def _metrics(m: Any) -> dict[str, Any]:
    """Compact dict of :class:`ErrorMetrics`."""
    return {"n": m.n, "mape": _r(m.mape), "wape": _r(m.wape), "r2": _r(m.r2), "bias": _r(m.bias)}


def _year_of(row: MonthCounts) -> str:
    return str(row.month.year)


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Pearson correlation (NaN when undefined)."""
    if len(xs) < 3:
        return math.nan
    try:
        return statistics.correlation(xs, ys)
    except statistics.StatisticsError:
        return math.nan


def check_stability(
    boxes: Sequence[MonthCounts], national: Sequence[MonthCounts], reference_year: int
) -> dict[str, Any]:
    """Test 1: are the ratios stable from year to year?

    Fits day/night/total ratios per year and compares them with the reference
    year (±10 %). Then compares three ways of using the ratios with the
    box-level error: fixed reference-year ratios on every other year, one
    pooled set over all years (leave-one-month-out), and one set per year.

    Args:
        boxes: Box-month rows over the overlap period.
        national: The same rows added up per month.
        reference_year: Year the original analysis used (2013).

    Returns:
        Per-year table, trend, cross-year predictions, CV comparison and decision.
    """
    years = sorted({r.month.year for r in national})
    ref = fit_ratios(r for r in national if r.month.year == reference_year)
    per_year = []
    for y in years:
        fy = fit_ratios(r for r in national if r.month.year == y)
        per_year.append({
            "year": y, **_ratios_dict(fy),
            "diff_day": _r(relative_change(fy.day, ref.day)),
            "diff_night": _r(relative_change(fy.night, ref.night)),
            "diff_total": _r(relative_change(fy.total, ref.total)),
        })
    max_abs = {k: max(abs(p[f"diff_{k}"] or 0) for p in per_year) for k in ("day", "night", "total")}
    trend = {k: _r(_pearson([p["year"] for p in per_year], [p[k] for p in per_year]))
             for k in ("day", "night", "total")}

    cross_year = []
    for y in years:
        if y == reference_year:
            continue
        cross_year.append({
            "fit_year": reference_year, "predict_year": y,
            "national": _metrics(predict_errors([r for r in national if r.month.year == y], ref)),
            "boxes": _metrics(predict_errors([r for r in boxes if r.month.year == y], ref)),
        })

    others = [r for r in boxes if r.month.year != reference_year]
    others_nat = [r for r in national if r.month.year != reference_year]
    variants = {
        "fixed_reference_year": {
            "boxes": _metrics(predict_errors(others, ref)),
            "national": _metrics(predict_errors(others_nat, ref)),
            "note": f"ratios of {reference_year} applied to every other year",
        },
        "pooled_all_years": {
            "boxes": _metrics(cross_validate(boxes)),
            "national": _metrics(cross_validate(national)),
            "note": "one set fitted on all overlap years, leave-one-month-out",
        },
        "per_year": {
            "boxes": _metrics(cross_validate(boxes, group_ratios=_year_of)),
            "national": _metrics(cross_validate(national, group_ratios=_year_of)),
            "note": "one set per year, leave-one-month-out within the year",
        },
    }
    simple = variants["pooled_all_years"]["boxes"]["wape"]
    adjusted = variants["per_year"]["boxes"]["wape"]
    improvement = simple - adjusted
    problem = any(v > YEAR_TOLERANCE for v in max_abs.values())
    decision = "adjusted (per-year ratios)" if problem and improvement >= MIN_IMPROVEMENT else "simple"
    return {
        "reference_year": reference_year,
        "reference": _ratios_dict(ref),
        "per_year": per_year,
        "max_abs_diff": {k: _r(v) for k, v in max_abs.items()},
        "trend_correlation_with_year": trend,
        "within_tolerance": not problem,
        "cross_year": cross_year,
        "cv_variants": variants,
        "wape_improvement_per_year_vs_pooled": _r(improvement),
        "decision": decision,
    }


def check_regions(boxes: Sequence[MonthCounts]) -> dict[str, Any]:
    """Test 2: do the ratios change by region?

    Args:
        boxes: Box-month rows over the overlap period.

    Returns:
        Ratios per region with their difference from the national ratios,
        CV with national vs regional ratios, and the decision.
    """
    national = fit_ratios(boxes)
    regions = []
    for name in ("north", "center", "south", "southeast"):
        rr = fit_ratios(r for r in boxes if region_of(r) == name)
        regions.append({
            "region": name, **_ratios_dict(rr),
            "diff_day": _r(relative_change(rr.day, national.day)),
            "diff_night": _r(relative_change(rr.night, national.night)),
            "diff_total": _r(relative_change(rr.total, national.total)),
        })
    max_abs = max(abs(v) for reg in regions for k in ("diff_day", "diff_night", "diff_total")
                  if (v := reg[k]) is not None)
    cv_national = cross_validate(boxes)
    cv_regional = cross_validate(boxes, group_ratios=region_of)
    improvement = cv_national.wape - cv_regional.wape
    problem = max_abs > REGION_TOLERANCE
    return {
        "national": _ratios_dict(national),
        "regions": regions,
        "max_abs_diff": _r(max_abs),
        "within_tolerance": not problem,
        "cv_boxes_national_ratios": _metrics(cv_national),
        "cv_boxes_regional_ratios": _metrics(cv_regional),
        "wape_improvement_regional_vs_national": _r(improvement),
        "decision": "adjusted (regional ratios)" if problem and improvement >= MIN_IMPROVEMENT else "simple",
        "region_rule": "north lat>=24; center 19-24; southeast lat<19 & lon>=-92; south the rest (1° box SW corner)",
    }


def _loo_predictions(boxes: Sequence[MonthCounts]) -> list[tuple[MonthCounts, float]]:
    """Leave-one-month-out MODIS_eq for every box-month (national ratios)."""
    total = fit_ratios(boxes)
    by_month: dict[date, list[MonthCounts]] = {}
    for r in boxes:
        by_month.setdefault(r.month, []).append(r)
    out = []
    for rows in by_month.values():
        m = fit_ratios(rows)
        md, mn = total.modis_day - m.modis_day, total.modis_night - m.modis_night
        vd, vn = total.viirs_day - m.viirs_day, total.viirs_night - m.viirs_night
        loo = Ratios(vd / md, vn / mn, (vd + vn) / (md + mn), md, mn, vd, vn, 0)
        out.extend((r, modis_eq(r.viirs_day, r.viirs_night, loo)) for r in rows)
    return out


def check_proportionality(boxes: Sequence[MonthCounts]) -> dict[str, Any]:
    """Test 3: is VIIRS proportional to MODIS, also at low counts?

    * Straight-line fit ``VIIRS = a + b · MODIS`` over box-months: a
      proportional relation has ``a`` close to 0 compared with typical counts.
    * Box-months are binned by size ``s = (MODIS + MODIS_eq) / 2`` (the mean of
      both sensors, so the bins do not favor either one; binning by MODIS alone
      would make low bins look biased just by chance, "regression to the mean").
      Per bin: Σ VIIRS / Σ MODIS and the cross-validated WAPE.
    * The reliable count is the lowest bin edge from which every larger bin
      has WAPE ≤ :data:`RELIABLE_WAPE`.

    Args:
        boxes: Box-month rows over the overlap period.

    Returns:
        Fit, bins, the reliable count and scatter points.
    """
    preds = _loo_predictions(boxes)
    xs = [float(r.modis) for r, _ in preds]
    ys = [float(r.viirs) for r, _ in preds]
    slope, intercept = statistics.linear_regression(xs, ys)
    through_origin = sum(x * y for x, y in zip(xs, ys)) / sum(x * x for x in xs)
    bins = []
    for i, low in enumerate(SIZE_BINS):
        high = SIZE_BINS[i + 1] if i + 1 < len(SIZE_BINS) else math.inf
        sel = [(r, p) for r, p in preds if low <= (r.modis + p) / 2 < high]
        if not sel:
            continue
        sm, sv = sum(r.modis for r, _ in sel), sum(r.viirs for r, _ in sel)
        m = error_metrics((r.modis, p) for r, p in sel)
        bins.append({"from": low, "to": None if high == math.inf else high, "n": len(sel),
                     "ratio": _r(sv / sm if sm else math.nan), "wape": _r(m.wape), "mape": _r(m.mape),
                     "bias": _r(m.bias)})
    reliable = unbiased = None
    for i, b in enumerate(bins):
        if reliable is None and all((x["wape"] or 0) <= RELIABLE_WAPE for x in bins[i:]):
            reliable = b["from"]
        if unbiased is None and all(abs(x["bias"] or 0) <= UNBIASED_TOLERANCE for x in bins[i:]):
            unbiased = b["from"]
    mean_y = statistics.fmean(ys)
    return {
        "n_box_months": len(xs),
        "linear_fit": {"slope": _r(slope), "intercept": _r(intercept),
                       "intercept_vs_mean_viirs": _r(intercept / mean_y if mean_y else math.nan),
                       "slope_through_origin": _r(through_origin)},
        "bins": bins,
        "reliable_wape_target": RELIABLE_WAPE,
        "min_reliable_count": reliable,
        "unbiased_tolerance": UNBIASED_TOLERANCE,
        "min_unbiased_count": unbiased,
        "points": [(r.modis, r.viirs) for r, _ in preds],
    }


def _month_iter(first: date, last: date) -> list[date]:
    """Every first-of-month from ``first`` to ``last`` (inclusive)."""
    out, y, m = [], first.year, first.month
    while (y, m) <= (last.year, last.month):
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def check_gaps(
    cursor: duckdb.DuckDBPyConnection, config: HarmonizationConfig, start: date, end: date
) -> dict[str, Any]:
    """Test 4: months with zero detections where fire was expected (clouds or missing data).

    * Days without a single detection in the whole database, per satellite
      (outages) and the longest runs.
    * Fire-season box-months with 0 detections in both sensors (0 MODIS before
      VIIRS) in boxes that *normally* burn that month (median MODIS count over
      the years ≥ :data:`NORMAL_FIRE_MEDIAN`). Only counted, never corrected.

    Args:
        cursor: DuckDB cursor.
        config: Settings (dry months, VIIRS start).
        start: First month analyzed.
        end: Last day analyzed.

    Returns:
        Outage runs and the zero box-month counts.
    """
    outages = {}
    for sat in ("Terra", "Aqua", "SNPP"):
        runs = cursor.execute(
            """
            WITH span AS (SELECT min(acq_date) a, max(acq_date) b FROM hotspots WHERE satellite = ?),
            days AS (SELECT CAST(g.d AS DATE) d FROM span, generate_series(span.a, span.b, INTERVAL 1 DAY) g(d)),
            missing AS (SELECT d FROM days WHERE d NOT IN (SELECT DISTINCT acq_date FROM hotspots WHERE satellite = ?)),
            grp AS (SELECT d, d - CAST(row_number() OVER (ORDER BY d) AS INTEGER) AS k FROM missing)
            SELECT min(d), max(d), count(*) FROM grp GROUP BY k ORDER BY count(*) DESC, min(d)
            """,
            [sat, sat],
        ).fetchall()
        outages[sat] = {"missing_days": sum(n for *_, n in runs),
                        "longest": [{"from": a.isoformat(), "to": b.isoformat(), "days": n} for a, b, n in runs[:5]]}

    rows = monthly_counts(cursor, start, end, by_box=True, box_size=BOX_SIZE_DEG)
    counts = {(r.box, r.month): r for r in rows}
    boxes = {r.box for r in rows}
    full_years = [y for y in range(start.year, end.year + 1) if date(y, 1, 1) >= start and date(y, 12, 31) <= end]
    normal: dict[tuple[Any, int], float] = {}
    for box in boxes:
        for m in config.dry_months:
            vals = [counts[(box, date(y, m, 1))].modis if (box, date(y, m, 1)) in counts else 0
                    for y in full_years]
            normal[(box, m)] = statistics.median(vals) if vals else 0
    eligible = zero = 0
    examples = []
    for month in _month_iter(start, end):
        if month.month not in config.dry_months:
            continue
        for box in boxes:
            if normal[(box, month.month)] < NORMAL_FIRE_MEDIAN:
                continue
            eligible += 1
            r = counts.get((box, month))
            both = (r.modis if r else 0) + ((r.viirs if r else 0) if month >= config.viirs_start else 0)
            if both == 0:
                zero += 1
                examples.append({"month": month.isoformat()[:7], "box_lat": box[0], "box_lon": box[1],
                                 "normal_median": normal[(box, month.month)]})
    return {
        "outages": outages,
        "fire_season_months": sorted(config.dry_months),
        "normal_fire_median_threshold": NORMAL_FIRE_MEDIAN,
        "eligible_box_months": eligible,
        "zero_box_months": zero,
        "zero_share": _r(zero / eligible if eligible else math.nan, 4),
        "examples": examples[:20],
    }


def build_report(
    cursor: duckdb.DuckDBPyConnection,
    config: HarmonizationConfig,
    start: date | None = None,
    end: date | None = None,
    reference_year: int = 2013,
    progress: Callable[[str], None] = lambda _msg: None,
) -> dict[str, Any]:
    """Run every check for the overlap period ``start..end`` (defaults: fit period).

    Args:
        cursor: DuckDB cursor.
        config: Harmonization settings.
        start: First day of the analyzed overlap period.
        end: Last day.
        reference_year: Year used as reference in test 1 (must be inside the period).
        progress: Callback for progress messages.

    Returns:
        The report as a dict (see :func:`to_markdown`).
    """
    start = start or config.fit_start
    end = end or config.fit_end
    progress("Counting box-months ...")
    boxes = monthly_counts(cursor, start, end, by_box=True, box_size=BOX_SIZE_DEG)
    national = aggregate_by_month(boxes)
    ratios = fit_ratios(national)
    dry, rest = seasonal_check(national, config.dry_months)

    def season(row: MonthCounts) -> str:
        return "dry" if row.month.month in config.dry_months else "rest"

    cv_boxes = cross_validate(boxes)
    cv_season = cross_validate(boxes, group_ratios=season)
    factor, terra, aqua = terra_factor(monthly_counts(cursor, config.terra_fit_start, config.terra_fit_end))
    progress("Test 1 (stability) ...")
    t1 = check_stability(boxes, national, reference_year) if any(
        r.month.year == reference_year for r in national) else None
    progress("Test 2 (regions) ...")
    t2 = check_regions(boxes)
    progress("Test 3 (proportionality) ...")
    t3 = check_proportionality(boxes)
    progress("Test 4 (gaps) ...")
    t4 = check_gaps(cursor, config, date(config.aqua_start.year + 1, 1, 1), end)
    return {
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "ratios": _ratios_dict(ratios),
        "terra_factor": {"value": _r(factor), "terra": terra, "aqua": aqua,
                         "period": [config.terra_fit_start.isoformat(), config.terra_fit_end.isoformat()]},
        "seasonal": {
            "dry_months": sorted(config.dry_months), "dry": _ratios_dict(dry), "rest": _ratios_dict(rest),
            "cv_boxes_one_set": _metrics(cv_boxes), "cv_boxes_per_season": _metrics(cv_season),
            "wape_improvement": _r(cv_boxes.wape - cv_season.wape),
            "decision": "adjusted (per-season ratios)" if cv_boxes.wape - cv_season.wape >= MIN_IMPROVEMENT
            else "simple",
        },
        "cross_validation": {
            "national_day_night": _metrics(cross_validate(national)),
            "national_single_ratio": _metrics(cross_validate(national, single_ratio=True)),
            "boxes_day_night": _metrics(cv_boxes),
            "boxes_single_ratio": _metrics(cross_validate(boxes, single_ratio=True)),
            "box_size_deg": BOX_SIZE_DEG,
        },
        "test1_stability": t1,
        "test2_regions": t2,
        "test3_proportionality": t3,
        "test4_gaps": t4,
    }


# --------------------------------------------------------------------------- #
# Output: markdown and SVG
# --------------------------------------------------------------------------- #


def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x * 100:.1f}%"


def _signed_pct(x: float | None) -> str:
    return "–" if x is None else f"{x * 100:+.1f}%"


def to_markdown(report: dict[str, Any], scatter_file: str | None = None) -> str:
    """Render the report as Markdown.

    Args:
        report: Output of :func:`build_report`.
        scatter_file: Relative path of the scatter SVG to link, if any.

    Returns:
        Markdown text.
    """
    p, r, cv = report["period"], report["ratios"], report["cross_validation"]
    out = [
        "# Harmonization validation report",
        "",
        f"Overlap period analyzed: **{p['start_date']} → {p['end_date']}** "
        "(MODIS = Terra + Aqua, VIIRS = Suomi-NPP, vegetation fires `type = 0`).",
        "",
        "## Ratios (ratio of sums)",
        "",
        "| ratio | value | MODIS detections | VIIRS detections |",
        "|---|---|---|---|",
        f"| day | {r['day']} | | |",
        f"| night | {r['night']} | | |",
        f"| total | {r['total']} | {r['modis']:,} | {r['viirs']:,} |",
        "",
        f"k_FRP = ΣFRP_MODIS / ΣFRP_VIIRS = **{r['k_frp']}**. "
        f"Terra factor (Terra+Aqua)/Terra = **{report['terra_factor']['value']}** "
        f"({report['terra_factor']['period'][0]} → {report['terra_factor']['period'][1]}).",
        "",
        f"Seasonal check (dry months {report['seasonal']['dry_months']}): total ratio "
        f"dry **{report['seasonal']['dry']['total']}** vs rest **{report['seasonal']['rest']['total']}** "
        f"(day {report['seasonal']['dry']['day']} vs {report['seasonal']['rest']['day']}, "
        f"night {report['seasonal']['dry']['night']} vs {report['seasonal']['rest']['night']}). "
        f"Box CV WAPE one set {_pct(report['seasonal']['cv_boxes_one_set']['wape'])} vs per season "
        f"{_pct(report['seasonal']['cv_boxes_per_season']['wape'])}: **{report['seasonal']['decision']}**.",
        "",
        "## Leave-one-month-out cross-validation",
        "",
        "| level | ratios | MAPE | WAPE | r² | n |",
        "|---|---|---|---|---|---|",
    ]
    for key, level, kind in (("national_day_night", "national", "day/night"),
                             ("national_single_ratio", "national", "single"),
                             ("boxes_day_night", f"{cv['box_size_deg']}° boxes", "day/night"),
                             ("boxes_single_ratio", f"{cv['box_size_deg']}° boxes", "single")):
        m = cv[key]
        out.append(f"| {level} | {kind} | {_pct(m['mape'])} | {_pct(m['wape'])} | {m['r2']} | {m['n']} |")
    out += ["", "MAPE over box-months is dominated by tiny counts (1 vs 3 = 200 %); WAPE is the fair summary.", ""]

    t1 = report.get("test1_stability")
    if t1:
        out += [
            f"## Test 1: stability over time (reference {t1['reference_year']})", "",
            "| year | day | night | total | Δday | Δnight | Δtotal | k_FRP | MODIS |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for y in t1["per_year"]:
            out.append(f"| {y['year']} | {y['day']} | {y['night']} | {y['total']} | {_signed_pct(y['diff_day'])} | "
                       f"{_signed_pct(y['diff_night'])} | {_signed_pct(y['diff_total'])} | {y['k_frp']} | {y['modis']:,} |")
        tr = t1["trend_correlation_with_year"]
        out += ["", f"Largest |Δ| vs {t1['reference_year']}: day {_pct(t1['max_abs_diff']['day'])}, "
                f"night {_pct(t1['max_abs_diff']['night'])}, total {_pct(t1['max_abs_diff']['total'])}. "
                f"Correlation with year: day {tr['day']}, night {tr['night']}, total {tr['total']}.", "",
                f"Fit with {t1['reference_year']}, predict another year:", "",
                "| predicted year | national MAPE | national WAPE | box WAPE | box r² |", "|---|---|---|---|---|"]
        for c in t1["cross_year"]:
            out.append(f"| {c['predict_year']} | {_pct(c['national']['mape'])} | {_pct(c['national']['wape'])} | "
                       f"{_pct(c['boxes']['wape'])} | {c['boxes']['r2']} |")
        out += ["", "| variant | box WAPE | box r² | national MAPE | national WAPE |", "|---|---|---|---|---|"]
        for name, v in t1["cv_variants"].items():
            out.append(f"| {name} ({v['note']}) | {_pct(v['boxes']['wape'])} | {v['boxes']['r2']} | "
                       f"{_pct(v['national']['mape'])} | {_pct(v['national']['wape'])} |")
        out += ["", f"Per-year vs pooled box WAPE improvement: {_pct(t1['wape_improvement_per_year_vs_pooled'])}. "
                f"**Decision: {t1['decision']}.**", ""]

    t2 = report["test2_regions"]
    out += ["## Test 2: regions", "", f"Rule: {t2['region_rule']}.", "",
            "| region | day | night | total | Δday | Δnight | Δtotal | MODIS |", "|---|---|---|---|---|---|---|---|"]
    for g in t2["regions"]:
        out.append(f"| {g['region']} | {g['day']} | {g['night']} | {g['total']} | {_signed_pct(g['diff_day'])} | "
                   f"{_signed_pct(g['diff_night'])} | {_signed_pct(g['diff_total'])} | {g['modis']:,} |")
    out += ["", f"Box CV WAPE national ratios {_pct(t2['cv_boxes_national_ratios']['wape'])} vs regional "
            f"{_pct(t2['cv_boxes_regional_ratios']['wape'])} (improvement "
            f"{_pct(t2['wape_improvement_regional_vs_national'])}). **Decision: {t2['decision']}.**", ""]

    t3 = report["test3_proportionality"]
    lf = t3["linear_fit"]
    out += ["## Test 3: proportionality (box-months)", ""]
    if scatter_file:
        out += [f"![MODIS vs VIIRS per box-month]({scatter_file})", ""]
    out += [f"{t3['n_box_months']:,} box-months. Line VIIRS = {lf['intercept']} + {lf['slope']} · MODIS "
            f"(intercept = {_pct(lf['intercept_vs_mean_viirs'])} of the mean VIIRS count; "
            f"slope through origin {lf['slope_through_origin']}).", "",
            "| size (MODIS units) | box-months | ΣVIIRS/ΣMODIS | WAPE | MAPE | bias |", "|---|---|---|---|---|---|"]
    for b in t3["bins"]:
        rng = f"{b['from']}–{b['to']}" if b["to"] is not None else f"≥ {b['from']}"
        out.append(f"| {rng} | {b['n']:,} | {b['ratio']} | {_pct(b['wape'])} | {_pct(b['mape'])} | "
                   f"{_signed_pct(b['bias'])} |")
    out += ["", f"Minimum reliable monthly count (every larger bin has WAPE ≤ {_pct(t3['reliable_wape_target'])}): "
            f"**{t3['min_reliable_count']}**. Smallest count from which every bin has |bias| ≤ "
            f"{_pct(t3['unbiased_tolerance'])} (the ratio itself holds): **{t3['min_unbiased_count']}**.", ""]

    t4 = report["test4_gaps"]
    out += ["## Test 4: gaps (clouds or missing data)", "", "| satellite | days without any detection | longest runs |",
            "|---|---|---|"]
    for sat, o in t4["outages"].items():
        runs = ", ".join(f"{x['from']}→{x['to']} ({x['days']} d)" for x in o["longest"][:3])
        out.append(f"| {sat} | {o['missing_days']} | {runs} |")
    out += ["", f"Fire-season box-months (months {t4['fire_season_months']}) in boxes whose median MODIS count is "
            f"≥ {t4['normal_fire_median_threshold']}: **{t4['eligible_box_months']}**; with 0 detections in both "
            f"sensors: **{t4['zero_box_months']}** ({_pct(t4['zero_share'])}). Not corrected; reported as a limitation.", ""]
    if t4["examples"]:
        out += ["Examples: " + ", ".join(f"{e['month']} box ({e['box_lat']}, {e['box_lon']}) median {e['normal_median']}"
                                          for e in t4["examples"][:10]), ""]
    return "\n".join(out)


def scatter_svg(points: Sequence[tuple[float, float]], slope: float, title: str) -> str:
    """Draw MODIS (x) vs VIIRS (y) per box-month on log(1 + count) axes, as SVG.

    Log axes because counts span 0 to thousands; ``1 +`` keeps zeros visible.
    The dashed line is ``VIIRS = slope · MODIS`` (proportional, through zero).

    Args:
        points: ``(modis, viirs)`` pairs.
        slope: Total ratio for the reference line.
        title: Plot title.

    Returns:
        SVG document text.
    """
    w, h, m = 640, 520, 60
    max_v = max(max(x for x, _ in points), max(y for _, y in points), 1)
    top = math.log10(1 + max_v)

    def sx(v: float) -> float:
        return m + (w - 2 * m) * math.log10(1 + v) / top

    def sy(v: float) -> float:
        return h - m - (h - 2 * m) * math.log10(1 + v) / top

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif" font-size="12">',
             f'<rect width="{w}" height="{h}" fill="white"/>',
             f'<text x="{w / 2}" y="24" text-anchor="middle" font-size="14" font-weight="bold">{title}</text>']
    for v in [0] + [10 ** k for k in range(0, int(math.log10(max_v)) + 1)]:
        parts.append(f'<line x1="{sx(v):.1f}" y1="{m}" x2="{sx(v):.1f}" y2="{h - m}" stroke="#eee"/>')
        parts.append(f'<line x1="{m}" y1="{sy(v):.1f}" x2="{w - m}" y2="{sy(v):.1f}" stroke="#eee"/>')
        parts.append(f'<text x="{sx(v):.1f}" y="{h - m + 16}" text-anchor="middle">{v:,}</text>')
        parts.append(f'<text x="{m - 6}" y="{sy(v) + 4:.1f}" text-anchor="end">{v:,}</text>')
    parts.append(f'<line x1="{m}" y1="{h - m}" x2="{w - m}" y2="{h - m}" stroke="#333"/>')
    parts.append(f'<line x1="{m}" y1="{m}" x2="{m}" y2="{h - m}" stroke="#333"/>')
    for x, y in points:
        parts.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="1.6" fill="#d95f02" fill-opacity="0.25"/>')
    xs = [0.0] + [10 ** (i / 20) for i in range(0, int(20 * math.log10(max_v / slope)) + 1)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(slope * x):.1f}" for i, x in enumerate(xs))
    parts.append(f'<path d="{path}" stroke="#1b4f9c" stroke-width="2" stroke-dasharray="6 4" fill="none"/>')
    parts.append(f'<text x="{w - m}" y="{m + 14}" text-anchor="end" fill="#1b4f9c">VIIRS = {slope:.2f} × MODIS</text>')
    parts.append(f'<text x="{w / 2}" y="{h - 18}" text-anchor="middle">MODIS detections per 1° box-month (log 1+x)</text>')
    parts.append(f'<text x="18" y="{h / 2}" text-anchor="middle" transform="rotate(-90 18 {h / 2})">'
                 'VIIRS detections per 1° box-month (log 1+x)</text>')
    parts.append("</svg>")
    return "\n".join(parts)
