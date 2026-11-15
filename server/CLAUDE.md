@AGENTS.md

## Key rules (summary; AGENTS.md is the source of truth)

- Work only in `server/`. Never touch `client/` or `server/harmonizer/`. Never commit `data/`.
- Stack is fixed: Python >= 3.12, pip, Flask factory, DuckDB read-only, Pydantic v2, flask-cors, pytest.
- English everywhere; Google-style docstrings explaining what/how/why; full type hints.
- SQL is always parameterized. One read-only connection per app, one cursor per request.
- Corners in any order (min/max), inclusive edges, inclusive UTC dates on `acq_date`, `limit + 1` truncation.
- LAN by default: `API_HOST=0.0.0.0`, CORS also allows private-network origins (`CORS_ALLOW_LAN`).
- No results → HTTP 200 + `"message": "No data found in the selected area"` (only then).
- Run `pytest` from `server/` after every change and keep `docs/` in sync.
- Git: work on a new branch, commit locally on your own (small commits, co-author trailer);
  push and open the PR only after the user confirms (AGENTS.md §14).
