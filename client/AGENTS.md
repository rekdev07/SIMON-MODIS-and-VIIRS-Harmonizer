# AGENTS.md: SIMON Harmonizer frontend (client/)

This file holds everything an agent or a person needs to build and maintain this
frontend. Read it before changing anything in `client/`.

## 1. Context

- Event: NASA Space Apps Challenge 2026, challenge "Harmonization of MODIS and VIIRS Hot Spots".
- This is the **web client** of the project: a map viewer where the user draws or picks a
  **rectangle** and a **date range**, and sees the fire hotspots detected by the MODIS and
  VIIRS satellite instruments (NASA FIRMS data) inside it.
- All data comes from the **Hotspots API** in `server/` (read-only REST, no authentication).
  The frontend does **not** download FIRMS data, does **not** harmonize sensors and does
  **not** read the DuckDB database directly.

### Monorepo

```
SIMON-MODIS-and-VIIRS-Harmonizer/
├─ client/             this frontend (all work happens here)
└─ server/             Flask + DuckDB Hotspots API (http://localhost:5000). NOT part of this app. Do not modify.
   └─ harmonizer/      placeholder for harmonization logic. Do not modify.
```

All paths below are relative to `client/`. Run every command (`npm`, `npx`) from
inside `client/`.

## 2. Stack (closed decisions, do not change)

| Concern            | Choice                                                                                                                 |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| Language           | **TypeScript** (strict-ish: `noUnusedLocals`, `noUnusedParameters`, `erasableSyntaxOnly`)                              |
| Runtime / packages | **Node + npm** only (`package.json` + `package-lock.json`). No yarn/pnpm/bun.                                          |
| UI library         | **React 19** function components + hooks                                                                               |
| Build / dev server | **Vite** (dev server http://localhost:5173)                                                                            |
| Styling            | **Tailwind CSS v4** via `@tailwindcss/vite`, imported in `src/index.css`                                               |
| Maps               | **Leaflet** + **react-leaflet**                                                                                        |
| Lint               | **ESLint** flat config (`eslint.config.js`): JS + typescript-eslint + react-hooks + react-refresh, Prettier-compatible |
| Format             | **Prettier** (`.prettierrc.json`): no semicolons, single quotes, trailing commas, width 80, Tailwind class sorting     |
| Config             | Vite env vars (`VITE_*`) from `.env` / `.env.local`                                                                    |

Do not add UI kits, state-management libraries, CSS-in-JS or other frameworks without
the team agreeing first. Keep it simple: `fetch` for HTTP, React state for state.

## 3. Structure

```
client/
├─ AGENTS.md / CLAUDE.md     agent instructions (this file + short summary)
├─ index.html                Vite entry HTML (title "SIMON Harmonizer")
├─ public/                   static files served as-is (favicon.svg)
├─ src/
│  ├─ main.tsx               React root: StrictMode + global CSS + <App />
│  ├─ App.tsx                top-level component / page switch
│  ├─ index.css              Tailwind import and global styles
│  ├─ pages/                 one component per screen (e.g. MapViewer.tsx)
│  └─ components/
│     ├─ landing/            components of the landing page (Navbar.tsx)
│     └─ ScreenViewer/       components of the map viewer (Map.tsx, SideBar.tsx)
├─ eslint.config.js, .prettierrc.json, .prettierignore
├─ vite.config.ts, tsconfig*.json
└─ package.json, package-lock.json, README.md
```

When the app starts talking to the API, add these (and keep the layering):

```
src/
├─ api/          typed fetch wrappers for the Hotspots API (the only place that builds URLs)
├─ types/        TypeScript types mirroring the API responses (section 5)
└─ hooks/        data hooks (e.g. useHotspots) that call src/api and expose loading/error/data
```

Layering: `pages` → `components` for UI → `hooks` for data → `api` for HTTP.
Components never call `fetch` directly and contain no URL building.

## 4. Code conventions

- **Everything in English**: identifiers, comments, UI text, commit messages.
- **Function components** only, one component per file, `PascalCase` file and component
  names, `export default` the component. Props typed with a `type` named `<Component>Props`.
- Use `import { type X }` / `import type` for type-only imports (`verbatimModuleSyntax`).
- **No `any`**. Type API responses explicitly (section 5); narrow `unknown` instead.
- **TSDoc comments** (`/** ... */`) on every exported component, hook, function and type,
  explaining **what**, **how** and **why**. Explain every non-obvious rule: corner order,
  `[longitude, latitude]` order in GeoJSON vs `[lat, lng]` in Leaflet, inclusive UTC dates,
  `truncated` handling, etc.
- Inline comments only where the logic is not obvious.
- **Styling with Tailwind utility classes**; no inline `style` except for values computed
  at runtime. Leaflet needs its CSS (`leaflet/dist/leaflet.css`) and a container with an
  explicit height.
- **Never** interpolate user input into URLs by hand: build query strings with
  `URLSearchParams`.
- Run `npm run lint` and `npm run format:check` (or `npm run format`) before every commit.

## 5. API contract (consumed, defined in `server/AGENTS.md`)

`server/AGENTS.md` is the source of truth; if it changes, update the types in `src/types/`
and this section.

### `GET /api/v1/hotspots`

| Param                       | Required | Rule                                                                                                           |
| --------------------------- | -------- | -------------------------------------------------------------------------------------------------------------- |
| `lat1`,`lon1`,`lat2`,`lon2` | yes      | rectangle corners in any order; lat ∈ [-90, 90], lon ∈ [-180, 180]; width and height > 0; must not cross ±180° |
| `start_date`,`end_date`     | yes      | `YYYY-MM-DD`, both **inclusive**, UTC days, `start <= end`, within [2000-11-01, today UTC]                     |
| `confidence_min`            | no       | `low` (default) / `nominal` / `high`                                                                           |
| `daynight`                  | no       | `D` / `N` (default both)                                                                                       |
| `instrument`                | no       | `MODIS` / `VIIRS` (default both)                                                                               |
| `vegetation_only`           | no       | bool, default false                                                                                            |
| `limit` / `offset`          | no       | default 10000 / 0, max limit 50000                                                                             |
| `format`                    | no       | `geojson` (default) / `json`                                                                                   |

- Leaflet bounds give corners directly: `getSouthWest()` / `getNorthEast()` → `lat1,lon1,lat2,lon2`.
- Dates are UTC calendar days: format them as `YYYY-MM-DD` without converting to local time.
- Validate on the client too (same ranges as above) to give instant feedback, but the API
  is the authority: always handle its 400 errors.

### Response

- GeoJSON `FeatureCollection`. **Coordinates are `[longitude, latitude]`**; Leaflet wants
  `[latitude, longitude]`, so swap them (or use `L.geoJSON`, which handles it).
- Feature properties: `acquired_at` (ISO-8601 UTC with `Z`), `instrument`, `satellite`,
  `daynight`, `frp` (may be null), `confidence` (`low`/`nominal`/`high`), `fire_type` (may be null).
- `metadata`: `bbox [min_lon, min_lat, max_lon, max_lat]`, `start_date`, `end_date`,
  `returned`, `limit`, `offset`, `truncated`.
- **No results → HTTP 200** with an empty list and `"message": "No data found in the selected area"`.
  Show that message to the user; it is not an error. `message` exists only when empty.
- `truncated: true` means there are more hotspots than `limit`: tell the user and offer to
  narrow the area/dates or page with `offset`.

### `GET /api/v1/calendar`

- Params: `lat1,lon1,lat2,lon2` (+ the same optional filters as `/hotspots`), **no dates**.
- Returns hotspot counts per month for every loaded month: `months[]` (`year`, `month`, `count`,
  `modis`, `viirs`, `partial`), `years[]`, `monthly_median` (12 values, index 0 = January, null when
  no full month), `coverage`, `harmonized` (false for now), `total`; `message` only when `total` is 0.
- A month **missing** from `months` = no data loaded (draw hatched); `count: 0` = observed, no fires.
  `partial` months are left out of medians and anomalies.
- Drawn by `components/Calendar/BurnCalendar.tsx` (year × month heatmap, YlOrRd counts / RdBu
  anomaly vs median, CSV export); clicking a month searches that month's hotspots on the map.

### Other endpoints

- `GET /api/v1/dataset`: total records, min/max `acq_date`, count per instrument, bbox of all
  data. Use it to bound the date pickers and the initial map view.
- `GET /health`: `200 {"status":"ok","database":"connected"}` or `503 {"status":"error","database":"unavailable"}`.

### Errors

`{"error": {"code": "...", "message": "...", "parameter"?: "..."}}`. Codes: 400
`INVALID_PARAMETER`, 404 `NOT_FOUND`, 405 `METHOD_NOT_ALLOWED`, 503 `DATABASE_UNAVAILABLE`,
500 `INTERNAL_ERROR`. Show `message` to the user (highlight the field named by `parameter`)
and handle network failures (API down) separately with a clear message.

## 6. Configuration

- API base URL from **`VITE_API_BASE_URL`** (default `http://localhost:5000`). Read it in one
  place (`src/api/`) through `import.meta.env`. Never hardcode another host in components.
- Local overrides go in `.env.local` (gitignored by `*.local`). Do not commit secrets; there
  are none, and anything in `VITE_*` ends up public in the bundle anyway.

### LAN access

- The API is shared on the local network during the hackathon (`server/` listens on `0.0.0.0:5000`
  and its CORS accepts private-network origins such as `http://192.168.x.x:5173`).
- To open the frontend from other devices, run `npm run dev -- --host` and point
  `VITE_API_BASE_URL` at the API machine's LAN URL (printed by `python run.py` as `Network:`).
- There is no authentication: anyone on the same network can read the data.

## 7. Running

```bash
npm install                 # once, or after package.json changes (use npm ci for a clean install)
npm run dev                 # http://localhost:5173 (add -- --host for LAN)
npm run lint                # ESLint (npm run lint:fix to auto-fix)
npm run format:check        # Prettier check (npm run format to rewrite)
npm run build               # tsc -b type check + production build into dist/
npm run preview             # serve dist/ locally
```

The API must be running (see `server/README.md`) for real data.

## 8. Checks before finishing

There is no test runner yet. Before committing, all of these must pass:

1. `npm run lint`
2. `npm run format:check`
3. `npm run build` (type check included)
4. Manual check in `npm run dev`: the map renders, hotspots load for a known area/dates,
   the empty-result message and API errors are shown.

If a test runner is added later, it must be **Vitest** (fits Vite) and every behavior change
then needs a test; update this section.

## 9. Documentation rules

- `README.md` covers install, running, LAN use, env vars and the scripts. Replace the Vite
  template text with project content when touching it.
- Update this file whenever the stack, structure, conventions or API usage change.

## 10. Out of scope

Any change to `server/` or `server/harmonizer/` (ask the backend owner instead);
downloading from FIRMS; harmonization/calibration between sensors; authentication;
direct database access. Never commit `node_modules/`, `dist/` or `.env*.local`.

## 11. Git workflow (agents)

All work goes **directly on `main`**: no feature branches and no pull requests.
Agents commit their own work locally; pushing always waits for the user's OK.

1. **Work on `main`.** Before starting, `git switch main` and `git pull --ff-only origin main`
   so you build on the latest work from the team.
2. **Commit automatically and locally**, without asking, once a logical step is done and
   the checks in section 8 pass:
   - Small commits, one logical change each (e.g. component, styles and docs can be separate commits).
   - Message: short imperative subject in English, ≤ 72 characters, no trailing period
     (`Add hotspots layer to the map viewer`); optional body explaining _why_.
   - End every commit message with the agent's co-author trailer, e.g.
     `Co-Authored-By: Claude <noreply@anthropic.com>` (use the trailer your tool provides).
     Keep the repository's configured git user as author; do not change `git config`.
   - Stage files explicitly (`git add <paths>`), check `git status` first, and never commit
     `node_modules/`, `dist/`, `.env*.local` or other ignored or local files. Commit
     `package-lock.json` only together with the `package.json` change that caused it.
     Leave other people's uncommitted changes alone.
3. **Do not push yet.** When the task is finished, list the new commits
   (`git log --oneline origin/main..HEAD`) and ask the user to review and confirm.
4. **After the user confirms it is good**, push to `main`:
   - `git pull --rebase origin main` if `origin/main` moved meanwhile (teammates push to it too),
     run the checks again, then `git push origin main`.
   - Reply with the pushed commits.
5. Never force-push or rewrite published history unless the user asks.
