# Eagle Eye

Eagle Eye is a self-hosted OSINT analyst application for aggregating global aircraft, maritime, and airspace activity into a single local investigation console. The v1 build emphasizes an analyst-first workflow: a dark high-density Cesium globe, live and replay movement data, cases, notes, tags, watchlists, and source provenance throughout the stack.

## What v1 includes

- Local-only Docker Compose deployment
- No authentication in v1
- React + TypeScript + Vite frontend with a Cesium 3D globe
- FastAPI backend with REST endpoints and a `/ws/live` websocket
- PostgreSQL + PostGIS current-state and history tables
- Redis-backed live pub/sub
- OpenSky aircraft polling structure
- AISStream websocket ingest structure
- CelesTrak-backed satellite catalog, live positions, and selected-orbit previews
- FAA TFR / airspace overlay ingest structure
- 7-day retention cleanup job
- Cases, notes, tags, watchlists, saved views, search, and playback-ready APIs

## Monorepo layout

```text
eagle-eye/
  apps/
    api/
    worker/
    web/
  packages/
    shared-types/
    ui/
    source-adapters/
  infra/
    docker/
    sql/
  docs/
  docker-compose.yml
  .env.example
  README.md
```

## Services

- `web`: analyst workstation UI on port `8080`
- `api`: FastAPI service on port `8000`
- `worker`: ingestion and retention loops
- `db`: PostgreSQL 16 + PostGIS
- `redis`: live pub/sub and cache support

## Configuration

1. Copy `.env.example` to `.env`.
2. Set the required secrets:
   - `OPENSKY_CLIENT_ID`
   - `OPENSKY_CLIENT_SECRET`
   - `AISSTREAM_API_KEY`
   - `CESIUM_ION_TOKEN`
3. Satellite support defaults to public CelesTrak GP data and requires no key for first boot. Optional provider credentials can be added later for Space-Track or N2YO.
4. Adjust database credentials and `VITE_API_BASE_URL` if your browser will reach the API through a different local IP or reverse proxy.

The required environment variables are:

```bash
APP_NAME
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
DATABASE_URL
REDIS_URL
OPENSKY_CLIENT_ID
OPENSKY_CLIENT_SECRET
AISSTREAM_API_KEY
CESIUM_ION_TOKEN
ENABLE_SATELLITES
SATELLITE_DEFAULT_SOURCE
CELESTRAK_GROUP
SPACETRACK_USERNAME
SPACETRACK_PASSWORD
N2YO_API_KEY
VITE_API_BASE_URL
RETENTION_DAYS
```

## Start the stack

```bash
cp .env.example .env
docker compose up --build
```

Once the services are up:

- UI: `http://localhost:8080`
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/health`

## Architecture summary

- `apps/worker` normalizes source feeds into canonical models from `packages/source-adapters`.
- Current-state tables power live map rendering and fast lookup.
- History tables power replay, movement playback, and timeline views.
- Satellite ingest persists four layers of state: `satellites_catalog`, `satellites_current`, `satellites_history`, and `satellite_source_snapshots`.
- Redis carries normalized live envelopes into `/ws/live`.
- `apps/api` exposes analyst CRUD workflows and geospatial/time-window queries.
- `apps/web` renders the globe, layered overlays, replay controls, analyst panels, and selected satellite orbit previews.

Additional detail lives in [`docs/architecture.md`](docs/architecture.md).

## Secrets rotation

- Replace the relevant values in `.env`.
- Rebuild the affected containers:

```bash
docker compose up --build -d web api worker
```

For Cesium, the token is baked into the web bundle at build time, so rebuilding `web` is required after rotation.

## Satellite Support

- v1 defaults to `CelesTrak` using the public GP endpoint and `GROUP=active`.
- `Space-Track` is scaffolded for v1.1-ready use, but still requires a valid account and approval workflow before it is useful in production.
- `N2YO` is scaffolded for v1.1-ready use and requires an API key generated from the user profile page after registration.
- Satellite history is retained for 7 days just like aircraft and vessels.
- The globe only renders a capped subset of in-view satellites and only draws full orbit paths for the selected satellite, so enabling the satellite layer does not force every object to render at full detail.
- Search now supports satellite NORAD ID and name through the general search bar and the dedicated `/api/satellites/search` endpoint.
- Notes, tags, and watchlists can reference satellites using the existing analyst object model.

### Satellite Env Knobs

- `ENABLE_SATELLITES=true` enables the satellite worker loop.
- `SATELLITE_DEFAULT_SOURCE=celestrak` keeps the default boot path free and public.
- `CELESTRAK_GROUP=active` controls the default public group; you can also pass a comma-separated list such as `active,stations,weather`.
- `SPACETRACK_USERNAME` and `SPACETRACK_PASSWORD` are optional and only used if you later switch `SATELLITE_DEFAULT_SOURCE=spacetrack`.
- `N2YO_API_KEY` is optional and only used if you later switch `SATELLITE_DEFAULT_SOURCE=n2yo`.

## v1 limitations

- FAA public airspace/TFR parsing is implemented as a best-effort ingestion path against public FAA pages and may need source-specific tuning if the FAA page structure changes.
- OpenSky and AISStream throughput depends on source-side limits and the resources of the local host.
- AISStream requires a valid API key; if it is blank or invalid, the vessel layer will remain empty while the rest of the stack stays up.
- Satellite paths in v1 are driven by current GP/TLE snapshots from public CelesTrak groups. Historical playback falls back to the nearest retained source snapshot when an exact historical point is unavailable.
- No authentication, alerting, anomaly detection, or shared multi-user workspace in v1.
- Webcams are intentionally deferred; only the adapter interface and placeholder catalog shape are prepared.
- Search supports identifiers, analyst object names, and direct coordinate lookup; it is not a full geocoder in v1.

## Planned for v1.5

- Webcam ingest and playback
- Analyst alerting
- Anomaly detection pipelines
- Shared workspace and collaboration features
- Richer provenance views and multi-source confidence fusion
- Space-Track and N2YO provider promotion beyond the default CelesTrak flow
