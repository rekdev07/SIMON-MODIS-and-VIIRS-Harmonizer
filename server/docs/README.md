# Hotspots API documentation

Plain-language docs for the backend in `server/`. No satellite background needed.

| Document | Read it to learn |
|---|---|
| [running.md](running.md) | Step by step: install, load data, start the API, share it on the local network (LAN), run the tests, fix common problems |
| [postman.md](postman.md) | How to try every endpoint in Postman, with a ready-to-import collection in [`postman/`](postman/) |
| [api.md](api.md) | Every endpoint, its parameters, `curl` examples and example responses |
| [dashboard-api.md](dashboard-api.md) | The `/api/v1/stats/*` endpoints that feed the dashboard charts (contract for the frontend) |
| [filtering.md](filtering.md) | How two corners become a rectangle, how each filter works, pagination |
| [dates.md](dates.md) | Why everything is UTC, why both dates are inclusive, the "midnight" case |
| [data-import.md](data-import.md) | How the raw FIRMS JSON is cleaned and loaded into DuckDB |
| [harmonization.md](harmonization.md) | How MODIS and VIIRS counts become one continuous series, and how reliable it is |

## 30-second glossary

- **Hotspot**: one satellite pixel where the sensor saw something much hotter than its
  surroundings, usually a fire. Each hotspot has a position, a time and some measurements.
- **MODIS**: an instrument on NASA's *Terra* and *Aqua* satellites (since 2000/2002). Pixels about 1 km wide.
- **VIIRS**: a newer instrument on *Suomi NPP* (SNPP), *NOAA-20* and *NOAA-21* (since 2012). Pixels about 375 m wide,
  so it sees smaller fires.
- **FIRMS**: NASA's Fire Information for Resource Management System, where the data comes from.
- **FRP** (fire radiative power): how much energy the fire radiates, in megawatts. Bigger means more intense.
- **Detection**: one hotspot. It is not the same as one fire: a big fire produces many detections.
- **Confidence**: how sure the detection algorithm is that it is a real fire (`low`, `nominal`, `high`).
- **UTC**: the world reference clock. Mexico City is UTC−6, so 19:00 UTC is 13:00 in Mexico City.

For developer conventions, see [`../AGENTS.md`](../AGENTS.md).
