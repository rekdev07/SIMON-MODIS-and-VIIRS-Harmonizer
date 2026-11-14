# Running the project

This guide takes you from a fresh copy of the repository to a running API, step by step.
You only need a terminal. Every command is run from inside the `server/` folder.

```text
SIMON-MODIS-and-VIIRS-Harmonizer/
├─ client/      ← the website (not needed for this guide)
└─ server/      ← open your terminal HERE
```

## The big picture

```text
  FIRMS JSON file  ──(import script)──►  DuckDB file  ◄──(reads)──  API  ◄──(HTTP)──  you / Postman / client
  data/raw/*.json                        data/*.duckdb              run.py
```

1. The API never reads the JSON directly. A script copies the JSON into a small database file (DuckDB).
2. The API opens that database file in read-only mode and answers questions about it.
3. You ask questions over HTTP: from a browser, `curl`, Postman or the React client.

## Step 1. Check Python

You need **Python 3.12 or newer**.

```bash
python --version        # on some Linux/macOS systems: python3 --version
```

If it says 3.11 or lower, install a newer Python from <https://www.python.org/downloads/>.

## Step 2. Create a virtual environment and install dependencies

A virtual environment (`.venv`) is a private folder with this project's libraries,
so they do not mix with other projects on your computer.

```bash
python -m venv .venv
```

Activate it (you must do this **every time you open a new terminal**):

| System | Command |
|---|---|
| Linux / macOS | `source .venv/bin/activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows cmd | `.venv\Scripts\activate.bat` |

When it is active, your prompt starts with `(.venv)`. Now install the libraries:

```bash
pip install -r requirements.txt        # needed to run the API
pip install -r requirements-dev.txt    # adds pytest, needed to run the tests
```

## Step 3. Load data into the database

The API needs a database file. Pick **one** option.

### Option A: real data (recommended)

The team's FIRMS export must be at `data/raw/fire_archive_SV-C2_849193.json`
(it is not in git because it is about 147 MB; ask a teammate for it).

```bash
python scripts/import_json.py data/raw/fire_archive_SV-C2_849193.json --db data/hotspots.duckdb
```

It takes a minute or two and ends with a summary like this:

```text
=== Import summary ===
Database:            data/hotspots.duckdb
Records read:        367064
Inserted:            367064
Rejected:            0
Duplicates skipped:  0 ...
Date range (UTC):    2013-01-01 -> 2014-01-01
Valid records per instrument:
  - VIIRS: 367064
```

`data/hotspots.duckdb` is the default database, so no extra configuration is needed.

### Option B: fake data (no JSON needed)

Useful if you do not have the JSON yet. It creates realistic but **invented** hotspots across Mexico.

```bash
python scripts/generate_mock_data.py --db data/mock_hotspots.duckdb
```

Then tell the API to use that file (see Step 4).

> **Stop the API before importing.** DuckDB does not allow a script to write the file
> while the API has it open.

## Step 4. (Optional) Configure with a `.env` file

The defaults work out of the box. To change something, copy the example file:

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

and edit `.env`. The most useful settings:

| Setting | Default | What it does |
|---|---|---|
| `HOTSPOTS_DB_PATH` | `data/hotspots.duckdb` | Which database file to read. Use `data/mock_hotspots.duckdb` for fake data |
| `API_PORT` | `5000` | Port the API listens on |
| `API_HOST` | `127.0.0.1` | `127.0.0.1` = only this computer; `0.0.0.0` = other devices on your network too |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Websites allowed to call the API from a browser |
| `FLASK_DEBUG` | `0` | `1` reloads the server when code changes (development only) |

## Step 5. Start the API

```bash
python run.py
```

You should see something like:

```text
 * Running on http://127.0.0.1:5000
```

Leave this terminal open: the API runs as long as it is open. Press `Ctrl+C` to stop it.

**macOS note:** port 5000 is sometimes taken by "AirPlay Receiver". If you get
"Address already in use", set `API_PORT=5001` in `.env` and use port 5001 everywhere.

## Step 6. Check it works

Open <http://localhost:5000/health> in your browser. You should see:

```json
{"status": "ok", "database": "connected"}
```

Then try a real query in the browser:

<http://localhost:5000/api/v1/hotspots?lat1=21.7&lon1=-90.4&lat2=19.5&lon2=-87.4&start_date=2013-04-01&end_date=2013-04-30&limit=5>

To explore the API comfortably, continue with [postman.md](postman.md).

## Step 7. Run the automated tests

```bash
pytest
```

All tests should pass (the last line says something like `104 passed`). The tests build
their own tiny database, so they work even if you never loaded any data.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/health` returns 503 `"database": "unavailable"` | The database file does not exist or is the wrong path | Do Step 3, or check `HOTSPOTS_DB_PATH` |
| `ModuleNotFoundError: No module named 'flask'` | The virtual environment is not active | Activate it (Step 2) |
| `Address already in use` | Another program uses the port | Change `API_PORT` in `.env` |
| Import script says the file is locked | The API is running | Stop the API (`Ctrl+C`) and import again |
| Browser shows a CORS error from the client | The client's address is not allowed | Add it to `CORS_ORIGINS` and restart the API |
| `python: command not found` | Python is called `python3` on your system | Use `python3` instead of `python` |
