export type SourceName =
  | "opensky"
  | "aisstream"
  | "celestrak"
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
  vessel_type?: string | null;
  flag?: string | null;
  heading_deg?: number | null;
  speed_kts?: number | null;
}

export interface Satellite extends SourceProvenance, GeoPoint {
  id: string;
  catalog_number: string;
  satellite_name: string;
  international_designator?: string | null;
  group_name?: string | null;
  orbit_class?: string | null;
  altitude_m?: number | null;
  velocity_kts?: number | null;
  tle_epoch?: string | null;
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
  heading_deg?: number | null;
  velocity_kts?: number | null;
  speed_kts?: number | null;
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
  topic: "aircraft" | "vessel" | "satellite" | "airspace" | "heartbeat";
  action: "upsert" | "delete";
  payload: Record<string, unknown>;
}
