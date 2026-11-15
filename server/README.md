# Hotspots API (server)

A small read-only REST API for the NASA Space Apps Challenge 2026 ("Harmonization of MODIS
and VIIRS Hot Spots"). Give it a rectangle and a date range, and it returns the fire hotspots
detected there by MODIS and VIIRS (NASA FIRMS data) from a local DuckDB database.
It lives in `server/`, next to the React frontend in `client/`.

## Requirements

- Python **3.12+**
- pip

## Installation (from `server/`)

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate.bat

pip install -r requirements.txt          # to run the API
pip install -r requirements-dev.txt      # + pytest, to run the tests
```

Optionally copy `.env.example` to `.env` and adjust it (database path, CORS origins, limits, port).

## Loading data

Real data (FIRMS JSON export, about 147 MB, not committed):

```bash
python scripts/import_json.py data/raw/fire_archive_SV-C2_849193.json --db data/hotspots.duckdb
```

Or fake data for development:

```bash
python scripts/generate_mock_data.py --db data/mock_hotspots.duckdb
# then run the API with HOTSPOTS_DB_PATH=data/mock_hotspots.duckdb
```

Stop the API while importing (DuckDB allows only one writer and no other open processes).

## Running the API

```bash
python run.py                # prints the Local and Network (LAN) addresses
# or
flask --app app run --host 0.0.0.0
```

The API listens on the local network by default, so teammates on the same Wi-Fi can use the
`Network:` address printed at startup (e.g. `http://192.168.1.23:5000`). Set `API_HOST=127.0.0.1`
in `.env` to keep it private to your computer. Details, firewall tips and frontend setup:
[docs/running.md](docs/running.md#using-the-api-from-other-devices-lan).

## Tests

```bash
pytest
```

The tests build their own small database and never use `data/`.

## Code documentation

Every module has Google-style docstrings readable with pydoc:

```bash
python -m pydoc app.geo
python -m pydoc app.repository
python -m pydoc app.stats_repository
python -m pydoc scripts.import_json
```

## Examples

```bash
# Health check
curl http://localhost:5000/health

# What data is loaded (date range, instruments, bbox)
curl http://localhost:5000/api/v1/dataset

# Hotspots in the Yucatán peninsula, April 2013 (GeoJSON)
curl "http://localhost:5000/api/v1/hotspots?lat1=21.7&lon1=-90.4&lat2=19.5&lon2=-87.4&start_date=2013-04-01&end_date=2013-04-30"

# Same, high-confidence night detections only, plain JSON, first 100
curl "http://localhost:5000/api/v1/hotspots?lat1=21.7&lon1=-90.4&lat2=19.5&lon2=-87.4&start_date=2013-04-01&end_date=2013-04-30&confidence_min=high&daynight=N&format=json&limit=100"

# An area with no data → 200 + "No data found in the selected area"
curl "http://localhost:5000/api/v1/hotspots?lat1=40&lon1=0&lat2=41&lon2=1&start_date=2013-04-01&end_date=2013-04-30"

# Dashboard statistics (Durango, 2013): KPIs per sensor, weekly series, FRP histogram
curl "http://localhost:5000/api/v1/stats/summary?lat1=22.3&lon1=-107.2&lat2=26.8&lon2=-102.5&start_date=2013-01-01&end_date=2013-12-31"
curl "http://localhost:5000/api/v1/stats/timeseries?freq=week&lat1=22.3&lon1=-107.2&lat2=26.8&lon2=-102.5&start_date=2013-01-01&end_date=2013-12-31"
curl "http://localhost:5000/api/v1/stats/distribution?field=frp&bins=20&log=true&lat1=22.3&lon1=-107.2&lat2=26.8&lon2=-102.5&start_date=2013-01-01&end_date=2013-12-31"
```

All 13 `/api/v1/stats/*` endpoints (one per group of dashboard charts) are described in
[docs/dashboard-api.md](docs/dashboard-api.md).

## More documentation

See [`docs/`](docs/README.md): [step-by-step setup](docs/running.md), [testing with Postman](docs/postman.md)
(collection in `docs/postman/`), [API reference](docs/api.md), [dashboard statistics](docs/dashboard-api.md), [filtering](docs/filtering.md),
[dates](docs/dates.md) and [data import](docs/data-import.md). Developer rules are in
[`AGENTS.md`](AGENTS.md).
