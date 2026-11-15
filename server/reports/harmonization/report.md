# Harmonization validation report

Overlap period analyzed: **2012-02-01 → 2025-12-31** (MODIS = Terra + Aqua, VIIRS = Suomi-NPP, vegetation fires `type = 0`).

## Ratios (ratio of sums)

| ratio | value | MODIS detections | VIIRS detections |
|---|---|---|---|
| day | 3.823 | | |
| night | 7.266 | | |
| total | 4.335 | 860,138 | 3,728,921 |

k_FRP = ΣFRP_MODIS / ΣFRP_VIIRS = **0.919**. Terra factor (Terra+Aqua)/Terra = **2.223** (2003-01-01 → 2011-12-31).

Seasonal check (dry months [1, 2, 3, 4, 5]): total ratio dry **4.233** vs rest **4.776** (day 3.719 vs 4.273, night 7.186 vs 7.601). Box CV WAPE one set 27.5% vs per season 27.0%: **simple**.

## Leave-one-month-out cross-validation

| level | ratios | MAPE | WAPE | r² | n |
|---|---|---|---|---|---|
| national | day/night | 11.5% | 9.1% | 0.987 | 167 |
| national | single | 11.4% | 8.8% | 0.987 | 167 |
| 1.0° boxes | day/night | 65.8% | 27.5% | 0.93 | 31816 |
| 1.0° boxes | single | 65.8% | 29.4% | 0.908 | 31816 |

MAPE over box-months is dominated by tiny counts (1 vs 3 = 200 %); WAPE is the fair summary.

## Test 1: stability over time (reference 2013)

| year | day | night | total | Δday | Δnight | Δtotal | k_FRP | MODIS |
|---|---|---|---|---|---|---|---|---|
| 2012 | 3.916 | 9.016 | 4.614 | +6.1% | +11.9% | +8.7% | 0.909 | 60,110 |
| 2013 | 3.692 | 8.058 | 4.246 | +0.0% | +0.0% | +0.0% | 0.954 | 76,878 |
| 2014 | 3.899 | 8.389 | 4.226 | +5.6% | +4.1% | -0.5% | 0.87 | 36,243 |
| 2015 | 3.759 | 7.746 | 4.002 | +1.8% | -3.9% | -5.8% | 0.882 | 50,110 |
| 2016 | 3.838 | 8.892 | 4.372 | +4.0% | +10.4% | +3.0% | 0.87 | 59,233 |
| 2017 | 3.801 | 8.384 | 4.481 | +3.0% | +4.0% | +5.5% | 0.936 | 78,062 |
| 2018 | 3.968 | 8.771 | 4.568 | +7.5% | +8.9% | +7.6% | 0.872 | 56,023 |
| 2019 | 3.758 | 7.178 | 4.303 | +1.8% | -10.9% | +1.3% | 0.959 | 80,680 |
| 2020 | 3.8 | 6.941 | 4.205 | +2.9% | -13.9% | -1.0% | 0.936 | 60,699 |
| 2021 | 3.692 | 7.671 | 4.351 | +0.0% | -4.8% | +2.5% | 0.933 | 58,029 |
| 2022 | 4.041 | 7.064 | 4.505 | +9.5% | -12.3% | +6.1% | 0.829 | 52,362 |
| 2023 | 3.957 | 6.192 | 4.367 | +7.2% | -23.2% | +2.9% | 0.901 | 65,524 |
| 2024 | 3.63 | 5.512 | 4.079 | -1.7% | -31.6% | -4.0% | 0.997 | 71,872 |
| 2025 | 3.91 | 5.942 | 4.358 | +5.9% | -26.3% | +2.6% | 0.951 | 54,313 |

Largest |Δ| vs 2013: day 9.5%, night 31.6%, total 8.7%. Correlation with year: day 0.061, night -0.854, total -0.082.

Fit with 2013, predict another year:

| predicted year | national MAPE | national WAPE | box WAPE | box r² |
|---|---|---|---|---|
| 2012 | 10.9% | 9.1% | 30.4% | 0.88 |
| 2014 | 16.6% | 14.6% | 35.0% | 0.901 |
| 2015 | 11.6% | 10.7% | 28.6% | 0.93 |
| 2016 | 14.4% | 10.0% | 30.1% | 0.909 |
| 2017 | 8.7% | 8.9% | 27.4% | 0.904 |
| 2018 | 12.6% | 13.2% | 30.5% | 0.904 |
| 2019 | 12.5% | 8.5% | 25.0% | 0.944 |
| 2020 | 12.6% | 7.2% | 26.9% | 0.957 |
| 2021 | 8.8% | 7.1% | 29.0% | 0.906 |
| 2022 | 15.1% | 9.8% | 29.0% | 0.931 |
| 2023 | 9.7% | 9.1% | 25.0% | 0.951 |
| 2024 | 10.4% | 9.3% | 23.5% | 0.96 |
| 2025 | 9.1% | 5.5% | 25.3% | 0.964 |

| variant | box WAPE | box r² | national MAPE | national WAPE |
|---|---|---|---|---|
| fixed_reference_year (ratios of 2013 applied to every other year) | 27.7% | 0.931 | 11.8% | 9.3% |
| pooled_all_years (one set fitted on all overlap years, leave-one-month-out) | 27.5% | 0.93 | 11.5% | 9.1% |
| per_year (one set per year, leave-one-month-out within the year) | 27.6% | 0.928 | 11.9% | 9.9% |

Per-year vs pooled box WAPE improvement: -0.1%. **Decision: simple.**

## Test 2: regions

Rule: north lat>=24; center 19-24; southeast lat<19 & lon>=-92; south the rest (1° box SW corner).

| region | day | night | total | Δday | Δnight | Δtotal | MODIS |
|---|---|---|---|---|---|---|---|
| north | 3.974 | 9.388 | 5.05 | +4.0% | +29.2% | +16.5% | 129,529 |
| center | 3.867 | 7.449 | 4.34 | +1.2% | +2.5% | +0.1% | 330,282 |
| south | 3.867 | 6.375 | 4.283 | +1.2% | -12.3% | -1.2% | 300,366 |
| southeast | 3.389 | 5.222 | 3.553 | -11.4% | -28.1% | -18.0% | 99,961 |

Box CV WAPE national ratios 27.5% vs regional 26.6% (improvement 0.9%). **Decision: simple.**

## Test 3: proportionality (box-months)

![MODIS vs VIIRS per box-month](proportionality.svg)

31,816 box-months. Line VIIRS = 9.329 + 3.99 · MODIS (intercept = 8.0% of the mean VIIRS count; slope through origin 4.019).

| size (MODIS units) | box-months | ΣVIIRS/ΣMODIS | WAPE | MAPE | bias |
|---|---|---|---|---|---|
| 0–1 | 9,074 | 13.173 | 316.6% | 63.6% | +189.3% |
| 1–3 | 6,520 | 5.088 | 96.2% | 79.7% | +16.8% |
| 3–5 | 3,085 | 4.649 | 69.7% | 98.9% | +7.9% |
| 5–10 | 3,850 | 4.342 | 56.5% | 78.9% | +2.4% |
| 10–20 | 3,007 | 4.393 | 44.3% | 59.2% | +4.4% |
| 20–50 | 2,798 | 4.437 | 33.9% | 40.9% | +4.6% |
| 50–100 | 1,431 | 4.513 | 28.7% | 32.5% | +5.2% |
| 100–300 | 1,418 | 4.396 | 22.7% | 25.2% | +1.2% |
| ≥ 300 | 633 | 4.12 | 19.2% | 20.4% | -6.3% |

Minimum reliable monthly count (every larger bin has WAPE ≤ 30.0%): **50**. Smallest count from which every bin has |bias| ≤ 10.0% (the ratio itself holds): **3**.

## Test 4: gaps (clouds or missing data)

| satellite | days without any detection | longest runs |
|---|---|---|
| Terra | 93 | 2001-06-15→2001-07-03 (19 d), 2022-10-11→2022-10-23 (13 d), 2002-03-20→2002-03-28 (9 d) |
| Aqua | 44 | 2022-04-01→2022-04-16 (16 d), 2002-07-30→2002-08-07 (9 d), 2002-09-12→2002-09-13 (2 d) |
| SNPP | 53 | 2022-07-27→2022-08-10 (15 d), 2024-07-10→2024-07-15 (6 d), 2026-07-11→2026-07-16 (6 d) |

Fire-season box-months (months [1, 2, 3, 4, 5]) in boxes whose median MODIS count is ≥ 10: **9499**; with 0 detections in both sensors: **32** (0.3%). Not corrected; reported as a limitation.

Examples: 2003-01 box (30, -108) median 17, 2003-01 box (29, -107) median 10, 2003-02 box (28, -107) median 18, 2003-02 box (29, -108) median 10, 2004-01 box (30, -108) median 17, 2004-02 box (29, -108) median 10, 2004-03 box (22, -105) median 16, 2004-04 box (26, -109) median 12, 2004-05 box (19, -99) median 10, 2005-01 box (30, -112) median 10
