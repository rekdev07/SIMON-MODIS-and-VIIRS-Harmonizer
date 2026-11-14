# How the data is imported

The API only **reads** a DuckDB file. That file is built by `scripts/import_json.py`
from a FIRMS JSON export:

```bash
# from server/, with the API stopped
python scripts/import_json.py data/raw/fire_archive_SV-C2_849193.json --db data/hotspots.duckdb
```

```
raw JSON ──► 1. inspect ──► 2. normalize each record ──► 3. reject / deduplicate ──► 4. insert ──► summary
```

The importer can be run again with new files: rows already in the database are skipped.
Stop the API first, because DuckDB does not let another process write to a file the API
has open.

## 1. Inspection

The script first detects the file's structure and prints every field name with how many
records contain it. Accepted layouts:

- a JSON list of records: `[ {...}, {...} ]` (the FIRMS archive download);
- an object wrapping the list: `{"data": [...]}` (also `records`, `hotspots`, `items`, `results`);
- a GeoJSON `FeatureCollection` (coordinates are taken from the geometry);
- newline-delimited JSON (one record per line).

Records can be **raw FIRMS** or **already normalized** (the schema below).

What we found in `fire_archive_SV-C2_849193.json`: a list of 367,064 records, all with
the same 15 fields (`latitude, longitude, acq_date, acq_time, satellite, daynight,
brightness, bright_t31, type, version, confidence, scan, track, instrument, frp`). They are
all VIIRS on Suomi NPP from 2013-01-01 to 2014-01-01, and `instrument` wrongly says `"SNPP"`.

## 2. Field mapping

| Raw FIRMS field(s) | Column | Notes |
|---|---|---|
| `latitude`, `longitude` | `latitude`, `longitude` | numbers or numeric strings |
| `acq_date` + `acq_time` | `acquired_at` | UTC; `acq_time` padded to 4 digits |
| (derived) | `acq_date` | UTC day of `acquired_at` |
| (deduced, see below) | `instrument` | `MODIS` / `VIIRS` |
| `satellite` | `satellite` | codes translated, see below |
| `source` | `source` | NULL when the file does not say |
| `daynight` | `daynight` | `D` / `N` (anything else → NULL) |
| `brightness` (MODIS) or `bright_ti4` (VIIRS) | `bright_mir` | ~4 µm brightness temperature, K |
| `bright_t31` (MODIS), `bright_ti5` (VIIRS) or `brightness_2` | `bright_tir` | ~11 µm brightness temperature, K |
| `frp` | `frp` | MW, NULL if missing |
| `scan` | `pixel_scan` | km |
| `track` | `pixel_track` | km |
| `confidence` | `confidence` + `confidence_raw` | see below |
| `type` | `fire_type` | integer or NULL |
| `version` | `version` | text |

Numbers that arrive as text are converted: `"2"` → `2`, `"19.5"` → `19.5`.

### Time padding

FIRMS stores the time as `HHMM`, but leading zeros are often lost: `757` means **07:57**.
The importer left-pads with zeros to 4 digits:

```
"757" → "0757" → 07:57      "5" → "0005" → 00:05      "1930" → 19:30
```

`acquired_at = acq_date + HH:MM`, for example `2013-01-01` + `0757` → `2013-01-01 07:57:00 UTC`.

## 3. Confidence rule

The two instruments express confidence differently. Both are mapped to the same three words:

| Instrument | Raw value | Category |
|---|---|---|
| MODIS | number < 30 | `low` |
| MODIS | 30 ≤ number < 80 | `nominal` |
| MODIS | number ≥ 80 | `high` |
| VIIRS | `l` | `low` |
| VIIRS | `n` | `nominal` |
| VIIRS | `h` | `high` |

The original value is always kept in `confidence_raw` (`"67"`, `"n"`), so no information is lost.
An unreadable confidence becomes NULL, and the record is still stored.

## 4. Instrument rule (the raw `instrument` field is not trusted)

Some FIRMS exports put the **satellite** in `instrument` (our file says `"SNPP"`). So the
instrument is **deduced**:

```
1. satellite is Terra or Aqua               → MODIS
   satellite is SNPP, NOAA-20 or NOAA-21    → VIIRS
2. otherwise: confidence is a number        → MODIS
              confidence is l / n / h       → VIIRS
3. otherwise: raw instrument literally "MODIS" or "VIIRS" → use it
4. otherwise: reject the record (reason unknown_instrument)
```

## 5. Satellites

| Code in file | Stored as |
|---|---|
| `T`, `Terra` | `Terra` (MODIS) |
| `A`, `Aqua` | `Aqua` (MODIS) |
| `N`, `SNPP`, `NPP` | `SNPP` (VIIRS) |
| `N20`, `1`, `NOAA-20`, `J1` | `NOAA-20` (VIIRS) |
| `N21`, `NOAA-21`, `J2` | `NOAA-21` (VIIRS) |
| anything else | **kept as-is**, reported in the log and the summary |

## 6. `fire_type`: NULL is not 0

| Value | Meaning |
|---|---|
| 0 | presumed vegetation fire |
| 1 | active volcano |
| 2 | other static land source |
| 3 | offshore |
| NULL | **missing in the source** |

If `type` is missing, `fire_type` is **NULL, never 0**. Writing 0 would claim "this is a
vegetation fire" without evidence. The API's `vegetation_only` filter relies on this
distinction (see [filtering.md](filtering.md)).

## 7. Rejections

A record is **not stored** (and is logged) when it cannot be placed in space and time:

| Reason | Example |
|---|---|
| `missing_coordinates` | no `latitude` or `longitude` |
| `invalid_coordinates` | `"latitude": "abc"` |
| `out_of_range_coordinates` | latitude 95, longitude −190 |
| `missing_date` / `invalid_date` | no `acq_date`, or `2013-13-01` |
| `missing_time` / `invalid_time` | no `acq_time`, or `2575` |
| `missing_satellite` | no `satellite` (it is part of the unique key) |
| `unknown_instrument` | the instrument cannot be deduced (see rule above) |

The first 20 examples of each reason are logged as warnings. Use `-v` to log all of them.

## 8. Duplicates

A hotspot is identified by `(instrument, satellite, latitude, longitude, acquired_at)`,
which is the table's primary key. Duplicates are skipped in two places:

- **inside the file**: the first occurrence wins;
- **against the database**: `INSERT ... ON CONFLICT DO NOTHING`, so re-importing the same file
  inserts 0 rows.

## 9. Summary

At the end the script prints something like:

```
=== Import summary ===
Database:            data/hotspots.duckdb
Records read:        367064
Inserted:            367064
Rejected:            0
Duplicates skipped:  0 (in file: 0, already in DB: 0)
Date range (UTC):    2013-01-01 -> 2014-01-01
Valid records per instrument:
  - VIIRS: 367064
```

## Fake data

`python scripts/generate_mock_data.py --db data/mock_hotspots.duckdb` creates about 200,000
realistic fake hotspots over Mexico: MODIS 2001–today, VIIRS 2012–today, an April–June peak,
and some NULL `frp`/`fire_type`. Point the API at it with
`HOTSPOTS_DB_PATH=data/mock_hotspots.duckdb`. Use `--overwrite` to regenerate it.
