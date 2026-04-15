# Eagle Eye v2 Architecture

## Flow

1. Source adapters normalize provider payloads into canonical records.
2. Worker loops persist those records into PostGIS current/history tables.
3. Event detection workers derive events and relationships from persisted state.
4. The API exposes time-aware viewport queries, FOV/pass analysis, and analyst CRUD workflows.
5. The Cesium client computes the current globe view and asks the API for only that slice.

## Data Domains

### Aircraft

- Current table for latest state
- Append-only history for replay
- Linear path prediction for near-future trails
- Airspace violation and stale-track event detection

### Maritime

- AISStream primary ingest
- AISHub fallback-ready polling
- Provider health tracking
- Loitering detection and watchlist workflows

### Space

- CelesTrak catalog ingest
- Propagated current positions
- History retention for replay
- FOV footprint and pass calculations

### Hazards

- EONET natural-event ingestion with source-native geometry history
- FIRMS thermal detections stored raw, then optionally clustered into view-friendly fire events
- NWS public weather alerts stored natively and normalized into the event system
- Hazard-native tables plus `hazard_events_normalized` for cross-source querying

## Global Time Engine

`time_state` stores the active mode, status, current timestamp, speed, and step size.

Supported modes:

- `live`
- `paused`
- `replay`
- `simulate`

The web app uses `/api/time/state` and `/api/time/set`, and the viewport API consumes the resulting timestamp for all queries.

## View Query Contract

`POST /api/view/query`

Input:

- camera bounds
- camera height
- orientation
- timestamp
- mode
- enabled layers
- selected entities / AOIs

Output:

- concrete entities for high-detail views
- clusters for zoomed-out views
- current events
- current hazard events from EONET, FIRMS, and NWS when those layers are enabled
- relevant relationships
- stats

## Event Engine

Current rules implemented in the worker:

- stale aircraft tracks
- airspace violations
- vessel loitering
- satellite overflight over AOIs

Each event is stored in `events`, and derived graph links are stored in `relationships`.

## Investigation Workflows

- `cases` and `case_entities`
- `notes`
- `watchlists` and `watchlist_entities`
- `tags`
- `workspaces`
- `aois`

These records are local-first analyst artifacts and intentionally do not require authentication in this deployment profile.

## Deployment

Docker Compose runs all services locally:

- `db`
- `redis`
- `api`
- `worker`
- `web`

The system is designed for single-node local operation with no auth and no external dependency required beyond the data providers you choose to enable.

## Hazard Query Model

- `POST /api/hazards/view-query` returns normalized hazard rows intersecting the viewport and time window.
- `GET /api/hazards/eonet`, `/api/hazards/firms`, and `/api/hazards/nws` expose source-native records for drill-in and debugging.
- The frontend keeps no global hazard cache; hazard rendering remains viewport-scoped and time-aware.
