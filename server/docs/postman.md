# Testing the API with Postman

[Postman](https://www.postman.com/downloads/) is a free app for sending HTTP requests and
reading the answers, without writing code. This guide shows how to try every endpoint.

**Before you start:** the API must be running (see [running.md](running.md)).
Open <http://localhost:5000/health> in a browser: if you see `"status": "ok"`, you are ready.
Using Postman on a **different computer** from the API? Replace `localhost` with the API's LAN address
everywhere in this guide (for example `http://192.168.1.23:5000`).

## Fastest way: import the ready-made collection

We ship a Postman **collection** (a saved list of requests) with every endpoint, the common
error cases and automatic checks:

```text
server/docs/postman/hotspots-api.postman_collection.json
```

1. Open Postman and click **Import** (top-left).
2. Drag the file above into the window, or click **files** and select it.
3. A collection named **Hotspots API** appears in the left sidebar.
4. Open any request and click **Send**.

The collection uses a variable called `baseUrl` (default `http://localhost:5000`). Change it when:

- **Postman runs on another computer** than the API: use the `Network:` address printed when the API
  starts, e.g. `http://192.168.1.23:5000` (see [running.md](running.md#using-the-api-from-other-devices-lan)).
- **The API uses another port**, e.g. `http://localhost:5001`.

To change it: click the collection → **Variables** tab → edit `baseUrl` → **Save**. Every request uses it.

### Run all requests at once

Click the **⋯** next to the collection → **Run collection** → **Run Hotspots API**.
Each request has small automatic checks (called *tests*), for example "status is 200" or
"coordinates are [lon, lat]". A green **PASS** means the API behaves as documented.

The checks expect the **real data** (`fire_archive_SV-C2_849193.json`, Mexico 2013). With fake
data, the "Hotspots: Yucatán" checks may still pass, but the exact numbers will differ.
The **Calendar (monthly counts)** request checks the shape of the calendar (12 monthly
medians, total = sum of the months), so it passes with any data. **Calendar, harmonized**
checks `harmonized: true`, the `harmonization` block and that every month has a `source`; the
Errors folder has **Harmonized with instrument** (400, `parameter: instrument`).

The **Stats (dashboard)** folder has one request per `/api/v1/stats/*` endpoint (Durango, 2013),
an empty-area case and three 400 cases. Its checks only look at the shape of the answer
(fields, `message`, error `parameter`), so they pass with any data that has detections in
Durango in 2013. What each endpoint returns: [dashboard-api.md](dashboard-api.md).

The **Machine Learning** folder checks the model's supported input categories, the saved
evaluation report, and a prediction using the example record. It requires the default model
artifacts in `server/model_artifacts/`; the prediction check confirms all three normalized
probabilities sum to 1.

## Doing it by hand (to understand what is happening)

### 1. Your first request: health

1. Click **New → HTTP** (or the **+** tab).
2. Leave the method as **GET**.
3. Type the URL: `http://localhost:5000/health`
4. Click **Send**.

At the bottom you will see the **status** (`200 OK`) and the **body**:

```json
{ "status": "ok", "database": "connected" }
```

### 2. What data is loaded: dataset

`GET http://localhost:5000/api/v1/dataset`

```json
{
  "total_records": 367064,
  "min_date": "2013-01-01",
  "max_date": "2014-01-01",
  "instruments": { "VIIRS": 367064 },
  "bbox": [-117.10352, 14.49439, -86.84244, 32.79351]
}
```

This tells you which dates are worth asking for. Asking for 2020 with this data gives an empty result.

### 3. Searching hotspots

URL: `http://localhost:5000/api/v1/hotspots`

Instead of typing a long URL, open the **Params** tab and fill the table. Postman builds the URL for you:

| Key | Value | Meaning |
|---|---|---|
| `lat1` | `21.7` | Latitude of one corner |
| `lon1` | `-90.4` | Longitude of the same corner |
| `lat2` | `19.5` | Latitude of the opposite corner |
| `lon2` | `-87.4` | Longitude of the opposite corner |
| `start_date` | `2013-04-01` | First day (included) |
| `end_date` | `2013-04-30` | Last day (included) |
| `limit` | `5` | Return only 5 hotspots (keeps the answer short) |

That box covers the Yucatán peninsula:

```text
 (lat1=21.7, lon1=-90.4) ●───────────────┐
                         │   Yucatán     │
                         │   peninsula   │
                         └───────────────● (lat2=19.5, lon2=-87.4)
```

Click **Send**. You get a GeoJSON `FeatureCollection`:

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
    "start_date": "2013-04-01", "end_date": "2013-04-30",
    "returned": 5, "limit": 5, "offset": 0, "truncated": true
  }
}
```

How to read it:
- Each **feature** is one hotspot. `coordinates` are **[longitude, latitude]** (this is the GeoJSON rule, x before y).
- `acquired_at` is in **UTC** (`Z` at the end). 08:11 UTC is 02:11 in Mexico City.
- `truncated: true` means there are **more** hotspots than `limit`. To see the next 5, set `offset` to `5`, then `10`, and so on.

### 4. Try the optional filters

Add rows in **Params** (or tick/untick them to switch them on and off):

| Key | Try | Effect |
|---|---|---|
| `format` | `json` | Plain JSON with every column instead of GeoJSON |
| `confidence_min` | `high` | Only the detections the satellite is most sure about |
| `daynight` | `N` | Only night detections (`D` for day) |
| `instrument` | `VIIRS` | Only one instrument (`MODIS` or `VIIRS`) |
| `vegetation_only` | `true` | Drop volcanoes, industrial heat sources and offshore platforms |

See [filtering.md](filtering.md) for exactly how each one works.

### 5. See an empty result

Change the box to a place with no data, for example Spain: `lat1=40`, `lon1=0`, `lat2=41`, `lon2=1`.

You still get **200 OK** (the question was valid), with an empty list and a message:

```json
{
  "type": "FeatureCollection",
  "features": [],
  "metadata": { "returned": 0, "truncated": false, "...": "..." },
  "message": "No data found in the selected area"
}
```

### 6. See the error messages

Break a parameter on purpose and read the **400 Bad Request** answer:

| Change | Message you get |
|---|---|
| Untick `lat1` | `Missing required parameter 'lat1'` |
| `lat1` = `100` | `Invalid value for 'lat1': ...` (latitude must be between −90 and 90) |
| `lat2` = same as `lat1` | `The rectangle has zero height: 'lat1' and 'lat2' must differ` |
| `end_date` before `start_date` | `'end_date' must be the same as or later than 'start_date'` |
| `start_date` = `01/04/2013` | `Invalid value for 'start_date': must be a date in YYYY-MM-DD format` |
| Method **POST** instead of GET | `405`, `METHOD_NOT_ALLOWED` |

Every error has the same shape, so it is easy to handle in the frontend:

```json
{ "error": { "code": "INVALID_PARAMETER", "message": "Missing required parameter 'lat1'", "parameter": "lat1" } }
```

## Tips

- **Save your requests:** click **Save** and put them in a collection so the team can reuse them.
- **Share with the team:** collection **⋯ → Export** creates a `.json` file anyone can import.
- **Large answers:** without `limit`, a big box can return up to 10,000 hotspots. Postman handles it, but
  it is slow to scroll. Use `limit=5` while exploring.
- **"Could not send request" / connection refused from another computer?** It is a network issue, not the API:
  see [If the other device cannot connect](running.md#if-the-other-device-cannot-connect).
- **Status 503 everywhere?** The API cannot open the database. Check [running.md](running.md#troubleshooting).
- **Prefer the terminal?** Every request here also has a `curl` version in [api.md](api.md).
