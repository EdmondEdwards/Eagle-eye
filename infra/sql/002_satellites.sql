CREATE TABLE IF NOT EXISTS satellites_current (
  id TEXT PRIMARY KEY,
  catalog_number TEXT NOT NULL,
  satellite_name TEXT NOT NULL,
  international_designator TEXT,
  group_name TEXT,
  orbit_class TEXT,
  geom geometry(Point, 4326) NOT NULL,
  altitude_m DOUBLE PRECISION,
  velocity_kts DOUBLE PRECISION,
  tle_epoch TIMESTAMPTZ,
  source TEXT NOT NULL,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  observed_at TIMESTAMPTZ NOT NULL,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_satellites_current_geom ON satellites_current USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_satellites_current_observed_at ON satellites_current (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_satellites_current_catalog ON satellites_current (catalog_number);

CREATE TABLE IF NOT EXISTS satellites_history (
  history_id BIGSERIAL PRIMARY KEY,
  entity_id TEXT NOT NULL,
  catalog_number TEXT NOT NULL,
  satellite_name TEXT NOT NULL,
  international_designator TEXT,
  group_name TEXT,
  orbit_class TEXT,
  geom geometry(Point, 4326) NOT NULL,
  altitude_m DOUBLE PRECISION,
  velocity_kts DOUBLE PRECISION,
  tle_epoch TIMESTAMPTZ,
  source TEXT NOT NULL,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  observed_at TIMESTAMPTZ NOT NULL,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_satellites_history_entity_time ON satellites_history (entity_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_satellites_history_observed_at ON satellites_history (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_satellites_history_geom ON satellites_history USING GIST (geom);
