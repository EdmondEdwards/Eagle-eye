CREATE TABLE IF NOT EXISTS time_state (
  singleton BOOLEAN PRIMARY KEY DEFAULT TRUE,
  mode TEXT NOT NULL DEFAULT 'live',
  status TEXT NOT NULL DEFAULT 'playing',
  current_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  playback_speed DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  step_seconds INTEGER NOT NULL DEFAULT 60,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (singleton = TRUE),
  CHECK (mode IN ('live', 'paused', 'replay', 'simulate')),
  CHECK (status IN ('playing', 'paused'))
);

INSERT INTO time_state (singleton, mode, status, current_timestamp, playback_speed, step_seconds)
VALUES (TRUE, 'live', 'playing', NOW(), 1.0, 60)
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type TEXT NOT NULL,
  category TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'medium',
  title TEXT NOT NULL,
  summary TEXT,
  entity_kind TEXT,
  entity_id TEXT,
  related_entity_kind TEXT,
  related_entity_id TEXT,
  geom geometry(Geometry, 4326),
  start_time TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status TEXT NOT NULL DEFAULT 'open',
  confidence DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  source TEXT NOT NULL DEFAULT 'system',
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.7,
  raw_reference TEXT,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_geom ON events USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_events_start_time ON events (start_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_status ON events (status, severity, start_time DESC);
CREATE INDEX IF NOT EXISTS idx_events_entity_ref ON events (entity_kind, entity_id, start_time DESC);

CREATE TABLE IF NOT EXISTS relationships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_kind TEXT NOT NULL,
  source_id TEXT NOT NULL,
  target_kind TEXT NOT NULL,
  target_id TEXT NOT NULL,
  relationship_type TEXT NOT NULL,
  strength DOUBLE PRECISION NOT NULL DEFAULT 0.5,
  context_event_id UUID REFERENCES events(id) ON DELETE SET NULL,
  context_case_id UUID REFERENCES cases(id) ON DELETE SET NULL,
  source TEXT NOT NULL DEFAULT 'system',
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.7,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_relationships_source_ref ON relationships (source_kind, source_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_relationships_target_ref ON relationships (target_kind, target_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships (relationship_type, observed_at DESC);

CREATE TABLE IF NOT EXISTS aois (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  geometry_type TEXT NOT NULL,
  geom geometry(Geometry, 4326) NOT NULL,
  center_geom geometry(Point, 4326),
  radius_m DOUBLE PRECISION,
  tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  source TEXT NOT NULL DEFAULT 'user',
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  CHECK (geometry_type IN ('polygon', 'rectangle', 'circle'))
);

CREATE INDEX IF NOT EXISTS idx_aois_geom ON aois USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_aois_center_geom ON aois USING GIST (center_geom);

CREATE TABLE IF NOT EXISTS workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  camera JSONB NOT NULL DEFAULT '{}'::jsonb,
  time_context JSONB NOT NULL DEFAULT '{}'::jsonb,
  layers JSONB NOT NULL DEFAULT '{}'::jsonb,
  selected_entities JSONB NOT NULL DEFAULT '[]'::jsonb,
  selected_aois JSONB NOT NULL DEFAULT '[]'::jsonb,
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

CREATE INDEX IF NOT EXISTS idx_watchlist_entities_watchlist_id ON watchlist_entities (watchlist_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_watchlist_entities_entity_ref ON watchlist_entities (entity_kind, entity_id);

CREATE OR REPLACE VIEW analyst_workspace_summary AS
SELECT
  w.id,
  w.name,
  w.description,
  w.camera,
  w.time_context,
  w.layers,
  w.selected_entities,
  w.selected_aois,
  w.source,
  w.created_at,
  w.updated_at
FROM workspaces w;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'saved_views'
      AND column_name = 'layers'
  ) THEN
    ALTER TABLE saved_views ADD COLUMN layers JSONB NOT NULL DEFAULT '{}'::jsonb;
  END IF;
EXCEPTION
  WHEN undefined_table THEN
    NULL;
END $$;
