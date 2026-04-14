# Webcam Seed Catalog

## Purpose

Eagle Eye's webcam seed catalog is a curated starter layer of intentionally public cameras that add visual context to air, maritime, infrastructure, weather, and public-place investigations. The seed is designed for local-first intelligence workflows, not mass camera discovery.

The catalog intentionally avoids:

- unsecured or accidentally exposed cameras
- residential or privacy-sensitive viewpoints
- assumptions about embed rights on third-party platforms
- brittle scraping dependencies

## Trust Model

Only intentionally public sources from reputable operators should be cataloged.

Approved source patterns:

- official airport, port, city, park, transport, and weather agency cameras
- public wildlife streams from recognized operators
- official or clearly public livestream pages
- curated public directories such as EarthCam, Skyline Webcams, Webcam Galore, and similar services, handled conservatively

Disallowed source patterns:

- open directory listings
- default-password or vendor-console cameras
- cameras discovered through network scanning
- user-uploaded streams without clear public intent

## Access Rules

`access_mode` controls how Eagle Eye should present a camera:

- `embed`: use only when the provider explicitly supports embedded playback
- `preview_only`: show catalog metadata and thumbnail-style previews, but route the user to the provider page for live viewing
- `link_only`: treat the record as a nearby visual context source and open the provider page in a separate tab or panel

Default provider guidance:

- `YouTube Live`: `embed` only when the stream is official and embedding is not disabled
- `EarthCam`: `link_only` by default
- `Skyline Webcams`: `preview_only` or `link_only` by default
- `Explore.org`: `link_only` by default
- `Webcam Galore` and other directories: `preview_only` or `link_only`
- official agency sources: conservative default is `link_only` unless explicit embed support exists

## Category Definitions

- `airport`: runway, apron, or terminal-adjacent views useful for flight-context monitoring
- `port`: harbors, container terminals, anchorages, and channel approaches
- `city`: skyline and downtown overview cameras
- `traffic`: road, bridge, and interchange cameras
- `rail`: passenger stations, rail corridors, yards, and railfan viewpoints
- `weather`: weather, storm, snow, volcanic, or environmental-observation cameras
- `coast`: beaches, bays, harbor entrances, surf lines, and shoreline cameras
- `wildlife`: intentionally public animal and habitat cameras
- `public_square`: plazas, civic landmarks, and dense public gathering points
- `infrastructure`: bridges, straits, canals, dams, and other fixed strategic assets

## Seed File Layout

The seed lives in:

- `/Users/edmondedwards/Desktop/Eagle eye/data/webcams/approved_webcams_seed.json`
- `/Users/edmondedwards/Desktop/Eagle eye/data/webcams/approved_webcams_seed.yaml`

The JSON file is the canonical machine-readable source. The YAML file is an equivalent JSON-compatible YAML representation so the catalog can be loaded in environments that prefer `.yaml`.

Each entry contains:

- identity: `id`, `provider`, `provider_camera_id`
- geospatial context: `country`, `region`, `city`, `lat`, `lon`
- workflow typing: `category`, `subcategory`, `tags`, `priority`
- access controls: `watch_url`, `embed_url`, `access_mode`, `embed_allowed`
- confidence and notes: `source_confidence`, `metadata`

## Validation And Import

Validate the seed:

```bash
python3 scripts/validate_seed_webcams.py data/webcams/approved_webcams_seed.json
python3 scripts/validate_seed_webcams.py data/webcams/approved_webcams_seed.yaml
```

Import into PostgreSQL/PostGIS:

```bash
DATABASE_URL=postgresql://eagle:eagle@localhost:5432/eagle_eye \
python3 scripts/import_seed_webcams.py --file data/webcams/approved_webcams_seed.json
```

The importer:

- validates before writing
- updates existing rows by `provider + provider_camera_id` when available
- otherwise updates by `provider + watch_url`
- writes `geom` using `ST_SetSRID(ST_MakePoint(lon, lat), 4326)`

## Extension Workflow

When adding new cameras:

1. Confirm the source is intentionally public and operationally appropriate.
2. Prefer the provider page over direct media URLs.
3. Default to `link_only` unless embed permission is clear.
4. Use precise geospatial coordinates for nearby-camera lookup.
5. Add tags that make AOI and event workflows easier, such as `runway`, `container-port`, `storm-watch`, or `rail-yard`.
6. Re-run validation before import.

## Provider Handling Notes

Use `embed_allowed=true` only when the provider model clearly supports it. For all other providers:

- keep `embed_url` empty
- set `embed_allowed=false`
- use `preview_only` or `link_only`

This keeps the catalog safe, durable, and aligned with provider intent.

## Example AOI Query

Find approved cameras within 25 km of an AOI centroid:

```sql
SELECT
  w.id,
  w.name,
  w.category,
  w.provider,
  w.watch_url,
  ST_Distance(w.geom::geography, a.geom::geography) AS distance_m
FROM webcams w
JOIN aois a ON a.id = 'aoi:strait-watch'
WHERE w.approved = TRUE
  AND ST_DWithin(w.geom::geography, a.geom::geography, 25000)
ORDER BY distance_m ASC, w.priority ASC
LIMIT 20;
```
