CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS aircraft_current (
  id TEXT PRIMARY KEY,
  icao24 TEXT NOT NULL,
  callsign TEXT,
  registration TEXT,
  operator TEXT,
  geom geometry(Point, 4326) NOT NULL,
  altitude_m DOUBLE PRECISION,
  heading_deg DOUBLE PRECISION,
  velocity_kts DOUBLE PRECISION,
  vertical_rate DOUBLE PRECISION,
  source TEXT NOT NULL,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  observed_at TIMESTAMPTZ NOT NULL,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aircraft_current_geom ON aircraft_current USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_aircraft_current_observed_at ON aircraft_current (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_aircraft_current_icao24 ON aircraft_current (icao24);

CREATE TABLE IF NOT EXISTS aircraft_history (
  history_id BIGSERIAL PRIMARY KEY,
  entity_id TEXT NOT NULL,
  icao24 TEXT NOT NULL,
  callsign TEXT,
  registration TEXT,
  operator TEXT,
  geom geometry(Point, 4326) NOT NULL,
  altitude_m DOUBLE PRECISION,
  heading_deg DOUBLE PRECISION,
  velocity_kts DOUBLE PRECISION,
  vertical_rate DOUBLE PRECISION,
  speed_kts DOUBLE PRECISION,
  source TEXT NOT NULL,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  observed_at TIMESTAMPTZ NOT NULL,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_aircraft_history_entity_time ON aircraft_history (entity_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_aircraft_history_observed_at ON aircraft_history (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_aircraft_history_geom ON aircraft_history USING GIST (geom);

CREATE TABLE IF NOT EXISTS vessels_current (
  id TEXT PRIMARY KEY,
  mmsi TEXT NOT NULL,
  imo TEXT,
  vessel_name TEXT,
  vessel_type TEXT,
  flag TEXT,
  geom geometry(Point, 4326) NOT NULL,
  heading_deg DOUBLE PRECISION,
  speed_kts DOUBLE PRECISION,
  source TEXT NOT NULL,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  observed_at TIMESTAMPTZ NOT NULL,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vessels_current_geom ON vessels_current USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_vessels_current_observed_at ON vessels_current (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_vessels_current_mmsi ON vessels_current (mmsi);

CREATE TABLE IF NOT EXISTS vessels_history (
  history_id BIGSERIAL PRIMARY KEY,
  entity_id TEXT NOT NULL,
  mmsi TEXT NOT NULL,
  imo TEXT,
  vessel_name TEXT,
  vessel_type TEXT,
  flag TEXT,
  geom geometry(Point, 4326) NOT NULL,
  heading_deg DOUBLE PRECISION,
  speed_kts DOUBLE PRECISION,
  altitude_m DOUBLE PRECISION,
  velocity_kts DOUBLE PRECISION,
  source TEXT NOT NULL,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  observed_at TIMESTAMPTZ NOT NULL,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vessels_history_entity_time ON vessels_history (entity_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_vessels_history_observed_at ON vessels_history (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_vessels_history_geom ON vessels_history USING GIST (geom);

CREATE TABLE IF NOT EXISTS airspace_overlays (
  id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  geom geometry(Geometry, 4326),
  active_from TIMESTAMPTZ,
  active_to TIMESTAMPTZ,
  source TEXT NOT NULL,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_airspace_overlays_geom ON airspace_overlays USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_airspace_overlays_active_window ON airspace_overlays (active_from, active_to);
CREATE INDEX IF NOT EXISTS idx_airspace_overlays_name ON airspace_overlays (name);

CREATE TABLE IF NOT EXISTS cases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  summary TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  priority TEXT NOT NULL DEFAULT 'medium',
  source TEXT NOT NULL DEFAULT 'user',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS case_entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  entity_kind TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  role TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_case_entities_case_id ON case_entities (case_id);
CREATE INDEX IF NOT EXISTS idx_case_entities_entity_ref ON case_entities (entity_kind, entity_id);

CREATE TABLE IF NOT EXISTS notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_id UUID REFERENCES cases(id) ON DELETE SET NULL,
  entity_kind TEXT,
  entity_id TEXT,
  body TEXT NOT NULL,
  author TEXT NOT NULL DEFAULT 'local-analyst',
  source TEXT NOT NULL DEFAULT 'user',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notes_case_id ON notes (case_id);
CREATE INDEX IF NOT EXISTS idx_notes_entity_ref ON notes (entity_kind, entity_id);

CREATE TABLE IF NOT EXISTS tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  color TEXT NOT NULL DEFAULT '#6ee7ff',
  source TEXT NOT NULL DEFAULT 'user',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS entity_tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  case_id UUID REFERENCES cases(id) ON DELETE CASCADE,
  entity_kind TEXT,
  entity_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entity_tags_tag_id ON entity_tags (tag_id);
CREATE INDEX IF NOT EXISTS idx_entity_tags_entity_ref ON entity_tags (entity_kind, entity_id);

CREATE TABLE IF NOT EXISTS watchlists (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  color TEXT NOT NULL DEFAULT '#4ade80',
  source TEXT NOT NULL DEFAULT 'user',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS watchlist_entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  watchlist_id UUID NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
  entity_kind TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  label TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watchlist_entities_watchlist_id ON watchlist_entities (watchlist_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_entities_entity_ref ON watchlist_entities (entity_kind, entity_id);

CREATE TABLE IF NOT EXISTS saved_views (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  center_lat DOUBLE PRECISION NOT NULL,
  center_lon DOUBLE PRECISION NOT NULL,
  center_altitude DOUBLE PRECISION NOT NULL,
  heading_deg DOUBLE PRECISION NOT NULL,
  pitch_deg DOUBLE PRECISION NOT NULL,
  roll_deg DOUBLE PRECISION NOT NULL,
  layers JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_cases_updated_at ON cases;
CREATE TRIGGER trg_cases_updated_at BEFORE UPDATE ON cases FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_notes_updated_at ON notes;
CREATE TRIGGER trg_notes_updated_at BEFORE UPDATE ON notes FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_tags_updated_at ON tags;
CREATE TRIGGER trg_tags_updated_at BEFORE UPDATE ON tags FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_watchlists_updated_at ON watchlists;
CREATE TRIGGER trg_watchlists_updated_at BEFORE UPDATE ON watchlists FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_saved_views_updated_at ON saved_views;
CREATE TRIGGER trg_saved_views_updated_at BEFORE UPDATE ON saved_views FOR EACH ROW EXECUTE FUNCTION set_updated_at();

