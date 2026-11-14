# AGENTS.md: Hotspots API (server/)

This file holds everything an agent or a person needs to build and maintain this
backend. Read it before changing anything in `server/`.

## 1. Context

- Event: NASA Space Apps Challenge 2026, challenge "Harmonization of MODIS and VIIRS Hot Spots".
- This is a **simple, read-only REST API** that serves fire hotspots detected by the
  MODIS and VIIRS satellite instruments (NASA FIRMS data).
- The user sends a **rectangle** (two corners) and a **date range**. The API returns the
  hotspots inside that rectangle and those dates.
- The API only reads a local DuckDB database. It does **not** download FIRMS data,
  does **not** harmonize sensors and has **no** authentication.

### Monorepo

```
SIMON-MODIS-and-VIIRS-Harmonizer/
├─ client/             React + Vite + Tailwind frontend (dev server http://localhost:5173). NOT part of this API. Do not modify.
└─ server/             this backend (all work happens here)
   └─ harmonizer/      placeholder for harmonization logic. NOT part of this API. Do not modify.
```

All paths below are relative to `server/`. Run every command (`pip`, `python`,
`pytest`, `flask`) from inside `server/`.

## 2. Stack (closed decisions, do not change)

| Concern | Choice |
|---|---|
| Language | Python **>= 3.12** (`requires-python = ">=3.12"`) |
| Dependencies | **pip** only: `requirements.txt` (prod), `requirements-dev.txt` (tests). No Poetry/uv/conda. |
| Web framework | **Flask**, application factory `create_app()` |
| Database | **DuckDB** local file, opened **read-only** by the API |
| Validation | **Pydantic v2**, called explicitly inside the endpoints |
| CORS | **flask-cors**, origins from `CORS_ORIGINS` env var |
| Config | environment variables + `.env` (python-dotenv), template in `.env.example` |
| Tests | **pytest** + Flask test client |

## 3. Structure

```
server/
├─ AGENTS.md / CLAUDE.md     agent instructions (this file + short summary)
├─ app/
│  ├─ __init__.py            create_app(): config, CORS, error handlers, blueprints
│  ├─ config.py              Settings loaded from environment variables
│  ├─ db.py                  read-only DuckDB connection + one cursor per request
│  ├─ schemas.py             Pydantic models: query params and response metadata
│  ├─ geo.py                 rectangle normalization and validation (pure functions)
│  ├─ repository.py          table DDL + parameterized SQL queries
│  ├─ serializers.py         rows -> GeoJSON / JSON
│  ├─ errors.py              API exceptions + global Flask error handlers
│  └─ routes/
│     ├─ hotspots.py         GET /api/v1/hotspots
│     └─ meta.py             GET /api/v1/dataset, GET /health
├─ scripts/
│  ├─ import_json.py         raw FIRMS JSON -> normalized DuckDB table
│  └─ generate_mock_data.py  fake but realistic Mexico hotspots
├─ docs/                     plain-language docs (api, filtering, dates, data-import)
├─ tests/                    pytest suite with its own small known dataset
├─ data/                     GITIGNORED: data/raw/*.json and *.duckdb files
├─ .env.example, requirements*.txt, pyproject.toml, run.py, README.md
└─ harmonizer/               out of scope, do not modify
```

Layering: `routes` → (`schemas`, `geo`) for validation → `repository` for SQL →
`serializers` for output. Routes contain no SQL. The repository contains no Flask code.

## 4. Code conventions

- **Everything in English**: identifiers, comments, docstrings, API messages.
- **Google-style docstrings** on every module, class and function (`Args:`, `Returns:`,
  `Raises:`, `Example:`), compatible with pydoc (`python -m pydoc app.geo` must work).
- Docstrings explain **what**, **how** and **why**. Explain every formula: min/max
  normalization of corners, inclusive comparisons, date → UTC day ranges, `limit + 1`
  truncation detection, MODIS numeric confidence → category, etc.
- Inline comments only where the logic is not obvious.
- Full type hints (`from __future__ import annotations` is fine).
- **SQL is always parameterized** (`?` placeholders). Never interpolate user values into SQL.
  Only fixed SQL fragments chosen by code may be joined together.
- Keep it simple: no ORM, no extra frameworks.

## 5. Data schema: table `hotspots`

| Field | Type | Notes |
|---|---|---|
| latitude | DOUBLE | WGS84 |
| longitude | DOUBLE | WGS84 |
| acquired_at | TIMESTAMP | UTC (naive timestamp that is always UTC) |
| acq_date | DATE | `acquired_at` date in UTC, used for date filtering |
| instrument | VARCHAR | `MODIS` or `VIIRS` |
| satellite | VARCHAR | `Terra`, `Aqua`, `SNPP`, `NOAA-20`, `NOAA-21` (unknown codes kept as-is) |
| source | VARCHAR | e.g. `MODIS_SP`, `VIIRS_NOAA20_NRT`; NULL if unknown |
| daynight | VARCHAR | `D` or `N` |
| bright_mir | DOUBLE | mid-infrared (~4 µm) brightness temperature, K |
| bright_tir | DOUBLE | thermal infrared (~11 µm) brightness temperature, K |
| frp | DOUBLE NULL | fire radiative power, MW |
| pixel_scan | DOUBLE | km |
| pixel_track | DOUBLE | km |
| confidence | VARCHAR | `low`, `nominal`, `high` |
| confidence_raw | VARCHAR | original value (`"67"` or `"n"`) |
| fire_type | INTEGER NULL | 0 vegetation, 1 volcano, 2 static land source, 3 offshore; NULL if missing |
| version | VARCHAR | FIRMS product version |

Primary key: `(instrument, satellite, latitude, longitude, acquired_at)`.
The DDL lives in `app/repository.py` (`HOTSPOTS_TABLE_DDL`, `create_hotspots_table()`)
and is shared by the importer, the mock generator and the tests.

## 6. Data import rules (`scripts/import_json.py`)

Usage: `python scripts/import_json.py data/raw/fire_archive_SV-C2_849193.json --db data/hotspots.duckdb`

- Inspects the file first. Accepted inputs: a JSON list of records, an object wrapping a
  list (`data`/`records`/`hotspots`/`features`), GeoJSON features, or NDJSON. Records may be
  raw FIRMS or already in the normalized schema.
- `acquired_at = acq_date + acq_time` (UTC); `acq_time` is zero-padded to 4 digits (`757` → `0757`).
- `brightness`/`bright_ti4` → `bright_mir`; `bright_t31`/`bright_ti5`/`brightness_2` → `bright_tir`;
  `scan` → `pixel_scan`; `track` → `pixel_track`; `type` → `fire_type`.
- Confidence: MODIS numeric 0–100: `<30` low, `30–79` nominal, `>=80` high. VIIRS `l`/`n`/`h`
  → low/nominal/high. The original always goes to `confidence_raw`.
- **Never trust raw `instrument`** (it is sometimes "SNPP"). Deduce: satellite Terra/Aqua or numeric
  confidence → MODIS; satellite SNPP/NOAA-* or `l`/`n`/`h` confidence → VIIRS. Raw `instrument`
  is only a last resort when it literally says MODIS or VIIRS.
- Satellites: `T`→Terra, `A`→Aqua, `N`→SNPP, `N20`/`1`→NOAA-20, `N21`→NOAA-21; unknown codes kept and logged.
- Missing `type` → `fire_type = NULL`, **never 0** (0 means vegetation fire).
- Numeric strings are converted (`"2"` → `2`).
- Reject (log, do not store) records missing latitude/longitude/date/time, with non-numeric or
  out-of-range coordinates, or with an unparseable date/time.
- Duplicates (same primary key) are skipped, both inside the file and against existing rows.
- Ends with a summary: read, inserted, rejected by reason, duplicates, date range, count per instrument.
- The API must be **stopped** while importing (DuckDB allows one writer and no readers from other processes).

## 7. Endpoints and filtering rules

### `GET /api/v1/hotspots`

| Param | Required | Rule |
|---|---|---|
| `lat1`,`lon1`,`lat2`,`lon2` | yes | corners in any order; lat ∈ [-90, 90], lon ∈ [-180, 180] |
| `start_date`,`end_date` | yes | `YYYY-MM-DD`, both inclusive, `start <= end`, within [2000-11-01, today UTC] |
| `confidence_min` | no | `low` (default, all) / `nominal` / `high` |
| `daynight` | no | `D` / `N` (default both) |
| `instrument` | no | `MODIS` / `VIIRS` (default both) |
| `vegetation_only` | no | bool, default false; excludes `fire_type` 1, 2, 3, **keeps NULL** |
| `limit` | no | default 10000, max 50000 (`DEFAULT_LIMIT`, `MAX_LIMIT`) |
| `offset` | no | default 0 |
| `format` | no | `geojson` (default) / `json` |

- Corners → `min_lat = min(lat1, lat2)`, `max_lat = max(...)`, same for longitude.
- Rectangle must be non-degenerate: width > 0 and height > 0.
- Assumption: the rectangle does **not** cross the antimeridian (±180°).
- SQL: `latitude BETWEEN ? AND ?`, `longitude BETWEEN ? AND ?`, `acq_date BETWEEN ? AND ?` (inclusive).
- Order: `acquired_at` ascending, with the rest of the primary key as tie-breaker (stable pagination).
- Truncation: fetch `limit + 1` rows; if more than `limit` came back, `truncated = true` and the extra row is dropped.
- No coverage regions and no validation by state or country: same behavior anywhere in the world.

### Response format

GeoJSON (default): `FeatureCollection`, coordinates `[longitude, latitude]`, properties
`acquired_at` (ISO-8601 with `Z`), `instrument`, `satellite`, `daynight`, `frp`, `confidence`, `fire_type`.
`format=json`: `{"data": [full records], "metadata": {...}}`.
`metadata`: `bbox [min_lon, min_lat, max_lon, max_lat]`, `start_date`, `end_date`, `returned`,
`limit`, `offset`, `truncated`.
No results → **HTTP 200**, empty list, and `"message": "No data found in the selected area"`.
The `message` key appears **only** when there are no results.

### `GET /api/v1/dataset`
Total records, min/max `acq_date`, count per instrument, bbox of all data (for frontend date pickers).

### `GET /health`
`200 {"status": "ok", "database": "connected"}` or `503 {"status": "error", "database": "unavailable"}`.

### Errors
`{"error": {"code": "...", "message": "..."}}` (plus `"parameter"` for invalid parameters).
400 `INVALID_PARAMETER`; 404 `NOT_FOUND`; 405 `METHOD_NOT_ALLOWED`; 503 `DATABASE_UNAVAILABLE`;
500 `INTERNAL_ERROR` (never expose stack traces). All messages in English.

## 8. Database connection

- One read-only `duckdb.connect(path, read_only=True)` per app, opened at startup
  (retried lazily on requests if the file was missing at startup).
- One `connection.cursor()` per request (stored in `flask.g`, closed on teardown).
  A DuckDB connection must not be used by several threads at once; a cursor is a cheap
  duplicate connection to the same database, so each request thread gets its own.
- Path from `HOTSPOTS_DB_PATH` (default `data/hotspots.duckdb`, relative to `server/`).

## 9. Configuration (`.env.example`)

`HOTSPOTS_DB_PATH`, `CORS_ORIGINS` (default `http://localhost:5173,http://localhost:3000`),
`DEFAULT_LIMIT` (10000), `MAX_LIMIT` (50000), `API_HOST` (127.0.0.1), `API_PORT` (5000), `FLASK_DEBUG` (0).

## 10. Running

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/import_json.py data/raw/fire_archive_SV-C2_849193.json --db data/hotspots.duckdb
# or: python scripts/generate_mock_data.py --db data/mock_hotspots.duckdb
python run.py                    # or: flask --app app run
pytest                           # tests use their own data from tests/conftest.py
python -m pydoc app.geo          # code docs
```

## 11. Tests

- Tests never use the real JSON or `data/`. `tests/conftest.py` builds a small known database
  in a temp directory.
- Required coverage: reversed corners, inclusive edges, empty result + exact message, no message
  with results, 400 cases (coords, degenerate rectangle, dates), limit/truncated,
  vegetation_only, confidence_min, daynight, instrument, GeoJSON `[lon, lat]`, `/health`
  with and without DB, import normalization (padding, confidence, satellites, type→NULL,
  rejections, duplicates).
- Every behavior change needs a test. Run `pytest` before finishing.

## 12. Documentation rules

- `docs/` is written for people who know nothing about the project or satellites:
  concrete examples and text diagrams. Update `docs/` and this file whenever behavior changes.
- `README.md` covers install, data loading, running, tests, pydoc and curl examples.

## 13. Out of scope

Downloading from FIRMS; harmonization/calibration between sensors (`harmonizer/`);
coverage regions or state/country validation; authentication; free-form polygons;
calendar and anomaly endpoints (later); any change to `client/` or `harmonizer/`.
Never commit `data/` (raw JSON, `.duckdb`).
