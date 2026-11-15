# Dashboard statistics API (`/api/v1/stats/*`)

This is the contract between the backend and the dashboard frontend. Every chart
gets its numbers **already computed** by DuckDB: the frontend only calls an
endpoint and draws what comes back. No aggregation is needed on the client.

Two words used on purpose everywhere:

- A **detection** (or hotspot) is one satellite pixel flagged as hot. It is **not**
  a fire: one large fire produces many detections, and a small fire may produce none.
- **MODIS and VIIRS counts are never added together.** Every row carries a
  `sensor` field (`MODIS` or `VIIRS`). VIIRS pixels are ~375 m wide and MODIS
  pixels ~1 km, so VIIRS sees many more detections for the same fire; a sum would
  mean nothing. Draw one series per sensor.

---

## 1. Base URL and how to run

Base URL: `http://localhost:5000` (or `http://<LAN IP>:5000` from another device;
the address is printed at startup). All endpoints are `GET` and return JSON.

```bash
cd server
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/import_json.py data/raw/fire_archive_M-C61_849192.json --db data/hotspots.duckdb
python run.py
```

Full guide (LAN, troubleshooting): [running.md](running.md). The API must be
stopped while importing.

---

## 2. Common parameters (all stats endpoints)

They are **the same names and rules as** [`GET /api/v1/hotspots`](api.md), plus
`satellite` and `fire_type`.

| Name | Required | Type / values | Default | Meaning |
|---|---|---|---|---|
| `lat1`, `lon1` | yes | number, lat −90…90, lon −180…180 | | First corner of the rectangle |
| `lat2`, `lon2` | yes | same | | Opposite corner, any order (see [filtering.md](filtering.md)) |
| `start_date` | yes | `YYYY-MM-DD` | | First UTC day, **inclusive** |
| `end_date` | yes | `YYYY-MM-DD` | | Last UTC day, **inclusive**, ≥ `start_date` |
| `instrument` | no | `MODIS`, `VIIRS` | both | Sensor filter (shown as `sensor` in responses) |
| `satellite` | no | `Terra`, `Aqua`, `SNPP`, `NOAA-20`, `NOAA-21` | all | One satellite only |
| `daynight` | no | `D`, `N` | both | Day or night detections |
| `confidence_min` | no | `low`, `nominal`, `high` | `low` (= all) | Minimum confidence level |
| `fire_type` | no | `0`, `1`, `2`, `3`, `all` | `0` | `0` vegetation, `1` volcano, `2` static land source (e.g. gas flares), `3` offshore. `0` also keeps detections of **unknown** type (most near-real-time VIIRS data has none) |

- Any rectangle works: there are no coverage regions.
- Dates are between `2000-11-01` and today (UTC).
- Enum values are case-insensitive (`instrument=viirs`, `freq=WEEK`). Unknown parameters are ignored.
- `confidence_min` uses the normalized level: MODIS numeric confidence `< 30` = `low`,
  `30–79` = `nominal`, `≥ 80` = `high`; VIIRS `l`/`n`/`h`.

---

## 3. Response envelope

Every stats endpoint answers HTTP 200 with:

```json
{
  "data": [ ... ],
  "metadata": {
    "bbox": [-107.2, 22.3, -102.5, 26.8],
    "start_date": "2013-04-01",
    "end_date": "2013-04-30",
    "filters": {"confidence_min": "low", "daynight": null, "instrument": null, "satellite": null, "fire_type": 0},
    "units": {"frp_mean": "MW"}
  }
}
```

- `data` is a list of rows (except `/sensor-comparison`, where it is an object of two lists).
- `metadata.bbox` is `[min_lon, min_lat, max_lon, max_lat]` actually used.
- `metadata.units` gives the unit of the numeric fields of that endpoint.
  Endpoint-specific options (`freq`, `bins`, `limit`, ...) are echoed in `metadata` too.
- Dates are ISO 8601 `YYYY-MM-DD` (UTC day); timestamps are ISO 8601 UTC with `Z`
  (`2013-04-17T20:32:00Z`).
- Missing values are `null`, never `NaN` (for example a mean FRP when no detection has FRP).
- Floats are rounded to 6 decimals.
- Periods or categories **without detections are not returned** (no zero rows),
  except histogram bins, which are always complete.

**No data.** When nothing matches the rectangle, dates and filters, the answer is
still **HTTP 200**, with an empty `data` and a `message` (the key exists only then):

```json
{"data": [], "metadata": {...}, "message": "No data found in the selected area"}
```

### Units

| Field | Unit |
|---|---|
| `frp`, `frp_*` | MW (megawatts) |
| `bright_mir` (~4 µm), `bright_tir` (~11 µm), `bright_*_mean` | K (kelvin). MODIS `bright_mir` saturates near 500 K |
| `scan`, `track`, `scan_start`, `scan_end` | km |
| `pixel_area_km2` (= scan × track) | km² |
| `lat`, `lon` | decimal degrees (WGS84) |
| `confidence_raw` | percent, MODIS only |
| `hour_utc` | hour of the day, UTC (Mexico City = UTC−6) |

---

## 4. Errors

Invalid input returns **HTTP 400** with the same body as the rest of the API:

```json
{"error": {"code": "INVALID_PARAMETER", "message": "Invalid value for 'freq': Input should be 'day', 'week' or 'month'", "parameter": "freq"}}
```

| Situation | `parameter` | Example message |
|---|---|---|
| Missing required parameter | its name | `Missing required parameter 'lat1'` |
| Coordinate out of range | `lat1` … `lon2` | `'lat1' must be a latitude between -90 and 90` |
| Zero-width / zero-height rectangle | `lat2` / `lon2` | `The rectangle has zero height: 'lat1' and 'lat2' must differ` |
| `start_date` after `end_date` | `end_date` | `'end_date' must be the same as or later than 'start_date'` |
| Bad date format or out of window | the date | `Invalid value for 'start_date': must be a date in YYYY-MM-DD format` |
| Unknown enum value (`freq`, `field`, `x`, `satellite`...) | its name | `Invalid value for 'field': Input should be 'frp', 'bright_mir', 'bright_tir' or 'confidence_raw'` |
| Number out of range (`bins`, `limit`, `n`, `cell`) | its name | `Invalid value for 'bins': Input should be less than or equal to 100` |

Other codes: 404 `NOT_FOUND` (unknown URL), 405 `METHOD_NOT_ALLOWED`,
503 `DATABASE_UNAVAILABLE` (no database loaded), 500 `INTERNAL_ERROR`.

---

## 5. Endpoints

All examples use the **Durango** rectangle in April 2013 from the Mexico MODIS
file (MODIS-only, so there are no VIIRS rows). Long lists are cut with `...`.

```bash
AREA="lat1=22.3&lon1=-107.2&lat2=26.8&lon2=-102.5&start_date=2013-04-01&end_date=2013-04-30"
```

### Endpoint → chart map

| Endpoint | Charts |
|---|---|
| [`/summary`](#get-apiv1statssummary) | 1 |
| [`/timeseries`](#get-apiv1statstimeseries) | 2, 3, 4, 5 |
| [`/distribution`](#get-apiv1statsdistribution) | 6, 7, 8, 17 |
| [`/scatter`](#get-apiv1statsscatter) | 9, 10, 19 |
| [`/calendar`](#get-apiv1statscalendar) | 11 |
| [`/by-hour`](#get-apiv1statsby-hour) | 12 |
| [`/by-category`](#get-apiv1statsby-category) | 13, 14, 15, 16 |
| [`/by-scan`](#get-apiv1statsby-scan) | 18 |
| [`/top-events`](#get-apiv1statstop-events) | 20 |
| [`/points`](#get-apiv1statspoints) | 21 |
| [`/grid`](#get-apiv1statsgrid) | 22 |
| [`/sensor-comparison`](#get-apiv1statssensor-comparison) | 23, 24 |
| [`/monthly`](#get-apiv1statsmonthly) | 25 |
| [`/celldays`](#get-apiv1statscelldays) | 26, 27, 28 (cell-day harmonization panel) |

---

### `GET /api/v1/stats/summary`

**Charts: 1 (KPIs).** One row per sensor with data.

Params: common only.

| Field | Type | Unit |
|---|---|---|
| `sensor` | string | |
| `total_detections` | integer | detections |
| `frp_mean`, `frp_max` | number or null | MW |
| `bright_mir_mean`, `bright_tir_mean` | number or null | K |

```bash
curl "http://localhost:5000/api/v1/stats/summary?lat1=22.3&lon1=-107.2&lat2=26.8&lon2=-102.5&start_date=2013-01-01&end_date=2013-12-31"
```

```json
{
  "data": [
    {"sensor": "MODIS", "total_detections": 2928, "frp_mean": 35.982821, "frp_max": 2075.9,
     "bright_mir_mean": 328.064891, "bright_tir_mean": 304.565745}
  ],
  "metadata": {
    "bbox": [-107.2, 22.3, -102.5, 26.8], "start_date": "2013-01-01", "end_date": "2013-12-31",
    "filters": {"confidence_min": "low", "daynight": null, "instrument": null, "satellite": null, "fire_type": 0},
    "units": {"frp_mean": "MW", "frp_max": "MW", "bright_mir_mean": "K", "bright_tir_mean": "K"}
  }
}
```

---

### `GET /api/v1/stats/timeseries`

**Charts: 2–5 (time series).** Detections and FRP per period and sensor, ordered by period.

| Param | Type | Default | Values |
|---|---|---|---|
| `freq` | string | `day` | `day`, `week` (weeks start on Monday, ISO 8601), `month` |

| Field | Type | Unit |
|---|---|---|
| `period` | date | first day of the period |
| `sensor` | string | |
| `detections` | integer | detections |
| `frp_total`, `frp_mean` | number or null | MW |
| `bright_mir_mean` | number or null | K |

```bash
curl "http://localhost:5000/api/v1/stats/timeseries?freq=week&$AREA"
```

```json
{
  "data": [
    {"period": "2013-04-01", "sensor": "MODIS", "detections": 37, "frp_total": 1467.5, "frp_mean": 39.662162, "bright_mir_mean": 332.32973},
    {"period": "2013-04-08", "sensor": "MODIS", "detections": 80, "frp_total": 2831.9, "frp_mean": 35.39875, "bright_mir_mean": 327.17125},
    {"period": "2013-04-15", "sensor": "MODIS", "detections": 126, "frp_total": 13790.4, "frp_mean": 109.447619, "bright_mir_mean": 335.315873},
    "..."
  ],
  "metadata": {"...": "...", "units": {"frp_total": "MW", "frp_mean": "MW", "bright_mir_mean": "K"}, "freq": "week"}
}
```

Errors: `freq` not in the list → 400.

---

### `GET /api/v1/stats/distribution`

**Charts: 6, 7, 8 (histograms of FRP, MIR and TIR brightness) and 17
(MODIS confidence, `field=confidence_raw`).** Equal-width bins shared by both
sensors (same edges, so the two series can be overlaid). Every bin is returned
for every sensor present, with `count: 0` when empty.

| Param | Type | Default | Values |
|---|---|---|---|
| `field` | string | `frp` | `frp`, `bright_mir`, `bright_tir`, `confidence_raw` |
| `bins` | integer | 20 | 1…100 |
| `log` | boolean | `false` | `true` = bins of equal width in log10 space (only values > 0); recommended for FRP |

- The range is `[min, max]` of the selected values; `confidence_raw` uses the fixed
  range 0…100. The maximum value falls in the last bin (`bin_end` inclusive).
- `confidence_raw` is numeric only for MODIS, so it returns only MODIS rows.
- `metadata.excluded`: detections left out (value missing, or ≤ 0 with `log=true`).

| Field | Type | Unit |
|---|---|---|
| `bin_start`, `bin_end` | number | unit of `field` (in `metadata.units`) |
| `sensor` | string | |
| `count` | integer | detections |

```bash
curl "http://localhost:5000/api/v1/stats/distribution?field=frp&bins=4&log=true&$AREA"
```

```json
{
  "data": [
    {"bin_start": 4.9, "bin_end": 22.230471, "sensor": "MODIS", "count": 239},
    {"bin_start": 22.230471, "bin_end": 100.855887, "sensor": "MODIS", "count": 186},
    {"bin_start": 100.855887, "bin_end": 457.566101, "sensor": "MODIS", "count": 45},
    {"bin_start": 457.566101, "bin_end": 2075.9, "sensor": "MODIS", "count": 9}
  ],
  "metadata": {"...": "...", "units": {"bin_start": "MW", "bin_end": "MW"}, "field": "frp", "bins": 4, "log": true, "excluded": 0}
}
```

`field=confidence_raw&bins=4` on the same area:
`[{"bin_start": 0.0, "bin_end": 25.0, "sensor": "MODIS", "count": 15}, {25–50: 90}, {50–75: 174}, {75–100: 200}]`.

Errors: unknown `field`, `bins` outside 1…100, `log` not a boolean → 400.

---

### `GET /api/v1/stats/scatter`

**Charts: 9 (`x=bright_mir&y=bright_tir`), 10 and 19 (`x=pixel_area_km2&y=frp`,
`x=bright_mir&y=frp`).** A sample of points with both values present.

| Param | Type | Default | Values |
|---|---|---|---|
| `x` | string | `bright_mir` | `bright_mir`, `pixel_area_km2` |
| `y` | string | `bright_tir` | `bright_tir`, `frp` |
| `limit` | integer | 2000 | 1…5000 |

The sample is pseudo-random but **stable**: the same request always returns the
same points (they are ordered by a hash of time and place). `metadata.available`
= detections that could be drawn; `metadata.sampled` = true when only part of them came back.

| Field | Type | Unit |
|---|---|---|
| `x`, `y` | number | in `metadata.units.x` / `.y` (K, km², MW) |
| `sensor` | string | |
| `confidence_level` | `low`, `nominal`, `high` | |

```bash
curl "http://localhost:5000/api/v1/stats/scatter?x=bright_mir&y=bright_tir&limit=3&$AREA"
```

```json
{
  "data": [
    {"x": 316.7, "y": 284.0, "sensor": "MODIS", "confidence_level": "nominal"},
    {"x": 341.8, "y": 314.5, "sensor": "MODIS", "confidence_level": "high"},
    {"x": 302.2, "y": 285.8, "sensor": "MODIS", "confidence_level": "nominal"}
  ],
  "metadata": {"...": "...", "units": {"x": "K", "y": "K"}, "x": "bright_mir", "y": "bright_tir",
               "limit": 3, "available": 479, "returned": 3, "sampled": true}
}
```

Errors: unknown `x`/`y`, `limit` outside 1…5000 → 400.

---

### `GET /api/v1/stats/calendar`

**Chart: 11 (burn calendar, year × day of year).**

| Param | Type | Default | Values |
|---|---|---|---|
| `metric` | string | `detections` | `detections` (count) or `frp` (sum of FRP, MW) |
| `granularity` | string | `day` | `day` or `week` |

| Field | Type | Meaning |
|---|---|---|
| `year` | integer | calendar year (`day`) or ISO year (`week`) |
| `day_of_year` | integer 1…366 | only with `granularity=day` |
| `week` | integer 1…53 | ISO week, only with `granularity=week` |
| `date` | date | the day, or the Monday of the week |
| `sensor` | string | |
| `value` | number or null | detections, or MW for `metric=frp` (see `metadata.units.value`) |

```bash
curl "http://localhost:5000/api/v1/stats/calendar?metric=frp&$AREA"
```

```json
{
  "data": [
    {"year": 2013, "day_of_year": 91, "date": "2013-04-01", "sensor": "MODIS", "value": 16.6},
    {"year": 2013, "day_of_year": 92, "date": "2013-04-02", "sensor": "MODIS", "value": 27.7},
    {"year": 2013, "day_of_year": 93, "date": "2013-04-03", "sensor": "MODIS", "value": 120.3},
    "..."
  ],
  "metadata": {"...": "...", "units": {"value": "MW"}, "metric": "frp", "granularity": "day"}
}
```

With `granularity=week`, a row looks like
`{"year": 2013, "week": 1, "date": "2012-12-31", "sensor": "MODIS", "value": 9}`
(ISO week 1 of 2013 starts on Monday 31 Dec 2012).

Errors: unknown `metric` or `granularity` → 400.

---

### `GET /api/v1/stats/by-hour`

**Chart: 12 (detection hour).** Detections per UTC hour of acquisition and satellite.
Each satellite passes at roughly fixed local times, so the hours cluster
(over Mexico in 2013: Terra ~04–05 and ~16–18 UTC, Aqua ~07–09 and ~18–20 UTC).

Params: common only.

| Field | Type |
|---|---|
| `hour_utc` | integer 0…23 |
| `sensor`, `satellite` | string |
| `detections` | integer |

```bash
curl "http://localhost:5000/api/v1/stats/by-hour?$AREA"
```

```json
{
  "data": [
    {"hour_utc": 4, "sensor": "MODIS", "satellite": "Terra", "detections": 19},
    {"hour_utc": 5, "sensor": "MODIS", "satellite": "Terra", "detections": 36},
    {"hour_utc": 8, "sensor": "MODIS", "satellite": "Aqua", "detections": 12},
    "..."
  ],
  "metadata": {"...": "...", "units": {"hour_utc": "hour (UTC)"}}
}
```

---

### `GET /api/v1/stats/by-category`

**Charts: 13–16 (categories).** Detections and mean FRP per category and sensor.

| Param | Type | Default | Values |
|---|---|---|---|
| `field` | string | **required** | `daynight`, `satellite`, `type`, `confidence_level` |

- With `field=type`, send `fire_type=all`; otherwise the default filter keeps only
  type 0 and unknown. Unknown type is `"category": null`.

| Field | Type | Unit |
|---|---|---|
| `category` | string, integer (`type`) or null | |
| `sensor` | string | |
| `detections` | integer | |
| `frp_mean` | number or null | MW |

```bash
curl "http://localhost:5000/api/v1/stats/by-category?field=daynight&$AREA"
```

```json
{
  "data": [
    {"category": "D", "sensor": "MODIS", "detections": 401, "frp_mean": 70.940648},
    {"category": "N", "sensor": "MODIS", "detections": 78, "frp_mean": 17.737179}
  ],
  "metadata": {"...": "...", "units": {"frp_mean": "MW"}, "field": "daynight"}
}
```

Errors: missing or unknown `field` → 400.

---

### `GET /api/v1/stats/by-scan`

**Chart: 18 (view-angle effect).** Pixels at the edge of the satellite swath are
larger (bigger `scan`), so only stronger fires are detected there and FRP rises.
For each sensor separately, its `[min, max]` scan range is split into `bins` equal
ranges (MODIS scan is 1–4.8 km, VIIRS 0.32–0.8 km). Ranges without detections are absent.

| Param | Type | Default | Values |
|---|---|---|---|
| `bins` | integer | 10 | 1…50 |

| Field | Type | Unit |
|---|---|---|
| `sensor` | string | |
| `scan_start`, `scan_end` | number | km |
| `detections` | integer | |
| `frp_p5`, `frp_median` | number or null | MW (5th percentile and median, linear interpolation) |

```bash
curl "http://localhost:5000/api/v1/stats/by-scan?bins=3&$AREA"
```

```json
{
  "data": [
    {"sensor": "MODIS", "scan_start": 1.0, "scan_end": 2.266667, "detections": 423, "frp_p5": 7.72, "frp_median": 19.8},
    {"sensor": "MODIS", "scan_start": 2.266667, "scan_end": 3.533333, "detections": 33, "frp_p5": 22.2, "frp_median": 43.1},
    {"sensor": "MODIS", "scan_start": 3.533333, "scan_end": 4.8, "detections": 23, "frp_p5": 66.02, "frp_median": 199.4}
  ],
  "metadata": {"...": "...", "units": {"scan_start": "km", "scan_end": "km", "frp_p5": "MW", "frp_median": "MW"}, "bins": 3}
}
```

Errors: `bins` outside 1…50 → 400.

---

### `GET /api/v1/stats/top-events`

**Chart: 20 (top events table).** The `n` detections with the highest FRP
(detections without FRP are skipped).

| Param | Type | Default | Values |
|---|---|---|---|
| `n` | integer | 10 | 1…100 |

| Field | Type | Unit |
|---|---|---|
| `timestamp_utc` | ISO 8601 UTC | |
| `lat`, `lon` | number | degrees |
| `frp` | number | MW |
| `bright_mir`, `bright_tir` | number or null | K |
| `sensor`, `satellite` | string | |

```bash
curl "http://localhost:5000/api/v1/stats/top-events?n=2&$AREA"
```

```json
{
  "data": [
    {"timestamp_utc": "2013-04-17T20:32:00Z", "lat": 23.7911, "lon": -104.9476, "frp": 2075.9,
     "bright_mir": 500.3, "bright_tir": 336.2, "sensor": "MODIS", "satellite": "Aqua"},
    {"timestamp_utc": "2013-04-17T20:32:00Z", "lat": 23.7814, "lon": -104.9463, "frp": 1636.1,
     "bright_mir": 484.7, "bright_tir": 400.1, "sensor": "MODIS", "satellite": "Aqua"}
  ],
  "metadata": {"...": "...", "units": {"lat": "degrees", "lon": "degrees", "frp": "MW", "bright_mir": "K", "bright_tir": "K"}, "n": 2}
}
```

Errors: `n` outside 1…100 → 400.

---

### `GET /api/v1/stats/points`

**Chart: 21 (point map).** Light-weight points (4 fields) ordered by FRP descending,
so when the area holds more than `limit` detections the most intense ones are kept
(`metadata.truncated = true`). Detections without FRP come last.
For the full records (GeoJSON, pagination) use [`/api/v1/hotspots`](api.md).

| Param | Type | Default | Values |
|---|---|---|---|
| `limit` | integer | 5000 (or `MAX_LIMIT` if lower) | 1…`MAX_LIMIT` (50000 by default) |

| Field | Type | Unit |
|---|---|---|
| `lat`, `lon` | number | degrees |
| `frp` | number or null | MW |
| `sensor` | string | |

```bash
curl "http://localhost:5000/api/v1/stats/points?limit=2&$AREA"
```

```json
{
  "data": [
    {"lat": 23.7911, "lon": -104.9476, "frp": 2075.9, "sensor": "MODIS"},
    {"lat": 23.7814, "lon": -104.9463, "frp": 1636.1, "sensor": "MODIS"}
  ],
  "metadata": {"...": "...", "units": {"lat": "degrees", "lon": "degrees", "frp": "MW"}, "limit": 2, "returned": 2, "truncated": true}
}
```

All of Mexico for 2013 with the default limit is ~300 KB and answers in < 0.1 s.

Errors: `limit` < 1 or > `MAX_LIMIT` → 400.

---

### `GET /api/v1/stats/grid`

**Chart: 22 (heat map).** Detections and total FRP per square cell and sensor.
Cells are anchored at 0°/0° (cell index = `floor(lat / cell)`), so a cell always has
the same center whatever rectangle is requested. Cells without detections are absent.

| Param | Type | Default | Values |
|---|---|---|---|
| `cell` | number | 0.25 | > 0 and ≤ 5 (degrees; 0.25° ≈ 28 km) |

| Field | Type | Unit |
|---|---|---|
| `lat`, `lon` | number | degrees, **cell center** |
| `sensor` | string | |
| `detections` | integer | |
| `frp_total` | number or null | MW |

```bash
curl "http://localhost:5000/api/v1/stats/grid?cell=1&$AREA"
```

```json
{
  "data": [
    {"lat": 22.5, "lon": -106.5, "sensor": "MODIS", "detections": 1, "frp_total": 10.0},
    {"lat": 22.5, "lon": -105.5, "sensor": "MODIS", "detections": 27, "frp_total": 670.9},
    {"lat": 22.5, "lon": -104.5, "sensor": "MODIS", "detections": 20, "frp_total": 424.1},
    "..."
  ],
  "metadata": {"...": "...", "units": {"lat": "degrees (cell center)", "lon": "degrees (cell center)", "cell": "degrees", "frp_total": "MW"}, "cell": 1.0}
}
```

Errors: `cell` ≤ 0, > 5 or not a number → 400.

---

### `GET /api/v1/stats/sensor-comparison`

**Charts: 23–24 (MODIS vs VIIRS).** `data` is an object with two lists:

- `daily`: detections and total FRP per day and sensor (days without detections absent).
- `ratio`: only on days where **both** sensors have detections:
  `detections_ratio = viirs_detections / modis_detections` and
  `frp_ratio = VIIRS frp_total / MODIS frp_total` (null when MODIS FRP is 0 or unknown).
  **Empty when the data has no VIIRS** (as with the Mexico MODIS file) or when `instrument` is set.

Params: common only. The `message` appears only when `daily` is empty.

| Field | Type | Unit |
|---|---|---|
| `daily[].date` | date | |
| `daily[].sensor` | string | |
| `daily[].detections` | integer | |
| `daily[].frp_total` | number or null | MW |
| `ratio[].date` | date | |
| `ratio[].modis_detections`, `ratio[].viirs_detections` | integer | |
| `ratio[].detections_ratio`, `ratio[].frp_ratio` | number or null | VIIRS / MODIS |

```bash
curl "http://localhost:5000/api/v1/stats/sensor-comparison?$AREA"
```

```json
{
  "data": {
    "daily": [
      {"date": "2013-04-01", "sensor": "MODIS", "detections": 1, "frp_total": 16.6},
      {"date": "2013-04-02", "sensor": "MODIS", "detections": 1, "frp_total": 27.7},
      {"date": "2013-04-03", "sensor": "MODIS", "detections": 7, "frp_total": 120.3},
      "..."
    ],
    "ratio": []
  },
  "metadata": {"...": "...", "units": {"frp_total": "MW", "detections_ratio": "VIIRS / MODIS", "frp_ratio": "VIIRS / MODIS"}}
}
```

With both sensors a ratio row looks like
`{"date": "2024-04-15", "modis_detections": 2, "viirs_detections": 2, "detections_ratio": 1.0, "frp_ratio": 0.175}`.

---

### `GET /api/v1/stats/monthly`

**Chart: 25 (seasonality).** Detections per calendar month (1 = January … 12 = December)
and sensor, **all selected years together**. `years_with_data` = how many distinct
years contributed to that month, so `detections / years_with_data` is a yearly average.
For a month-by-month timeline use `/timeseries?freq=month` instead.

Params: common only.

| Field | Type |
|---|---|
| `month` | integer 1…12 |
| `sensor` | string |
| `detections` | integer |
| `years_with_data` | integer |

```bash
curl "http://localhost:5000/api/v1/stats/monthly?lat1=22.3&lon1=-107.2&lat2=26.8&lon2=-102.5&start_date=2013-01-01&end_date=2013-12-31"
```

```json
{
  "data": [
    {"month": 1, "sensor": "MODIS", "detections": 34, "years_with_data": 1},
    {"month": 2, "sensor": "MODIS", "detections": 85, "years_with_data": 1},
    {"month": 3, "sensor": "MODIS", "detections": 209, "years_with_data": 1},
    {"month": 4, "sensor": "MODIS", "detections": 479, "years_with_data": 1},
    "..."
  ],
  "metadata": {"...": "...", "units": {}}
}
```

---

### `GET /api/v1/stats/celldays`

**Charts: 26-28 (cell-day harmonization panel).** One series in **VIIRS SNPP-equivalent
cell-days** that runs over the whole selection: days with VIIRS SNPP data use SNPP, days
without it are **extrapolated from MODIS** (Aqua, or Terra when Aqua is missing). Method,
factors and limits: [harmonization.md § Cell-days](harmonization.md#cell-days-modis-extrapolated-to-viirs).

```
cell-day = one 5 km × 5 km cell with ≥ 1 detection on one UTC day
            ┌───┬───┐
day 1       │ ●●│   │   3 detections in 2 cells → 2 cell-days
            │   │ ● │
            └───┴───┘
value of a day = SNPP cell-days               if SNPP has data that day (anywhere in the database)
               = Aqua cell-days  × 7.685      otherwise, if Aqua has data
               = Terra cell-days × 9.453      otherwise, if Terra has data
               = null                         no satellite has data
```

Params: common area and dates, plus `freq` = `day` / `week` / `month` (default) / `year`
for `series`. Weeks are 7-day blocks counted from `start_date`. **The filters
(`confidence_min`, `daynight`, `instrument`, `satellite`, `fire_type`) are ignored**: the
factors were calibrated on every detection (`metadata.filters_applied` is `false`).

`data` is an object:

| Key | Content |
|---|---|
| `series` | one row per `freq` period (same fields as `months`) |
| `months` | one row per calendar month (for the year × month calendar) |
| `profile` | 12 rows: `month`, `mean`, `min`, `max`, `years` over **full** months with data |
| `phases` | periods to name in the UI: `category` (`extrapolated` / `viirs` / `none`), `start`, `end`, `days`, `days_viirs`, `days_aqua`, `days_terra`, `days_missing`. Gaps shorter than 30 days are folded into the phase around them (their days stay counted). |
| `periods` | exact runs of days with the same `source` (`viirs`, `aqua`, `terra`, `none`), `start`, `end`, `days` |
| `summary` | totals over the selection (same fields as a `months` row, without dates) |

Fields of a `series` / `months` row:

| Field | Type | Meaning |
|---|---|---|
| `start`, `end` | date | period inside the selection |
| `partial` | bool | the selection cuts the period |
| `value` | number \| null | harmonized cell-days; null when no day had data |
| `viirs` | number | part observed by VIIRS SNPP |
| `extrapolated` | number | part extrapolated from MODIS |
| `source` | string | `viirs`, `extrapolated`, `mixed` or `none` |
| `days_viirs`, `days_aqua`, `days_terra`, `days_missing` | integer | days of each source |

Extra `metadata`: `freq`, `filters_applied` (false), `cell_km` (5), `factors`, `priority`,
`pilot_bounds`, `pilot_area` (rectangle within 0.01° of the pilot one), `warning` (text, or
null in the pilot area) and `disclaimer` (text to show with the charts).

```bash
curl "http://localhost:5000/api/v1/stats/celldays?lat1=22.345&lon1=-107.210278&lat2=26.845&lon2=-102.472778&start_date=2011-11-01&end_date=2012-04-30"
```

```json
{
  "data": {
    "series": [
      "...",
      {"start": "2011-12-01", "end": "2011-12-31", "partial": false, "value": 245.94, "viirs": 0.0,
       "extrapolated": 245.94, "source": "extrapolated", "days_viirs": 0, "days_aqua": 31, "days_terra": 0, "days_missing": 0},
      {"start": "2012-01-01", "end": "2012-01-31", "partial": false, "value": 390.94, "viirs": 145.0,
       "extrapolated": 245.94, "source": "mixed", "days_viirs": 12, "days_aqua": 19, "days_terra": 0, "days_missing": 0},
      "..."
    ],
    "months": ["..."],
    "profile": [{"month": 1, "mean": 390.94, "min": 390.94, "max": 390.94, "years": 1}, "..."],
    "phases": [
      {"category": "extrapolated", "start": "2011-11-01", "end": "2012-01-19", "days": 80, "days_viirs": 0, "days_aqua": 80, "days_terra": 0, "days_missing": 0},
      {"category": "viirs", "start": "2012-01-20", "end": "2012-04-30", "days": 102, "days_viirs": 101, "days_aqua": 1, "days_terra": 0, "days_missing": 0}
    ],
    "periods": ["..."],
    "summary": {"value": 3989.95, "viirs": 3329.0, "extrapolated": 660.95, "source": "mixed", "...": "..."}
  },
  "metadata": {
    "...": "...",
    "freq": "month", "filters_applied": false, "cell_km": 5.0,
    "factors": {"Aqua": 7.685487, "Terra": 9.452675, "SNPP": 1.0},
    "priority": ["SNPP", "Aqua", "Terra"],
    "pilot_bounds": {"west": -107.210278, "east": -102.472778, "south": 22.345, "north": 26.845},
    "pilot_area": true, "warning": null,
    "disclaimer": "Cell-days are an indirect metric of the average fire activity level in the region. ..."
  }
}
```

---

## 6. How the data is normalized

The stats endpoints read the `hotspots` table through one SQL projection
(`NORMALIZED_HOTSPOTS_SQL` in `app/repository.py`; the importer also stores it as
the DuckDB view `hotspots_normalized`):

| Column | From | Notes |
|---|---|---|
| `sensor` | `instrument` | `MODIS` / `VIIRS` |
| `satellite` | `satellite` | `Terra`, `Aqua`, `SNPP`, `NOAA-20`, `NOAA-21` |
| `timestamp_utc` | `acq_date` + `acq_time` (HHMM UTC) | |
| `acq_date` | | UTC day, used by the date filter |
| `lat`, `lon` | `latitude`, `longitude` | |
| `bright_mir` | MODIS `brightness` / VIIRS `bright_ti4` | K |
| `bright_tir` | MODIS `bright_t31` / VIIRS `bright_ti5` | K |
| `frp` | `frp` | MW |
| `confidence_level` | `confidence_raw` | MODIS `<30` low, `30–79` nominal, `≥80` high; VIIRS `l/n/h` |
| `confidence_raw` | `confidence` | original value (`"67"` or `"n"`) |
| `daynight` | | `D` / `N` |
| `type` | `type` | integer 0–3, null if unknown |
| `scan`, `track` | | km |
| `pixel_area_km2` | `scan * track` | km² |

How raw FIRMS files are cleaned on import: [data-import.md](data-import.md).
