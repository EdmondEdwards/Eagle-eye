CREATE TABLE IF NOT EXISTS satellites_catalog (
  id TEXT PRIMARY KEY,
  norad_cat_id TEXT NOT NULL UNIQUE,
  international_designator TEXT,
  name TEXT NOT NULL,
  object_type TEXT,
  group_name TEXT,
  orbit_class TEXT,
  source TEXT NOT NULL,
  tle_line1 TEXT,
  tle_line2 TEXT,
  epoch TIMESTAMPTZ,
  inclination_deg DOUBLE PRECISION,
  eccentricity DOUBLE PRECISION,
  mean_motion DOUBLE PRECISION,
  raan_deg DOUBLE PRECISION,
  arg_perigee_deg DOUBLE PRECISION,
  mean_anomaly_deg DOUBLE PRECISION,
  bstar DOUBLE PRECISION,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  observed_at TIMESTAMPTZ NOT NULL,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_satellites_catalog_norad ON satellites_catalog (norad_cat_id);
CREATE INDEX IF NOT EXISTS idx_satellites_catalog_group ON satellites_catalog (group_name);
CREATE INDEX IF NOT EXISTS idx_satellites_catalog_name ON satellites_catalog (name);
CREATE INDEX IF NOT EXISTS idx_satellites_catalog_epoch ON satellites_catalog (epoch DESC);

CREATE TABLE IF NOT EXISTS satellites_current (
  id TEXT PRIMARY KEY,
  norad_cat_id TEXT NOT NULL UNIQUE,
  catalog_number TEXT,
  international_designator TEXT,
  name TEXT NOT NULL,
  satellite_name TEXT,
  object_type TEXT,
  group_name TEXT,
  orbit_class TEXT,
  source TEXT NOT NULL,
  tle_line1 TEXT,
  tle_line2 TEXT,
  epoch TIMESTAMPTZ,
  tle_epoch TIMESTAMPTZ,
  inclination_deg DOUBLE PRECISION,
  eccentricity DOUBLE PRECISION,
  mean_motion DOUBLE PRECISION,
  raan_deg DOUBLE PRECISION,
  arg_perigee_deg DOUBLE PRECISION,
  mean_anomaly_deg DOUBLE PRECISION,
  bstar DOUBLE PRECISION,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  observed_at TIMESTAMPTZ NOT NULL,
  altitude_m DOUBLE PRECISION,
  velocity_kts DOUBLE PRECISION,
  computed_lat DOUBLE PRECISION NOT NULL,
  computed_lon DOUBLE PRECISION NOT NULL,
  computed_alt_km DOUBLE PRECISION,
  computed_velocity_kms DOUBLE PRECISION,
  geom geometry(Point, 4326) NOT NULL,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_satellites_current_geom ON satellites_current USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_satellites_current_observed_at ON satellites_current (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_satellites_current_norad ON satellites_current (norad_cat_id);
CREATE INDEX IF NOT EXISTS idx_satellites_current_group ON satellites_current (group_name);

CREATE TABLE IF NOT EXISTS satellites_history (
  history_id BIGSERIAL PRIMARY KEY,
  entity_id TEXT NOT NULL,
  norad_cat_id TEXT NOT NULL,
  catalog_number TEXT,
  international_designator TEXT,
  name TEXT NOT NULL,
  satellite_name TEXT,
  object_type TEXT,
  group_name TEXT,
  orbit_class TEXT,
  source TEXT NOT NULL,
  tle_line1 TEXT,
  tle_line2 TEXT,
  epoch TIMESTAMPTZ,
  tle_epoch TIMESTAMPTZ,
  inclination_deg DOUBLE PRECISION,
  eccentricity DOUBLE PRECISION,
  mean_motion DOUBLE PRECISION,
  raan_deg DOUBLE PRECISION,
  arg_perigee_deg DOUBLE PRECISION,
  mean_anomaly_deg DOUBLE PRECISION,
  bstar DOUBLE PRECISION,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  observed_at TIMESTAMPTZ NOT NULL,
  altitude_m DOUBLE PRECISION,
  velocity_kts DOUBLE PRECISION,
  computed_lat DOUBLE PRECISION NOT NULL,
  computed_lon DOUBLE PRECISION NOT NULL,
  computed_alt_km DOUBLE PRECISION,
  computed_velocity_kms DOUBLE PRECISION,
  playback_confidence DOUBLE PRECISION,
  geom geometry(Point, 4326) NOT NULL,
  source_snapshot_id UUID,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_satellites_history_entity_time ON satellites_history (entity_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_satellites_history_norad_time ON satellites_history (norad_cat_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_satellites_history_observed_at ON satellites_history (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_satellites_history_geom ON satellites_history USING GIST (geom);

CREATE TABLE IF NOT EXISTS satellite_source_snapshots (
  snapshot_id UUID PRIMARY KEY,
  satellite_id TEXT NOT NULL,
  norad_cat_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  group_name TEXT,
  payload_format TEXT NOT NULL,
  epoch TIMESTAMPTZ,
  observed_at TIMESTAMPTZ NOT NULL,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_satellite_source_snapshots_norad_time ON satellite_source_snapshots (norad_cat_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_satellite_source_snapshots_provider_time ON satellite_source_snapshots (provider, observed_at DESC);
