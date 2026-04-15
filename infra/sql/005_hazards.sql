CREATE TABLE IF NOT EXISTS hazard_source_health (
  source_key TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  source_type TEXT NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  status TEXT NOT NULL DEFAULT 'idle',
  last_success_at TIMESTAMPTZ,
  last_error_at TIMESTAMPTZ,
  last_error TEXT,
  item_count INTEGER NOT NULL DEFAULT 0,
  details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hazard_source_health_status ON hazard_source_health (status, updated_at DESC);

CREATE TABLE IF NOT EXISTS eonet_events (
  id BIGSERIAL PRIMARY KEY,
  eonet_event_id TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  description TEXT,
  link TEXT,
  status TEXT NOT NULL,
  categories_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  sources_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  closed_at TIMESTAMPTZ,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw_event_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eonet_events_status ON eonet_events (status, closed_at DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_eonet_events_seen ON eonet_events (first_seen_at DESC, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_eonet_events_categories ON eonet_events USING GIN (categories_json);
CREATE INDEX IF NOT EXISTS idx_eonet_events_sources ON eonet_events USING GIN (sources_json);

CREATE TABLE IF NOT EXISTS eonet_event_geometry (
  id BIGSERIAL PRIMARY KEY,
  eonet_event_id TEXT NOT NULL REFERENCES eonet_events(eonet_event_id) ON DELETE CASCADE,
  geometry_type TEXT NOT NULL,
  event_time TIMESTAMPTZ,
  geometry geometry(Geometry, 4326) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eonet_event_geometry_event_id ON eonet_event_geometry (eonet_event_id, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_eonet_event_geometry_geom ON eonet_event_geometry USING GIST (geometry);

CREATE TABLE IF NOT EXISTS firms_detections (
  id BIGSERIAL PRIMARY KEY,
  firms_detection_id TEXT NOT NULL UNIQUE,
  source_sensor TEXT NOT NULL,
  acquisition_time TIMESTAMPTZ NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  brightness DOUBLE PRECISION,
  confidence TEXT,
  frp DOUBLE PRECISION,
  daynight TEXT,
  satellite TEXT,
  raw_detection_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  geometry geometry(Point, 4326) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_firms_detections_sensor_time ON firms_detections (source_sensor, acquisition_time DESC);
CREATE INDEX IF NOT EXISTS idx_firms_detections_daynight ON firms_detections (daynight, acquisition_time DESC);
CREATE INDEX IF NOT EXISTS idx_firms_detections_geom ON firms_detections USING GIST (geometry);

CREATE TABLE IF NOT EXISTS nws_alerts (
  id BIGSERIAL PRIMARY KEY,
  nws_alert_id TEXT NOT NULL UNIQUE,
  event TEXT NOT NULL,
  severity TEXT,
  certainty TEXT,
  urgency TEXT,
  status TEXT NOT NULL,
  sent TIMESTAMPTZ,
  effective TIMESTAMPTZ,
  onset TIMESTAMPTZ,
  expires TIMESTAMPTZ,
  headline TEXT,
  description TEXT,
  instruction TEXT,
  area_desc TEXT,
  parameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  raw_alert_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  geometry geometry(Geometry, 4326),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nws_alerts_status ON nws_alerts (status, effective DESC, expires DESC);
CREATE INDEX IF NOT EXISTS idx_nws_alerts_event ON nws_alerts (event, severity, urgency);
CREATE INDEX IF NOT EXISTS idx_nws_alerts_geom ON nws_alerts USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_nws_alerts_parameters ON nws_alerts USING GIN (parameters_json);

CREATE TABLE IF NOT EXISTS hazard_events_normalized (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  severity TEXT,
  confidence DOUBLE PRECISION,
  start_time TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ,
  geometry geometry(Geometry, 4326),
  properties_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (source, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_hazard_events_normalized_source ON hazard_events_normalized (source, type, status);
CREATE INDEX IF NOT EXISTS idx_hazard_events_normalized_time ON hazard_events_normalized (start_time DESC, end_time DESC);
CREATE INDEX IF NOT EXISTS idx_hazard_events_normalized_geom ON hazard_events_normalized USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_hazard_events_normalized_props ON hazard_events_normalized USING GIN (properties_json);

