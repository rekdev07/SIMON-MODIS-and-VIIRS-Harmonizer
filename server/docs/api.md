# API reference

Base URL when running locally: `http://localhost:5000`. All responses are JSON and all
messages are in English. There is no authentication.

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
