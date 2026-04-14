export type TimeMode = "live" | "paused" | "replay" | "simulate";
export type PlaybackStatus = "playing" | "paused";

export interface GlobeViewState {
  west: number;
  south: number;
  east: number;
  north: number;
  camera_height: number;
  heading: number;
  pitch: number;
  roll: number;
  timestamp: string;
  mode: "live" | "replay" | "simulate";
  enabled_layers: string[];
  selected_entities: string[];
  selected_aois: string[];
}

export interface TimeState {
  mode: TimeMode;
  status: PlaybackStatus;
  current_timestamp: string;
  playback_speed: number;
  step_seconds: number;
  updated_at: string;
}

export interface ClusterRecord {
  id: string;
  entity_kind: "aircraft" | "vessel" | "satellite" | "event";
  count: number;
  lat: number;
  lon: number;
  sample_ids: string[];
}

export interface EntityRecord {
  id: string;
  entity_kind: "aircraft" | "vessel" | "satellite" | "airspace" | "aoi";
  label: string;
  geometry: GeoJsonGeometry;
  properties: Record<string, unknown>;
  observed_at: string;
  predicted_path: TimelinePoint[];
}

export interface EventRecord {
  id: string;
  event_type: string;
  category: string;
  severity: string;
  title: string;
  summary?: string | null;
  entity_kind?: string | null;
  entity_id?: string | null;
  related_entity_kind?: string | null;
  related_entity_id?: string | null;
  geometry?: GeoJsonGeometry | null;
  start_time: string;
  end_time?: string | null;
  detected_at: string;
  status: string;
  confidence: number;
  source: string;
  source_confidence: number;
  raw_reference?: string | null;
}

export interface RelationshipRecord {
  id: string;
  source_kind: string;
  source_id: string;
  target_kind: string;
  target_id: string;
  relationship_type: string;
  strength: number;
  context_event_id?: string | null;
  context_case_id?: string | null;
  source: string;
  source_confidence: number;
  observed_at: string;
  raw_payload: Record<string, unknown>;
}

export interface ViewQueryResponse {
  view: GlobeViewState;
  entities: EntityRecord[];
  clusters: ClusterRecord[];
  events: EventRecord[];
  relationships: RelationshipRecord[];
  stats: Record<string, number>;
}

export interface GeoJsonGeometry {
  type: string;
  coordinates?: unknown;
}

export interface Aircraft {
  id: string;
  icao24: string;
  callsign?: string | null;
  registration?: string | null;
  operator?: string | null;
  aircraft_category?: string | null;
  lat: number;
  lon: number;
  altitude_m?: number | null;
  heading_deg?: number | null;
  velocity_kts?: number | null;
  vertical_rate?: number | null;
}

export interface Vessel {
  id: string;
  mmsi: string;
  vessel_name?: string | null;
  callsign?: string | null;
  lat: number;
  lon: number;
  heading_deg?: number | null;
  course_deg?: number | null;
  speed_kts?: number | null;
}

export interface Satellite {
  id: string;
  norad_cat_id: string;
  name: string;
  computed_lat: number;
  computed_lon: number;
  computed_alt_km?: number | null;
}

export interface TimelinePoint {
  lat: number;
  lon: number;
  observed_at: string;
  altitude_m?: number | null;
  confidence?: number | null;
}

export interface EntityTimelineResponse {
  entity_id: string;
  entity_kind: string;
  history: TimelinePoint[];
  predicted: TimelinePoint[];
  window: Record<string, string>;
}

export interface AoiRecord {
  id: string;
  name: string;
  description?: string | null;
  geometry_type: "polygon" | "rectangle" | "circle";
  geometry: GeoJsonGeometry;
  center?: GeoJsonGeometry | null;
  radius_m?: number | null;
  tags: string[];
  source: string;
  source_confidence: number;
  observed_at: string;
  updated_at: string;
}

export interface WorkspaceRecord {
  id: string;
  name: string;
  description?: string | null;
  camera: Record<string, unknown>;
  time_context: Record<string, unknown>;
  layers: Record<string, unknown>;
  selected_entities: string[];
  selected_aois: string[];
  source: string;
  created_at: string;
  updated_at: string;
}

export interface CaseEntity {
  entity_kind: string;
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

export interface WatchlistEntityRecord {
  id: string;
  entity_kind: string;
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
  entities: WatchlistEntityRecord[];
}

export interface CaseUpdate {
  title?: string | null;
  summary?: string | null;
  status?: string | null;
  priority?: string | null;
}

export interface NoteUpdate {
  body?: string | null;
  case_id?: string | null;
}

export interface WatchlistUpdate {
  name?: string | null;
  description?: string | null;
  color?: string | null;
}

export interface AoiUpdate {
  name?: string | null;
  description?: string | null;
  radius_m?: number | null;
  tags?: string[];
}

export interface TagRecord {
  id: string;
  name: string;
  color: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface SatelliteFovResponse {
  satellite_id: string;
  timestamp: string;
  footprint: GeoJsonGeometry & { properties?: Record<string, unknown> };
  cone: Record<string, unknown>;
  swath_km: number;
}

export interface SatellitePassResponse {
  satellite_id: string;
  target: Record<string, unknown>;
  passes: Array<Record<string, unknown>>;
}

export interface LiveEnvelope {
  topic: string;
  action: string;
  payload: Record<string, unknown>;
}

export interface SourceStatusRecord {
  key: string;
  label: string;
  domain: string;
  status: string;
  last_observed_at?: string | null;
  item_count: number;
  details: Record<string, unknown>;
}

export interface InvestigationBundle {
  entity?: EntityRecord | null;
  events: EventRecord[];
  relationships: RelationshipRecord[];
  notes: NoteRecord[];
  aois: AoiRecord[];
  watchlists: WatchlistRecord[];
  satellite_fov?: SatelliteFovResponse | null;
  satellite_passes: Array<Record<string, unknown>>;
  timeline?: EntityTimelineResponse | null;
  aoi_events: EventRecord[];
  aoi_passes: Array<Record<string, unknown>>;
}
