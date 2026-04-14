export type SourceName =
  | "opensky"
  | "aisstream"
  | "aishub"
  | "global_fishing_watch"
  | "celestrak"
  | "spacetrack"
  | "n2yo"
  | "faa_tfr"
  | "webcam_catalog_placeholder"
  | "user"
  | "system";

export interface SourceProvenance {
  source: SourceName | string;
  source_confidence: number;
  observed_at: string;
  raw_reference?: string | null;
}

export interface GeoPoint {
  lat: number;
  lon: number;
}

export interface GeoJsonGeometry {
  type: string;
  coordinates?: unknown;
  geometries?: GeoJsonGeometry[];
}

export interface Aircraft extends SourceProvenance, GeoPoint {
  id: string;
  icao24: string;
  callsign?: string | null;
  registration?: string | null;
  operator?: string | null;
  aircraft_category?: string | null;
  altitude_m?: number | null;
  heading_deg?: number | null;
  velocity_kts?: number | null;
  vertical_rate?: number | null;
}

export interface Vessel extends SourceProvenance, GeoPoint {
  id: string;
  mmsi: string;
  imo?: string | null;
  vessel_name?: string | null;
  callsign?: string | null;
  vessel_type?: string | null;
  flag?: string | null;
  heading_deg?: number | null;
  course_deg?: number | null;
  speed_kts?: number | null;
  nav_status?: string | null;
  destination?: string | null;
  draught_m?: number | null;
  source_record_id?: string | null;
  merged_confidence?: number | null;
  last_ingested_at?: string | null;
  stale?: boolean;
}

export interface VesselSourceHealthRecord {
  provider_name: string;
  ingest_mode: "websocket" | "polling" | "batch";
  enabled: boolean;
  priority: number;
  health_state: "healthy" | "degraded" | "unhealthy" | "disabled";
  last_success?: string | null;
  last_attempt?: string | null;
  valid_message_count: number;
  error_count: number;
  stall_threshold_seconds?: number | null;
  last_error?: string | null;
  updated_at: string;
}

export interface MaritimeProviderDescriptor {
  provider_name: string;
  ingest_mode: "websocket" | "polling" | "batch";
  priority: number;
  enabled: boolean;
  description?: string | null;
}

export interface VesselPresenceOverlayRecord extends SourceProvenance {
  overlay_id: string;
  provider: string;
  dataset: string;
  label: string;
  category: string;
  geometry: GeoJsonGeometry;
  density?: number | null;
  observed_from: string;
  observed_to: string;
}

export interface Satellite extends SourceProvenance {
  id: string;
  norad_cat_id: string;
  international_designator?: string | null;
  name: string;
  object_type?: string | null;
  group_name?: string | null;
  orbit_class?: string | null;
  tle_line1?: string | null;
  tle_line2?: string | null;
  epoch?: string | null;
  inclination_deg?: number | null;
  eccentricity?: number | null;
  mean_motion?: number | null;
  raan_deg?: number | null;
  arg_perigee_deg?: number | null;
  mean_anomaly_deg?: number | null;
  bstar?: number | null;
  computed_lat: number;
  computed_lon: number;
  computed_alt_km?: number | null;
  computed_velocity_kms?: number | null;
  playback_confidence?: number | null;
}

export interface SatelliteCatalogRecord extends SourceProvenance {
  id: string;
  norad_cat_id: string;
  international_designator?: string | null;
  name: string;
  object_type?: string | null;
  group_name?: string | null;
  orbit_class?: string | null;
  tle_line1?: string | null;
  tle_line2?: string | null;
  epoch?: string | null;
  inclination_deg?: number | null;
  eccentricity?: number | null;
  mean_motion?: number | null;
  raan_deg?: number | null;
  arg_perigee_deg?: number | null;
  mean_anomaly_deg?: number | null;
  bstar?: number | null;
}

export interface AirspaceOverlay extends SourceProvenance {
  id: string;
  source_id: string;
  name: string;
  category: string;
  geometry?: GeoJsonGeometry | null;
  active_from?: string | null;
  active_to?: string | null;
}

export interface EventPlaceholder extends SourceProvenance {
  id: string;
  title: string;
  category: string;
  location?: GeoPoint | null;
}

export interface CaseEntity {
  entity_kind: "aircraft" | "vessel" | "satellite" | "airspace";
  entity_id: string;
  role?: string | null;
}

export interface CaseRecord {
  id: string;
  title: string;
  summary?: string | null;
  status: string;
  priority: string;
  source: string;
  created_at: string;
  updated_at: string;
  entities: CaseEntity[];
}

export interface NoteRecord {
  id: string;
  case_id?: string | null;
  entity_kind?: string | null;
  entity_id?: string | null;
  body: string;
  author: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface TagRecord {
  id: string;
  name: string;
  color: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface TagAssignment {
  id: string;
  tag_id: string;
  case_id?: string | null;
  entity_kind?: string | null;
  entity_id?: string | null;
  created_at: string;
}

export interface WatchlistEntity {
  id: string;
  entity_kind: "aircraft" | "vessel" | "satellite";
  entity_id: string;
  label?: string | null;
  created_at: string;
}

export interface WatchlistRecord {
  id: string;
  name: string;
  description?: string | null;
  color: string;
  source: string;
  created_at: string;
  updated_at: string;
  entities: WatchlistEntity[];
}

export interface SavedViewRecord {
  id: string;
  name: string;
  description?: string | null;
  center_lat: number;
  center_lon: number;
  center_altitude: number;
  heading_deg: number;
  pitch_deg: number;
  roll_deg: number;
  layers: Record<string, boolean>;
  created_at: string;
  updated_at: string;
}

export interface TimelinePoint extends GeoPoint {
  observed_at: string;
  altitude_m?: number | null;
  alt_km?: number | null;
  heading_deg?: number | null;
  velocity_kts?: number | null;
  velocity_kms?: number | null;
  speed_kts?: number | null;
  confidence?: number | null;
}

export interface TimelineTrack {
  entity_id: string;
  label: string;
  entity_kind: "aircraft" | "vessel" | "satellite";
  points: TimelinePoint[];
}

export interface TimelineResponse {
  window: {
    from: string;
    to: string;
  };
  tracks: TimelineTrack[];
}

export interface OrbitPathResponse {
  norad_cat_id: string;
  source: string;
  epoch?: string | null;
  points: TimelinePoint[];
}

export interface SearchResult {
  kind: string;
  id: string;
  label: string;
  subtitle?: string | null;
  source?: string | null;
  observed_at?: string | null;
  location?: GeoPoint | null;
}

export interface LiveEnvelope {
  topic:
    | "aircraft"
    | "vessel"
    | "satellite"
    | "airspace"
    | "vessel.source-health"
    | "satellite.batch"
    | "heartbeat";
  action: "upsert" | "delete";
  payload: Record<string, unknown>;
}
