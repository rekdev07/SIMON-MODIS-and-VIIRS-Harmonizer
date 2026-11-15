@AGENTS.md

## Key rules (summary; AGENTS.md is the source of truth)

- Work only in `client/`. Never touch `server/` or `server/harmonizer/`. Never commit `node_modules/`, `dist/`, `.env*.local`.
- Stack is fixed: TypeScript, npm, React 19, Vite, Tailwind v4, Leaflet + react-leaflet, ESLint, Prettier.
- English everywhere; TSDoc on exported code explaining what/how/why; no `any`; function components, one per file.
- Layering: pages → components → hooks → `src/api` (only place that calls `fetch`; query strings via `URLSearchParams`).
- API base URL from `VITE_API_BASE_URL` (default `http://localhost:5000`); contract lives in `server/AGENTS.md`.
- GeoJSON coordinates are `[lon, lat]`, Leaflet wants `[lat, lng]`. Dates are inclusive UTC `YYYY-MM-DD`.
- Empty result is HTTP 200 + `"message": "No data found in the selected area"`: show it, not an error. Handle `truncated`.
- Run `npm run lint`, `npm run format:check` and `npm run build` from `client/` after every change.
- Git: work directly on `main` (no branches, no PRs), commit locally on your own (small commits,
  co-author trailer); push to `main` only after the user confirms (AGENTS.md §11).
