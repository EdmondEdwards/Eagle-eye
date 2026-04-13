# Eagle Eye Architecture

Eagle Eye v1 is a local-only OSINT analyst workstation designed around three concerns:

1. Collection
   - `apps/worker` polls or streams external public data sources.
   - `packages/source-adapters` normalizes each source into canonical records.

2. Storage and replay
   - PostgreSQL/PostGIS stores separate current-state and append-only history tables.
   - Redis carries low-latency live update envelopes to the API websocket layer.
   - Retention cleanup trims history tables to the configured `RETENTION_DAYS`.

3. Analyst workflow
   - `apps/api` exposes REST endpoints for live state, history playback, search, and analyst objects.
   - `apps/web` renders a Cesium-powered globe and dense workstation layout for cases, notes, watchlists, overlays, and replay.

The v1 system is intentionally local-only and unauthenticated so it can be stood up quickly inside a trusted network boundary.

