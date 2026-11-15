# API reference

Base URL: `http://localhost:5000` on the computer running the API, or
`http://<LAN IP>:5000` from other devices on the same network (the address is printed when the
API starts; see [running.md](running.md#using-the-api-from-other-devices-lan)). The examples use `localhost`. All responses are JSON and all
messages are in English. There is no authentication.

The pre-computed dashboard statistics (`/api/v1/stats/*`) have their own
reference: [dashboard-api.md](dashboard-api.md).

---

## `GET /api/v1/hotspots`

Returns the fire hotspots inside a rectangle and a date range.

### Parameters

| Name | Required | Values | Default | Meaning |
|---|---|---|---|---|
| `lat1`, `lon1` | yes | lat −90…90, lon −180…180 | | First corner of the rectangle |
| `lat2`, `lon2` | yes | same | | Opposite corner (any order, see [filtering.md](filtering.md)) |
| `start_date` | yes | `YYYY-MM-DD` | | First day, **inclusive**, UTC |
| `end_date` | yes | `YYYY-MM-DD` | | Last day, **inclusive**, UTC. Must be ≥ `start_date` |
| `confidence_min` | no | `low`, `nominal`, `high` | `low` | Minimum confidence (`low` = everything) |
| `daynight` | no | `D`, `N` | both | Day or night detections only |
| `instrument` | no | `MODIS`, `VIIRS` | both | One instrument only |
| `vegetation_only` | no | `true`/`false` (`1`/`0`, `yes`/`no`) | `false` | Drop volcanoes, static sources and offshore (keeps unknown type) |
| `limit` | no | 1…50000 | 10000 | Maximum hotspots in this response |
| `offset` | no | ≥ 0 | 0 | Hotspots to skip (pagination) |
| `format` | no | `geojson`, `json` | `geojson` | Output format |

Dates must lie between `2000-11-01` (start of MODIS) and today in UTC.
Enum values are case-insensitive (`instrument=viirs` works). Unknown parameters are ignored.

### Example: GeoJSON (default)

```bash
curl "http://localhost:5000/api/v1/hotspots?lat1=21.7&lon1=-90.4&lat2=19.5&lon2=-87.4&start_date=2013-04-01&end_date=2013-04-30&limit=1"
```

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [-89.4455, 20.26711] },
      "properties": {
        "acquired_at": "2013-04-01T08:11:00Z",
        "instrument": "VIIRS",
        "satellite": "SNPP",
        "daynight": "N",
        "frp": 0.98,
        "confidence": "nominal",
        "fire_type": 0
      }
    }
  ],
  "metadata": {
    "bbox": [-90.4, 19.5, -87.4, 21.7],
    "start_date": "2013-04-01",
    "end_date": "2013-04-30",
    "returned": 1,
    "limit": 1,
    "offset": 0,
    "truncated": true
  }
}
```

Remember: GeoJSON coordinates are **`[longitude, latitude]`** (x, y), and `bbox` is
`[min_lon, min_lat, max_lon, max_lat]`.

### Example: plain JSON with every column

```bash
curl "http://localhost:5000/api/v1/hotspots?lat1=18&lon1=-100&lat2=20&lon2=-98&start_date=2024-04-01&end_date=2024-04-30&format=json&instrument=VIIRS&confidence_min=nominal"
```

```json
{
  "data": [
    {
      "latitude": 19.0, "longitude": -99.0,
      "acquired_at": "2024-04-15T19:42:00Z", "acq_date": "2024-04-15",
      "instrument": "VIIRS", "satellite": "NOAA-20", "source": "VIIRS_NOAA20_SP",
      "daynight": "D", "bright_mir": 330.0, "bright_tir": 295.0, "frp": 12.4,
      "pixel_scan": 0.4, "pixel_track": 0.4,
      "confidence": "nominal", "confidence_raw": "n",
      "fire_type": 0, "version": "2"
    }
  ],
  "metadata": { "bbox": [-100.0, 18.0, -98.0, 20.0], "start_date": "2024-04-01", "end_date": "2024-04-30",
                "returned": 1, "limit": 10000, "offset": 0, "truncated": false }
}
```

### Example: nothing found (still HTTP 200)

```bash
curl "http://localhost:5000/api/v1/hotspots?lat1=40&lon1=0&lat2=41&lon2=1&start_date=2013-04-01&end_date=2013-04-30"
```

```json
{
  "type": "FeatureCollection",
  "features": [],
  "metadata": { "bbox": [0.0, 40.0, 1.0, 41.0], "start_date": "2013-04-01", "end_date": "2013-04-30",
                "returned": 0, "limit": 10000, "offset": 0, "truncated": false },
  "message": "No data found in the selected area"
}
```

`message` appears **only** when the list is empty. The behavior is identical for any place on Earth.

### Example: next page

If `metadata.truncated` is `true`, ask for the next page with `offset = offset + limit`:

```bash
curl "http://localhost:5000/api/v1/hotspots?lat1=14&lon1=-118&lat2=33&lon2=-86&start_date=2013-04-01&end_date=2013-04-30&limit=10000&offset=10000"
```

---

## `GET /api/v1/calendar`

The **burning activity calendar** of an area: how many hotspots were detected in each
month of every year the database holds. The frontend draws it as a year × month heatmap.

Counting happens inside DuckDB (`GROUP BY year, month`), so the answer is small (12 rows
per year) even when the area has millions of detections, and it never truncates.

### Parameters

| Name | Required | Values | Default | Meaning |
|---|---|---|---|---|
| `lat1`, `lon1`, `lat2`, `lon2` | yes | same as `/hotspots` | | Rectangle corners, any order |
| `confidence_min`, `daynight`, `instrument`, `vegetation_only` | no | same as `/hotspots` | | Same filters as `/hotspots` |
| `harmonized` | no | `true` / `false` | `false` | One continuous series in MODIS Terra+Aqua units (see below). Cannot be combined with `instrument`, `daynight` or `confidence_min` (400) |

There are **no dates**: the calendar always covers every loaded month, so the user can
compare the whole history of the area.

### Example

```bash
curl "http://localhost:5000/api/v1/calendar?lat1=14&lon1=-118&lat2=33&lon2=-86"
```

```json
{
  "bbox": [-118.0, 14.0, -86.0, 33.0],
  "coverage": { "start_date": "2013-01-01", "end_date": "2014-01-01" },
  "harmonized": false,
  "total": 367064,
  "months": [
    { "year": 2013, "month": 1, "count": 8149, "modis": 0, "viirs": 8149, "partial": false },
    "... one entry per month ...",
    { "year": 2014, "month": 1, "count": 75, "modis": 0, "viirs": 75, "partial": true }
  ],
  "years": [
    { "year": 2013, "count": 366989, "partial": false },
    { "year": 2014, "count": 75, "partial": true }
  ],
  "monthly_median": [8149.0, 17159.0, 41000.0, 93425.0, 137172.0, 41407.0,
                     6381.0, 5286.0, 2348.0, 4413.0, 4079.0, 6170.0]
}
```

How to read it:

- **`coverage`** is the first and last day loaded in the database (for one instrument if
  `instrument` is set), or `null` when the database is empty.
- **`months`** has *every* month inside `coverage`, including months with `count: 0`.
  A month that is **missing** means "no data loaded", while `0` means "observed, no fires".
- **`partial: true`** means the coverage cuts the month (here only 1 January 2014 is
  loaded). Its count is real but not comparable with full months.
- **`modis` / `viirs`** split each count by instrument.
- **`years`**: total per year; `partial` when any month of that year is missing or partial.
- **`monthly_median[i]`** is the median count of month `i + 1` (index 0 = January) over the
  **full** months only, or `null` if there is none. It is the "normal" level to compare the
  current month against. The median is used rather than the mean so one extreme year does
  not shift the reference.
- **`harmonized`** is `false`: counts are raw detections (use `instrument` to keep one sensor;
  MODIS and VIIRS raw counts are not comparable).
- If the area has no hotspots at all, `total` is 0, the months are still listed with zeros,
  and `"message": "No data found in the selected area"` is added.

### Harmonized calendar (`harmonized=true`)

```bash
curl "http://localhost:5000/api/v1/calendar?lat1=14&lon1=-118&lat2=33&lon2=-86&harmonized=true"
```

Same shape, but `count` is the **harmonized value** (MODIS Terra+Aqua units, one decimal,
vegetation fires only) and each month adds where it comes from (method in
[harmonization.md](harmonization.md)):

```json
{ "year": 2012, "month": 3, "count": 3778.6, "modis": 3756, "viirs": 16338, "partial": false,
  "source": "average", "modis_eq": 3801.2, "terra": 1698, "aqua": 2058,
  "viirs_day": 12527, "viirs_night": 3811, "low_count": false }
```

- `source`: `terra_scaled` (Terra × factor, before Aqua), `modis`, `average` (MODIS and VIIRS
  converted), `viirs_eq` (VIIRS converted, no MODIS).
- `modis_eq`: VIIRS converted to MODIS units (`null` when VIIRS is not used that month).
- `low_count`: the value is below the reliable monthly count (error > ~30 %).
- A `harmonization` block gives the ratios (`r_day`, `r_night`, `r_total`), `terra_factor`,
  `k_frp`, `fit_period`, `fit_detections`, `cutoffs` and `reliability`
  (`area_deg2`, `small_area` when under 1 deg², `typical_month`, `low_count`, `low_count_months`).

---

## `GET /api/v1/dataset`

Summary of everything in the database. The frontend uses it to limit its date pickers
and to set the initial map view.

```bash
curl http://localhost:5000/api/v1/dataset
```

```json
{
  "total_records": 367064,
  "min_date": "2013-01-01",
  "max_date": "2014-01-01",
  "instruments": { "VIIRS": 367064 },
  "bbox": [-117.10352, 14.49439, -86.84244, 32.79351]
}
```

For an empty table: `total_records` is 0, the dates and `bbox` are `null`, and `instruments` is `{}`.

---

## `GET /health`

```bash
curl -i http://localhost:5000/health
```

| Situation | Status | Body |
|---|---|---|
| Database opened and queryable | 200 | `{"status": "ok", "database": "connected"}` |
| File missing, locked or without `hotspots` table | 503 | `{"status": "error", "database": "unavailable"}` |

---

## Errors

All errors share one shape:

```json
{ "error": { "code": "INVALID_PARAMETER", "message": "Invalid value for 'lat1': ...", "parameter": "lat1" } }
```

| Status | `code` | When |
|---|---|---|
| 400 | `INVALID_PARAMETER` | Missing or invalid parameter; `parameter` names it |
| 404 | `NOT_FOUND` | Unknown URL |
| 405 | `METHOD_NOT_ALLOWED` | e.g. `POST` to a `GET` endpoint |
| 503 | `DATABASE_UNAVAILABLE` | The database file cannot be opened |
| 500 | `INTERNAL_ERROR` | Unexpected bug (details are only in the server log) |

Examples of 400 messages:

```text
Missing required parameter 'lat1'
Invalid value for 'lat1': Input should be less than or equal to 90  (or: 'lat1' must be a latitude between -90 and 90)
The rectangle has zero height: 'lat1' and 'lat2' must differ
'end_date' must be the same as or later than 'start_date'
Invalid value for 'start_date': must be a date in YYYY-MM-DD format
Invalid value for 'limit': must be between 1 and 50000
```
