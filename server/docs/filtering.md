# How hotspots are filtered

A request selects hotspots in three steps:

```
   all hotspots in the database
        │  1. inside the rectangle?   (latitude and longitude)
        │  2. inside the dates?       (acq_date, see dates.md)
        │  3. pass the optional filters?  (confidence, day/night, instrument, vegetation)
        ▼
   sorted by time ──► page of `limit` rows starting at `offset`
```

## 1. Two corners in any order become a rectangle

You give two opposite corners: `(lat1, lon1)` and `(lat2, lon2)`. A user may drag the
mouse from top-left to bottom-right, or from bottom-right to top-left. Both must give
the same area, so the API does not care which corner is which. It computes:

```
min_lat = min(lat1, lat2)      max_lat = max(lat1, lat2)
min_lon = min(lon1, lon2)      max_lon = max(lon1, lon2)
```

**Numeric example.** `lat1=20, lon1=-98, lat2=18, lon2=-100`:

```
min_lat = min(20, 18)    = 18        max_lat = max(20, 18)    = 20
min_lon = min(-98, -100) = -100      max_lon = max(-98, -100) = -98

        lon -100            lon -98
lat 20     ┌───────────────────┐  ← (20, -98) was "corner 1"
           │                   │
           │    the selected   │
           │       area        │
lat 18     └───────────────────┘
           ↑ (18, -100) was "corner 2"
```

Swapping the corners gives exactly the same four numbers, so the same hotspots come back.

Validation:

- Latitude must be in [-90, 90] and longitude in [-180, 180].
- The rectangle cannot be flat: `lat1 = lat2` (zero height) or `lon1 = lon2` (zero width)
  is an error (HTTP 400). That nearly always means an accidental double click.

### Why the edges are inclusive

The SQL is `latitude BETWEEN min_lat AND max_lat AND longitude BETWEEN min_lon AND max_lon`.
`BETWEEN` includes both ends, so a hotspot lying **exactly on an edge or a corner is returned**.

Why: if you tile a map into neighbouring rectangles, a point on the shared border
appears in both tiles rather than in neither. Losing a fire is worse than seeing it twice.

### The antimeridian assumption

The rectangle is assumed **not to cross the ±180° longitude line** (the middle of the
Pacific). A request with `lon1=170, lon2=-170` is read as the wide box from −170 to 170,
not the narrow one across the date line. Mexico and the rest of the Americas are nowhere
near it, and this keeps the query a single simple `BETWEEN`.

## 2. Dates

`start_date` and `end_date` are whole UTC days, both included. See [dates.md](dates.md).

## 3. Optional filters

| Filter | Default | What it keeps |
|---|---|---|
| `confidence_min=low` | ✔ | every hotspot (no filter, even if confidence is unknown) |
| `confidence_min=nominal` | | `nominal` and `high` |
| `confidence_min=high` | | only `high` |
| `daynight=D` / `N` | both | only day / night detections |
| `instrument=MODIS` / `VIIRS` | both | only that instrument |
| `vegetation_only=true` | false | everything except `fire_type` 1, 2 and 3 |

Confidence is ordered `low < nominal < high`, so "minimum nominal" means "nominal or better".

### `fire_type` and why `vegetation_only` keeps NULL

| `fire_type` | Meaning | `vegetation_only=true` |
|---|---|---|
| 0 | presumed vegetation fire | kept |
| 1 | active volcano | removed |
| 2 | other static land source (gas flares, factories) | removed |
| 3 | offshore (oil platforms) | removed |
| NULL | **unknown**: the product did not say | **kept** |

NULL means "we don't know", not "not vegetation". FIRMS near-real-time products often have
no type at all, and most of those detections are vegetation fires. Dropping them would
hide real fires, so the filter only removes detections **known** to be something else:

```sql
fire_type IS NULL OR fire_type NOT IN (1, 2, 3)
```

## 4. Order, `limit`, `offset` and `truncated`

Results are sorted by `acquired_at` (oldest first). Ties are broken by instrument,
satellite, latitude and longitude, so the order is always the same and pages never overlap.

- `limit`: the maximum number of hotspots in one response (default 10000, maximum 50000).
- `offset`: how many hotspots of the sorted list to skip.
- `truncated`: `true` if more hotspots exist after this page.

How `truncated` is computed: the API asks the database for **`limit + 1`** rows. If it gets
`limit + 1` back, at least one more exists, so it drops the extra row and sets
`truncated: true`. This is much cheaper than counting every matching row.

```
matching rows:  r1 r2 r3 r4 r5        limit=2
offset=0  → asks for 3 → gets r1 r2 r3 → returns r1 r2, truncated=true
offset=2  → asks for 3 → gets r3 r4 r5 → returns r3 r4, truncated=true
offset=4  → asks for 3 → gets r5       → returns r5,    truncated=false
```

## 5. No results

A valid query that matches nothing is **not an error**. It returns HTTP 200 with an empty
list and:

```json
"message": "No data found in the selected area"
```

The same happens anywhere in the world. The API has no notion of "covered regions", states
or countries. If the database has no hotspots there, it says so. `message` is absent
whenever at least one hotspot is returned.
