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
| `API_HOST` | `0.0.0.0` | `0.0.0.0` = this computer **and** other devices on your network; `127.0.0.1` = only this computer |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Websites allowed to call the API from a browser (`*` = any website) |
| `CORS_ALLOW_LAN` | `1` | `1` = also allow pages opened from your local network (e.g. `http://192.168.1.23:5173`); `0` = only `CORS_ORIGINS` |
| `FLASK_DEBUG` | `0` | `1` reloads the server when code changes (development only) |

## Step 5. Start the API

```bash
python run.py
```

You should see something like:

```text
Hotspots API is starting:
  Local:   http://localhost:5000
  Network: http://192.168.1.23:5000  <- share this with your team
```

- **Local** works only on this computer.
- **Network** works from any device on the same Wi-Fi or cable network (your own IP will differ).
  See [Using the API from other devices](#using-the-api-from-other-devices-lan).

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

## Using the API from other devices (LAN)

By default the API is shared on your **local network** (LAN): the Wi-Fi or cable network your
computer is connected to. Anyone on the same network can use it, which is handy when one laptop
runs the API and teammates work on the frontend from theirs.

```text
        same Wi-Fi network (e.g. 192.168.1.x)
 ┌──────────────────────────────────────────────────┐
 │  Laptop A (runs the API)     Laptop B / phone     │
 │  192.168.1.23:5000  ◄─────── http://192.168.1.23:5000/health
 └──────────────────────────────────────────────────┘
```

1. **Start the API** with `python run.py` and copy the `Network:` address it prints
   (e.g. `http://192.168.1.23:5000`).
2. **On the other device**, open `http://192.168.1.23:5000/health` in a browser.
   `{"status": "ok", ...}` means it works.
3. **Use that address everywhere** instead of `localhost`: in Postman (`baseUrl`), `curl`, or the frontend.

### If the other device cannot connect

| Check | How |
|---|---|
| Both devices are on the **same network** | Guest Wi-Fi, phone hotspots and university/company networks often block device-to-device traffic. A phone hotspot shared by everyone usually works |
| The API listens on the LAN | The startup message shows a `Network:` line. If it says "disabled", remove `API_HOST=127.0.0.1` from `.env` |
| The **firewall** allows port 5000 | See below |
| You used the right IP | It changes when you switch networks. Restart the API and read the `Network:` line again |

Firewall, on the computer running the API:
- **Windows:** the first time you run the API, Windows asks whether Python may communicate on networks.
  Tick **Private networks** and click **Allow**. If you clicked Cancel: *Windows Security → Firewall &
  network protection → Allow an app through firewall → Python → Private*. Also make sure your Wi-Fi is set
  as a **Private** network (*Settings → Network & Internet → Wi-Fi → your network → Private*).
- **macOS:** click **Allow** when asked "accept incoming network connections?". Otherwise:
  *System Settings → Network → Firewall → Options* and allow Python.
- **Linux (ufw):** `sudo ufw allow 5000/tcp`

### Frontend on the LAN

For teammates to open the website itself from their devices:
- Start the Vite dev server so it is reachable on the network: `npm run dev -- --host` (in `client/`).
- Point the frontend to the API's **Network** address (e.g. `http://192.168.1.23:5000`), not `localhost`:
  on another device, `localhost` means *that* device, where no API is running.

CORS (the browser's "which websites may call this API" check) is already handled: with
`CORS_ALLOW_LAN=1` (the default), pages served from `localhost` or any private network address
(`192.168.x.x`, `10.x.x.x`, `172.16.x.x`–`172.31.x.x`, `<name>.local`) are allowed. Public websites are not.

### Keeping it private

The API has **no password**: everyone on the same network can read the data. That is fine for public
FIRMS data at a hackathon, but on a network you do not trust, set `API_HOST=127.0.0.1` in `.env`
(and optionally `CORS_ALLOW_LAN=0`), then restart. The startup message will show `Network: disabled`.

## Step 7. Run the automated tests

```bash
pytest
```

All tests should pass (the last line says something like `128 passed`). The tests build
their own tiny database, so they work even if you never loaded any data.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/health` returns 503 `"database": "unavailable"` | The database file does not exist or is the wrong path | Do Step 3, or check `HOTSPOTS_DB_PATH` |
| `ModuleNotFoundError: No module named 'flask'` | The virtual environment is not active | Activate it (Step 2) |
| `Address already in use` | Another program uses the port | Change `API_PORT` in `.env` |
| Import script says the file is locked | The API is running | Stop the API (`Ctrl+C`) and import again |
| Browser shows a CORS error from the client | The client's address is not allowed (e.g. a public domain, or `CORS_ALLOW_LAN=0`) | Add it to `CORS_ORIGINS` (or set `CORS_ALLOW_LAN=1`) and restart the API |
| Works on my computer, not on my teammate's | Firewall, different network or wrong IP | See [If the other device cannot connect](#if-the-other-device-cannot-connect) |
| `python: command not found` | Python is called `python3` on your system | Use `python3` instead of `python` |
