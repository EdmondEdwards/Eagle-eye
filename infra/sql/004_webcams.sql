CREATE TABLE IF NOT EXISTS webcams (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  provider TEXT NOT NULL,
  provider_camera_id TEXT,
  country TEXT NOT NULL,
  region TEXT NOT NULL,
  city TEXT NOT NULL,
  lat DOUBLE PRECISION NOT NULL,
  lon DOUBLE PRECISION NOT NULL,
  geom geometry(Point, 4326) NOT NULL,
  category TEXT NOT NULL,
  subcategory TEXT NOT NULL,
  watch_url TEXT NOT NULL,
  embed_url TEXT,
  preview_image_url TEXT,
  access_mode TEXT NOT NULL,
  embed_allowed BOOLEAN NOT NULL DEFAULT FALSE,
  source_confidence DOUBLE PRECISION NOT NULL DEFAULT 0.75,
  tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
  priority SMALLINT NOT NULL DEFAULT 2,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  approved BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK (category IN ('airport', 'port', 'city', 'traffic', 'rail', 'weather', 'coast', 'wildlife', 'public_square', 'infrastructure')),
  CHECK (access_mode IN ('embed', 'preview_only', 'link_only')),
  CHECK (priority IN (1, 2, 3)),
  CHECK (lat BETWEEN -90 AND 90),
  CHECK (lon BETWEEN -180 AND 180)
);

CREATE INDEX IF NOT EXISTS idx_webcams_geom ON webcams USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_webcams_category ON webcams (category, priority, country);
CREATE INDEX IF NOT EXISTS idx_webcams_provider ON webcams (provider, country, city);
CREATE INDEX IF NOT EXISTS idx_webcams_tags ON webcams USING GIN (tags);

CREATE UNIQUE INDEX IF NOT EXISTS uq_webcams_provider_camera
  ON webcams (provider, provider_camera_id)
  WHERE provider_camera_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_webcams_provider_watch
  ON webcams (provider, watch_url);
