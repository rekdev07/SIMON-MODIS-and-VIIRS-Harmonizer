# SIMON: MODIS and VIIRS Hotspots Harmonizer

NASA Space Apps Challenge 2026, challenge **"Harmonization of MODIS and VIIRS Hot Spots"**.

SIMON shows fire hotspots (NASA FIRMS data) for an area you draw on a map of Mexico, and a
**burning activity calendar**: monthly hotspot counts from 2000 to today in one continuous,
harmonized series. VIIRS (375 m pixels) detects about 4× more hotspots than MODIS (1 km) over the
same fires, so VIIRS counts are converted to "MODIS Terra+Aqua units" with ratios fitted on the
years both sensors overlap. The method is explained in
[server/docs/harmonization.md](server/docs/harmonization.md).

```
SIMON-MODIS-and-VIIRS-Harmonizer/
├─ server/        Python API: Flask + DuckDB (http://localhost:5000)
│  └─ harmonizer/ harmonization math, fitting and validation
└─ client/        Web app: React + Vite + Leaflet (http://localhost:5173)
```

## Requirements

- **Python 3.12+** and pip
- **Node.js 20+** and npm (developed with Node 24)
- About 3 GB of free disk for the full datasets (database ≈ 1.4 GB)

## 1. Backend (`server/`)

```bash
cd server
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt  # API + pytest
cp .env.example .env                 # optional: database path, CORS, port, HARMONIZE_* settings
```

## 2. Load the data

The data is **not** in the repository (it is large). You need FIRMS archive downloads in JSON
format for your area, from <https://firms.modaps.eosdis.nasa.gov/download/>:

| Dataset | Covers | Approx. size (Mexico) |
|---|---|---|
| MODIS Collection 6.1 (Terra + Aqua), archive + NRT | Nov 2000 → today | ~0.7 GB JSON |
| VIIRS 375 m Suomi-NPP (Collection 2), archive + NRT | Jan 2012 → today | ~1.8 GB JSON |

Each FIRMS download is a zip with an `fire_archive_*.json` (standard processing) and, for the
latest weeks, a `fire_nrt_*.json` (near-real-time). Unzip them anywhere outside the tracked
files; the `test/` folder at the repository root is gitignored for this purpose:

```
test/
├─ MODIS/        fire_archive_M-C61_*.json, fire_nrt_M-C61_*.json
└─ VIIRS_SNPP/   fire_archive_SV-C2_*.json, fire_nrt_SV-C2_*.json
```

Then, from `server/` and **with the API stopped** (DuckDB allows only one writer):

```bash
# Build the database (about 1 minute for ~6 million detections). --replace rebuilds it from scratch.
python scripts/import_bulk.py ../test/MODIS/*.json ../test/VIIRS_SNPP/*.json \
    --db data/hotspots.duckdb --replace

# Fit the harmonization ratios and store them in the database
python scripts/harmonize.py fit

# Optional: validation report (ratios, cross-validation, 4 reliability tests)
python scripts/harmonize.py report        # -> reports/harmonization/report.md
```

Run `harmonize.py fit` again every time you import new data. Small files (or one sensor) can also
be loaded with `python scripts/import_json.py <file.json> --db data/hotspots.duckdb`, and
`python scripts/generate_mock_data.py --db data/mock_hotspots.duckdb` creates fake data for
development. Details: [server/docs/data-import.md](server/docs/data-import.md).

## 3. Start the API

```bash
cd server
python run.py                 # http://localhost:5000 (also prints a LAN URL)
curl http://localhost:5000/health
```

## 4. Start the web app (`client/`)

```bash
cd client
npm install
cp .env.example .env.local    # optional: VITE_API_BASE_URL (default http://localhost:5000)
npm run dev                   # http://localhost:5173  (add -- --host to share on the LAN)
```

Using it: in the side panel pick a place, draw a rectangle on the map, choose the dates and press
**Save**. The tabs at the top switch between:

- **Map**: the hotspots of the area and dates, colored by fire power (FRP).
- **Calendar**: the monthly burning activity of the area for the whole history (harmonized by
  default; raw MODIS or VIIRS can be chosen). The months of your dates are outlined; click a month
  to see its hotspots on the map. A warning appears for small areas, where the error grows.
- **Dashboard**: charts for the area and dates.

## Checks

```bash
cd server && pytest                                           # backend tests
cd client && npm run lint && npm run format:check && npm run build
```

## More documentation

- [server/README.md](server/README.md) and [server/docs/](server/docs/README.md): API endpoints,
  filtering, dates, data import, Postman collection, running on the LAN.
- [server/docs/harmonization.md](server/docs/harmonization.md): the harmonization method, its
  settings and its reliability.
- [server/AGENTS.md](server/AGENTS.md) and [client/AGENTS.md](client/AGENTS.md): conventions for
  contributors.
