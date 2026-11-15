# Harmonization: one continuous MODIS + VIIRS record

The calendar can show one **continuous monthly series from 2000 to today**, in
**"MODIS Terra+Aqua units"**, for any rectangle. This page explains how, in plain words.
Code: [`harmonizer/`](../harmonizer/) (math in `method.py`, SQL in `data.py`), API glue in
`app/harmonization.py`, command-line tool `scripts/harmonize.py`.

## The problem

```
same fire, two sensors
MODIS (1 km pixels)      ■            → 1 detection
VIIRS (375 m pixels)     ▪▪▪▪         → ~4 detections
```

VIIRS reports about **4 times more** hotspots than MODIS over the same fires: its smaller
pixels split one fire into more detections and see small fires MODIS misses. The total fire
energy (FRP) is about the same, so it is the same fire activity, counted with a finer grid.
Putting the raw counts side by side would invent a 4× jump in 2012, when VIIRS starts.

## The method (ratio estimator, day and night apart)

Over a period when both sensors fly (the **fit period**), add up the detections and divide:

```
r_day   = Σ VIIRS_day   / Σ MODIS_day         (≈ 3.8 for Mexico 2012–2025)
r_night = Σ VIIRS_night / Σ MODIS_night       (≈ 7.3)
MODIS_eq = VIIRS_day / r_day + VIIRS_night / r_night
```

- MODIS = Terra + Aqua; VIIRS = Suomi-NPP only (NOAA-20/21 would inflate the counts).
- Vegetation fires only (`fire_type = 0`; near-real-time rows, which have no type, are kept).
- A **ratio of sums**, not an average of monthly ratios: a month with 1 vs 3 detections would
  otherwise weigh as much as one with 1000 vs 4000.
- Day and night apart because the night ratio is twice the day ratio.

## The continuous series

| Period (configurable) | Value | `source` |
|---|---|---|
| Nov 2000 → Jul 2002 (Terra only) | Terra × factor, factor = Σ(Terra+Aqua)/Σ Terra over 2003–2011 (≈ 2.22) | `terra_scaled` |
| Aug 2002 → Jan 2012 | MODIS as counted | `modis` |
| Feb 2012 → end of MODIS | (MODIS + MODIS_eq) / 2 | `average` |
| after MODIS | MODIS_eq | `viirs_eq` |

A sensor only takes part in a month when its data covers **every loaded day** of that month
(near the end of the data the sensors stop on different days).

The cutoffs cannot be guessed from the data (a month with 0 detections may simply have had no
fire), so they are environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `HARMONIZE_FIT_START` / `HARMONIZE_FIT_END` | 2012-02-01 / 2025-12-31 | ratio fit period |
| `HARMONIZE_TERRA_FIT_START` / `_END` | 2003-01-01 / 2011-12-31 | Terra factor fit period |
| `HARMONIZE_AQUA_START` | 2002-08 | first full Terra + Aqua month (Aqua data starts 2002-07-04) |
| `HARMONIZE_VIIRS_START` | 2012-02 | first averaged month (VIIRS archive starts 2012-01-20) |
| `HARMONIZE_MODIS_END` | empty | last MODIS month; empty = still flying |
| `HARMONIZE_DRY_MONTHS` | 1,2,3,4,5 | fire season, for the seasonal check and test 4 |
| `HARMONIZE_MIN_RELIABLE_COUNT` | empty | override the reliable monthly count of test 3 |

## Workflow

```bash
python scripts/import_bulk.py ../test/MODIS/*.json ../test/VIIRS_SNPP/*.json --db data/hotspots.duckdb --replace
python scripts/harmonize.py fit       # stores ratios, Terra factor, reliable count (API stopped)
python scripts/harmonize.py report    # writes reports/harmonization/report.md (+ .json, scatter .svg)
python scripts/harmonize.py report --start 2013-01-01 --end 2013-12-31 --out reports/harmonization-2013
```

`fit` stores the values in the table `harmonization_params` (value, detections used, fit
period, date), so the API never recomputes them. If the table is missing the API fits them in
memory once.

## How reliable is it? (`reports/harmonization/report.md`)

Leave-one-month-out cross-validation: hide one month, fit with the others, predict that month's
MODIS count from its VIIRS count, compare. Results with the Mexico data (2012–2025):

| Level | MAPE | WAPE | r² |
|---|---|---|---|
| whole country, per month | 11.5 % | 9.1 % | 0.99 |
| 1° boxes (~110 km), per month | 66 % (tiny counts) | 27.5 % | 0.93 |

The four reliability tests and their decisions (rule: keep the simple method unless a test shows
a clear problem **and** the adjusted version lowers the box WAPE by ≥ 3 points):

| Test | Result | Decision |
|---|---|---|
| 1. Stability over time | day and total ratios within ±10 % of 2013 every year; **night ratio drifts down** (8.1 → 5.5–6.2 in 2023–25) | simple: per-year ratios do not lower the error (27.6 % vs 27.5 %) |
| 2. Regions | north and southeast differ by > 15 % (mostly at night) | simple: regional ratios gain only 0.9 points |
| 3. Proportionality | straight line through ~0; the ratio holds from ~3 detections/month; error ≤ 30 % from **50**/month | 50 = reliable monthly count used for the calendar warning |
| 4. Gaps | 93 / 44 / 53 days without any Terra / Aqua / SNPP detection; 0.3 % of fire-season box-months in burning boxes have 0 detections | not corrected; reported as a limitation |

## Limitations

- FIRMS stores detections only: a 0 can be "no fire", "clouds" or "no data".
- MODIS orbits drift in recent years (the night ratio changes); re-check with `report` when new
  years are loaded.
- Few night detections → the night ratio is the noisiest.
- Small areas (< 1° × 1°) or months under ~50 detections: the error grows (calendar warning).
- NRT months (no `type`) may include some industrial or volcano detections.
