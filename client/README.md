# SIMON web app (client)

React + TypeScript + Vite + Tailwind + Leaflet frontend of SIMON. It talks to the Hotspots API in
[`../server`](../server/README.md); the whole-project setup (including loading the MODIS and VIIRS
data) is in the [root README](../README.md).

## Run

```bash
npm install
cp .env.example .env.local   # optional: VITE_API_BASE_URL (default http://localhost:5000)
npm run dev                  # http://localhost:5173  (npm run dev -- --host to share on the LAN)
```

The API must be running for real data.

## Scripts

| Command                           | What it does                               |
| --------------------------------- | ------------------------------------------ |
| `npm run dev`                     | Development server with hot reload         |
| `npm run lint`                    | ESLint (`npm run lint:fix` to fix)         |
| `npm run format` / `format:check` | Prettier                                   |
| `npm run build`                   | Type check + production build into `dist/` |
| `npm run preview`                 | Serve `dist/` locally                      |

## Structure

- `src/pages/`: `MapViewer` (side panel + Map / Calendar / Dashboard / ML tabs),
  `Dashboard`, and the Machine Learning view.
- `src/components/`: `fields/` (side panel controls), `ScreenViewer/` (map), `Calendar/` (burning
  activity calendar), `dashboard/` (charts), and `model/` (prediction form and evaluation visuals).
- `src/api/`, `src/hooks/`, `src/types/`: typed API calls, data hooks and response types.

The Machine Learning view sends feature values to the server-side model; the
classifier artifacts and evaluation report are documented in
[`../server/docs/model.md`](../server/docs/model.md).

Conventions for contributors: [AGENTS.md](AGENTS.md).
