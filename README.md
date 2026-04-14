# Eagle Eye v2

Eagle Eye v2 is a self-hosted, local-first geospatial intelligence platform for continuous global ingest, viewport-scoped 3D visualization, time-aware replay, and analyst investigation workflows.

It is inspired by the interaction model of advanced world simulators, but the implementation here is original and purpose-built for local deployment with PostgreSQL/PostGIS, FastAPI, Redis, Python workers, and a React/Cesium workstation.

## Core Principles

- Database-first ingest: all source data lands in PostgreSQL/PostGIS before the UI sees it.
- Viewport-first rendering: the frontend never renders global datasets directly.
- Time-aware everything: live, paused, replay, and simulate modes all query against a central clock.
- Analyst workflow built in: cases, notes, watchlists, tags, AOIs, workspaces, events, and relationships live beside the globe.

## Monorepo

```text
eagle-eye/
  apps/
    api/
    worker/
    web/
  packages/
    shared-types/
    source-adapters/
    simulation/
    ui/
  infra/
    docker/
    sql/
  docs/
  docker-compose.yml
  .env.example
  README.md
```

## Services

- `web`: React + Vite + Cesium analyst workstation on `http://localhost:8080`
- `api`: FastAPI REST and websocket service on `http://localhost:8000`
- `worker`: ingest, event detection, simulation maintenance, retention cleanup
- `db`: PostgreSQL 16 + PostGIS
- `redis`: cache and invalidation/pubsub bus

## Key Capabilities

- Real-time and historical world model across air, maritime, and space domains
- Central simulation clock with play/pause, step, speed, and jump controls
- View-scoped query pipeline via `POST /api/view/query`
- LOD and clustering behavior based on camera height
- AOIs with events and satellite pass analysis
- Satellite FOV footprint and pass APIs
- Event engine for stale tracks, airspace violations, loitering, and overflight correlation
- Investigation workflows with cases, workspaces, watchlists, notes, tags, and relationships

## Database-first View Rendering

The critical contract is:

1. Workers ingest source data into PostGIS-backed current/history tables.
2. The web app computes `GlobeViewState` from the Cesium camera.
3. The frontend posts that state to `/api/view/query`.
4. The API returns only entities, clusters, events, and relationships relevant to that view/time.
5. Websocket frames send invalidation hints such as `view.invalidate`; they do not stream full global state.

## Main Tables

- `aircraft_current`, `aircraft_history`
- `vessels_current`, `vessels_history`
- `satellites_catalog`, `satellites_current`, `satellites_history`
- `airspace_overlays`
- `events`
- `relationships`
- `cases`
- `workspaces`
- `watchlists`, `watchlist_entities`
- `notes`
- `tags`
- `aois`
- `time_state`

Retention defaults to 7 days and all timestamps are UTC.

## Environment

Copy `.env.example` to `.env`, then set the provider secrets you want to enable. CelesTrak is usable without a key for initial satellite support.

Important variables:

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
VITE_API_BASE_URL
RETENTION_DAYS
```

## Run

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- `http://localhost:8080` for the workstation
- `http://localhost:8000/docs` for API docs
- `http://localhost:8000/health` for health

## Notes on Sources

- Aircraft: OpenSky ingest structure is live.
- Vessels: AISStream is primary, AISHub is fallback-ready, Global Fishing Watch is optional enrichment.
- Satellites: CelesTrak ingest with propagated current positions and sensor footprint APIs.
- Airspace: FAA TFR overlays are ingested into `airspace_overlays`.

If a provider key is absent, the system stays bootable and the corresponding ingest loop idles rather than blocking the rest of the platform.

## Docs

- High-level architecture: [docs/architecture.md](/Users/edmondedwards/Desktop/Eagle%20eye/docs/architecture.md)
