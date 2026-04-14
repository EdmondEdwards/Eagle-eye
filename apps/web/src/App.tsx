import {
  ArcType,
  Cartesian2,
  Cartesian3,
  Color,
  DistanceDisplayCondition,
  Entity,
  GeoJsonDataSource,
  Ion,
  JulianDate,
  LabelStyle,
  Math as CesiumMath,
  NearFarScalar,
  PropertyBag,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  VerticalOrigin,
  Viewer
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { startTransition, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type {
    Aircraft,
    AirspaceOverlay,
    CaseRecord,
    MaritimeProviderDescriptor,
    NoteRecord,
    SavedViewRecord,
    SearchResult,
    Satellite,
    TimelinePoint,
    TimelineTrack,
    Vessel,
    VesselPresenceOverlayRecord,
    VesselSourceHealthRecord,
    WatchlistRecord
} from "@eagle-eye/shared-types";
import { detailTabs, layerDefinitions } from "@eagle-eye/ui";
import { api, connectLiveFeed } from "./lib/api";
import { aircraftColorForAircraft, aircraftIconForAircraft, resolveAircraftCategory } from "./lib/aircraftIconMap";
import satelliteImage from "./assets/sat.png";

type SelectedEntity =
  | ({ kind: "aircraft" } & Aircraft)
  | ({ kind: "vessel" } & Vessel)
  | ({ kind: "satellite" } & Satellite)
  | ({ kind: "airspace" } & AirspaceOverlay)
  | null;

type GlobeEntityPayload =
  | { kind: "aircraft"; data: Aircraft }
  | { kind: "vessel"; data: Vessel }
  | { kind: "satellite"; data: Satellite }
  | { kind: "airspace"; data: AirspaceOverlay };

type LayerState = Record<string, boolean>;

type CameraPreset = {
  key: string;
  label: string;
  lat: number;
  lon: number;
  altitude: number;
  headingDeg?: number;
  pitchDeg?: number;
};

type ViewBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
  crossesAntimeridian: boolean;
  bbox: string | null;
};

const defaultLayers: LayerState = {
  aircraft: true,
  vessels: true,
  vesselPresence: false,
  satellites: true,
  airspace: true,
  webcams: false
};

const AIRCRAFT_COLOR = "#ffd54a";
const AIRCRAFT_SELECTED_COLOR = "#fff4b3";
const VESSEL_COLOR = "#6ee7ff";
const VESSEL_SELECTED_COLOR = "#b6f4ff";
const SATELLITE_COLOR = "#9af6b0";
const SATELLITE_SELECTED_COLOR = "#dcffd3";

const cameraPresets: readonly CameraPreset[] = [
  { key: "global", label: "Global", lat: 28, lon: -20, altitude: 22_000_000, headingDeg: 0, pitchDeg: -90 },
  { key: "conus", label: "CONUS", lat: 39.5, lon: -98.35, altitude: 5_600_000, headingDeg: 0, pitchDeg: -72 },
  { key: "europe", label: "Europe", lat: 50.2, lon: 8.6, altitude: 3_600_000, headingDeg: 8, pitchDeg: -70 },
  { key: "mena", label: "MENA", lat: 27.8, lon: 40.2, altitude: 4_800_000, headingDeg: 12, pitchDeg: -72 },
  { key: "indo", label: "Indo-Pacific", lat: 13.1, lon: 110.5, altitude: 8_800_000, headingDeg: 18, pitchDeg: -76 }
];

const VESSEL_ICON = `data:image/svg+xml;utf8,${encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
    <path fill="#061019" fill-opacity="0.42" d="M8 38h48l-4 10-20 10L12 48z"/>
    <path fill="#6ee7ff" stroke="#061019" stroke-width="2" d="M9 38h46l-4 10-19 10-19-10z"/>
    <path fill="#6ee7ff" stroke="#061019" stroke-width="2" d="M22 17h20v16H22z"/>
    <path fill="#061019" fill-opacity="0.3" d="M26 22h12v8H26z"/>
  </svg>
`)}`;

function isoNowMinus(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

function formatAltitudeFeet(altitudeMeters?: number | null): string | null {
  if (altitudeMeters == null) return null;
  return `${Math.round(altitudeMeters * 3.28084).toLocaleString()} ft`;
}

function formatKnots(speed?: number | null): string | null {
  if (speed == null) return null;
  return `${Math.round(speed)} kt`;
}

function formatAltitudeKm(altitudeMeters?: number | null): string | null {
  if (altitudeMeters == null) return null;
  return `${(altitudeMeters / 1000).toFixed(0)} km`;
}

function formatVelocityKms(speed?: number | null): string | null {
  if (speed == null) return null;
  return `${speed.toFixed(2)} km/s`;
}

function entityLabel(entity: SelectedEntity): string {
  if (!entity) return "No selection";
  if (entity.kind === "aircraft") return entity.callsign?.trim() || entity.icao24;
  if (entity.kind === "vessel") return entity.vessel_name?.trim() || entity.mmsi;
  if (entity.kind === "satellite") return entity.name?.trim() || entity.norad_cat_id;
  return entity.name;
}

function projectTrackVector(
  lat: number,
  lon: number,
  headingDeg?: number | null,
  distanceNm = 20
): { lat: number; lon: number } | null {
  if (headingDeg == null || Number.isNaN(headingDeg)) {
    return null;
  }

  const earthRadiusNm = 3440.065;
  const angularDistance = distanceNm / earthRadiusNm;
  const bearing = CesiumMath.toRadians(headingDeg);
  const lat1 = CesiumMath.toRadians(lat);
  const lon1 = CesiumMath.toRadians(lon);

  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(angularDistance) +
      Math.cos(lat1) * Math.sin(angularDistance) * Math.cos(bearing)
  );
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(lat1),
      Math.cos(angularDistance) - Math.sin(lat1) * Math.sin(lat2)
    );

  return {
    lat: CesiumMath.toDegrees(lat2),
    lon: ((CesiumMath.toDegrees(lon2) + 540) % 360) - 180
  };
}

function aircraftLabel(item: Aircraft, isSelected: boolean): string {
  const primary = item.callsign?.trim() || item.registration?.trim() || item.icao24;
  if (!isSelected) {
    return primary.toUpperCase();
  }

  const secondary = [
    resolveAircraftCategory(item).replaceAll("_", " ").toUpperCase(),
    formatAltitudeFeet(item.altitude_m),
    formatKnots(item.velocity_kts)
  ]
    .filter(Boolean)
    .join(" • ");
  return secondary ? `${primary.toUpperCase()}\n${secondary}` : primary.toUpperCase();
}

function vesselLabel(item: Vessel, isSelected: boolean): string {
  const freshness = item.stale ? "STALE" : "LIVE";
  const primary = item.vessel_name?.trim() || item.callsign?.trim() || item.mmsi;
  if (!isSelected) {
    return primary;
  }

  const secondary = [item.vessel_type?.trim(), formatKnots(item.speed_kts), freshness].filter(Boolean).join(" • ");
  return secondary ? `${primary}\n${secondary}` : primary;
}

function satelliteLabel(item: Satellite, isSelected: boolean): string {
  if (!isSelected) {
    return item.name;
  }
  const secondary = [item.orbit_class, formatAltitudeKm(item.computed_alt_km != null ? item.computed_alt_km * 1000 : null)].filter(Boolean).join(" • ");
  return secondary ? `${item.name}\n${secondary}` : item.name;
}

function pointAltitudeMeters(point: TimelinePoint): number {
  if (point.altitude_m != null) return point.altitude_m;
  if (point.alt_km != null) return point.alt_km * 1000;
  return 0;
}

function centroidFromAirspace(overlay: AirspaceOverlay): { lat: number; lon: number } | null {
  const coordinates = overlay.geometry?.coordinates;
  if (!Array.isArray(coordinates)) {
    return null;
  }

  const points: Array<[number, number]> = [];

  const visit = (value: unknown): void => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === "number" && typeof value[1] === "number") {
      points.push([value[0], value[1]]);
      return;
    }
    value.forEach(visit);
  };

  visit(coordinates);
  if (points.length === 0) {
    return null;
  }

  const [lonSum, latSum] = points.reduce(
    (acc, [lon, lat]) => [acc[0] + lon, acc[1] + lat],
    [0, 0]
  );

  return {
    lat: latSum / points.length,
    lon: lonSum / points.length
  };
}

function normalizeLongitude(lon: number): number {
  return ((lon + 540) % 360) - 180;
}

function buildViewBounds(viewer: Viewer): ViewBounds | null {
  const rectangle = viewer.camera.computeViewRectangle(viewer.scene.globe.ellipsoid);
  if (!rectangle) {
    return null;
  }

  const west = normalizeLongitude(CesiumMath.toDegrees(rectangle.west));
  const east = normalizeLongitude(CesiumMath.toDegrees(rectangle.east));
  const south = CesiumMath.toDegrees(rectangle.south);
  const north = CesiumMath.toDegrees(rectangle.north);

  if (![west, east, south, north].every(Number.isFinite)) {
    return null;
  }

  const crossesAntimeridian = east < west;
  const longitudinalSpan = crossesAntimeridian ? east + 360 - west : east - west;
  const latitudinalSpan = north - south;
  const bbox =
    longitudinalSpan >= 350 || latitudinalSpan >= 170 || crossesAntimeridian
      ? null
      : `${west.toFixed(4)},${south.toFixed(4)},${east.toFixed(4)},${north.toFixed(4)}`;

  return { west, south, east, north, crossesAntimeridian, bbox };
}

function isPointInView(lat: number, lon: number, bounds: ViewBounds | null): boolean {
  if (!bounds) {
    return true;
  }

  const normalizedLon = normalizeLongitude(lon);
  const insideLon = bounds.crossesAntimeridian
    ? normalizedLon >= bounds.west || normalizedLon <= bounds.east
    : normalizedLon >= bounds.west && normalizedLon <= bounds.east;

  return insideLon && lat >= bounds.south && lat <= bounds.north;
}

function viewWindowLabel(bounds: ViewBounds | null): string {
  if (!bounds?.bbox) {
    return "Global window";
  }

  const width = bounds.crossesAntimeridian ? bounds.east + 360 - bounds.west : bounds.east - bounds.west;
  const height = bounds.north - bounds.south;
  return `${Math.max(1, Math.round(width))}° × ${Math.max(1, Math.round(height))}° window`;
}

function zoomBandLabel(cameraHeight: number): string {
  if (cameraHeight >= 14_000_000) return "Orbital";
  if (cameraHeight >= 7_000_000) return "Theater";
  if (cameraHeight >= 2_500_000) return "Regional";
  if (cameraHeight >= 900_000) return "Sector";
  return "Local";
}

function formatCameraAltitude(cameraHeight: number): string {
  if (cameraHeight >= 1_000_000) {
    return `${(cameraHeight / 1_000_000).toFixed(1)} Mm`;
  }
  if (cameraHeight >= 1_000) {
    return `${Math.round(cameraHeight / 1_000)} km`;
  }
  return `${Math.round(cameraHeight)} m`;
}

function trimVisibleEntities<T extends { id: string }>(items: T[], maxItems: number, pinnedId?: string | null): T[] {
  if (items.length <= maxItems) {
    return items;
  }

  const stride = Math.max(1, Math.ceil(items.length / maxItems));
  const sampled = items.filter((_, index) => index % stride === 0).slice(0, maxItems);

  if (!pinnedId || sampled.some((item) => item.id === pinnedId)) {
    return sampled;
  }

  const pinned = items.find((item) => item.id === pinnedId);
  if (!pinned) {
    return sampled;
  }

  return [pinned, ...sampled.slice(0, maxItems - 1)];
}

function createPropertyBag(payload: GlobeEntityPayload): PropertyBag {
  return new PropertyBag({
    kind: payload.kind,
    data: payload.data
  });
}

function readPayload(entity: Entity | null, time: JulianDate): GlobeEntityPayload | null {
  const value = entity?.properties?.getValue(time) as Partial<GlobeEntityPayload> | undefined;
  if (!value || !value.kind || !value.data) {
    return null;
  }

  return value as GlobeEntityPayload;
}

function isAircraftPayload(payload: unknown): payload is Aircraft {
  if (typeof payload !== "object" || payload === null) {
    return false;
  }

  const value = payload as Record<string, unknown>;
  return (
    typeof value.id === "string" &&
    typeof value.icao24 === "string" &&
    typeof value.source === "string" &&
    typeof value.source_confidence === "number" &&
    typeof value.observed_at === "string" &&
    typeof value.lat === "number" &&
    typeof value.lon === "number"
  );
}

function isVesselPayload(payload: unknown): payload is Vessel {
  if (typeof payload !== "object" || payload === null) {
    return false;
  }

  const value = payload as Record<string, unknown>;
  return (
    typeof value.id === "string" &&
    typeof value.mmsi === "string" &&
    typeof value.source === "string" &&
    typeof value.source_confidence === "number" &&
    typeof value.observed_at === "string" &&
    typeof value.lat === "number" &&
    typeof value.lon === "number"
  );
}

function isSatellitePayload(payload: unknown): payload is Satellite {
  if (typeof payload !== "object" || payload === null) {
    return false;
  }

  const value = payload as Record<string, unknown>;
  return (
    typeof value.id === "string" &&
    typeof value.norad_cat_id === "string" &&
    typeof value.name === "string" &&
    typeof value.source === "string" &&
    typeof value.source_confidence === "number" &&
    typeof value.observed_at === "string" &&
    typeof value.computed_lat === "number" &&
    typeof value.computed_lon === "number"
  );
}

function toSelectedEntity(payload: GlobeEntityPayload): SelectedEntity {
  if (payload.kind === "aircraft") {
    return { kind: "aircraft", ...payload.data };
  }
  if (payload.kind === "vessel") {
    return { kind: "vessel", ...payload.data };
  }
  if (payload.kind === "satellite") {
    return { kind: "satellite", ...payload.data };
  }
  return { kind: "airspace", ...payload.data };
}

function flyCameraToLocation(
  viewer: Viewer,
  lat: number,
  lon: number,
  altitude: number,
  headingDeg = 0,
  pitchDeg = -72,
  duration = 1.15
) {
  viewer.camera.flyTo({
    destination: Cartesian3.fromDegrees(lon, lat, altitude),
    orientation: {
      heading: CesiumMath.toRadians(headingDeg),
      pitch: CesiumMath.toRadians(pitchDeg),
      roll: 0
    },
    duration
  });
}

function focusEntityInViewer(viewer: Viewer, entity: SelectedEntity): boolean {
  if (!entity) {
    return false;
  }

  if (entity.kind === "satellite") {
    flyCameraToLocation(viewer, entity.computed_lat, entity.computed_lon, 2_200_000, 0, -74, 1.2);
    return true;
  }

  if ("lat" in entity) {
    flyCameraToLocation(
      viewer,
      entity.lat,
      entity.lon,
      entity.kind === "aircraft" ? 1_050_000 : 1_400_000,
      "heading_deg" in entity ? entity.heading_deg ?? 0 : 0,
      entity.kind === "aircraft" ? -66 : -69,
      1.2
    );
    return true;
  }

  const centroid = centroidFromAirspace(entity);
  if (!centroid) {
    return false;
  }

  flyCameraToLocation(viewer, centroid.lat, centroid.lon, 2_800_000, 0, -76, 1.2);
  return true;
}

export default function App() {
  const viewerRef = useRef<Viewer | null>(null);
  const viewerHostRef = useRef<HTMLDivElement | null>(null);
  const airspaceSourceRef = useRef<GeoJsonDataSource | null>(null);
  const vesselPresenceSourceRef = useRef<GeoJsonDataSource | null>(null);
  const viewQueryRef = useRef("");
  const [layers, setLayers] = useState<LayerState>(defaultLayers);
  const [selected, setSelected] = useState<SelectedEntity>(null);
  const [detailTab, setDetailTab] = useState<(typeof detailTabs)[number]>("details");
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [satellites, setSatellites] = useState<Satellite[]>([]);
  const [airspace, setAirspace] = useState<AirspaceOverlay[]>([]);
  const [vesselPresenceOverlays, setVesselPresenceOverlays] = useState<VesselPresenceOverlayRecord[]>([]);
  const [vesselSourceHealth, setVesselSourceHealth] = useState<VesselSourceHealthRecord[]>([]);
  const [vesselProviders, setVesselProviders] = useState<MaritimeProviderDescriptor[]>([]);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [watchlists, setWatchlists] = useState<WatchlistRecord[]>([]);
  const [notes, setNotes] = useState<NoteRecord[]>([]);
  const [savedViews, setSavedViews] = useState<SavedViewRecord[]>([]);
  const [timelineMode, setTimelineMode] = useState<"live" | "paused" | "replay">("live");
  const [timelineMinutes, setTimelineMinutes] = useState(60);
  const [replaySpeed, setReplaySpeed] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [aircraftTracks, setAircraftTracks] = useState<TimelineTrack[]>([]);
  const [vesselTracks, setVesselTracks] = useState<TimelineTrack[]>([]);
  const [satelliteTracks, setSatelliteTracks] = useState<TimelineTrack[]>([]);
  const [satelliteOrbitPoints, setSatelliteOrbitPoints] = useState<TimelinePoint[]>([]);
  const [status, setStatus] = useState("Loading operational picture...");
  const [activePreset, setActivePreset] = useState<string>("global");
  const [viewBounds, setViewBounds] = useState<ViewBounds | null>(null);
  const [cameraHeight, setCameraHeight] = useState(22_000_000);

  const selectedNotes = useMemo(
    () =>
      notes.filter((note) => {
        if (!selected) return false;
        return note.entity_id === selected.id;
      }),
    [notes, selected]
  );

  const relatedCases = useMemo(
    () => cases.filter((record) => selected && record.entities.some((entity) => entity.entity_id === selected.id)),
    [cases, selected]
  );

  const relatedWatchlists = useMemo(
    () => watchlists.filter((record) => selected && record.entities.some((entity) => entity.entity_id === selected.id)),
    [selected, watchlists]
  );
  const primaryVesselHealth = useMemo(
    () => vesselSourceHealth.find((item) => item.provider_name === "aisstream") ?? vesselSourceHealth[0] ?? null,
    [vesselSourceHealth]
  );
  const selectedKey = selected ? `${selected.kind}:${selected.id}` : null;
  const viewQuery = viewBounds?.bbox ?? "";
  const visibleAircraft = useMemo(
    () => aircraft.filter((item) => isPointInView(item.lat, item.lon, viewBounds)).slice(0, 2200),
    [aircraft, viewBounds]
  );
  const visibleVessels = useMemo(
    () => vessels.filter((item) => isPointInView(item.lat, item.lon, viewBounds)).slice(0, 1400),
    [vessels, viewBounds]
  );
  const visibleSatellites = useMemo(
    () => satellites.filter((item) => isPointInView(item.computed_lat, item.computed_lon, viewBounds)).slice(0, 1000),
    [satellites, viewBounds]
  );
  const aircraftRenderBudget = cameraHeight >= 12_000_000 ? 900 : cameraHeight >= 5_500_000 ? 1_500 : 2_200;
  const vesselRenderBudget = cameraHeight >= 12_000_000 ? 420 : cameraHeight >= 5_500_000 ? 850 : 1_400;
  const satelliteRenderBudget = cameraHeight >= 12_000_000 ? 240 : cameraHeight >= 5_500_000 ? 460 : 760;
  const renderedAircraft = useMemo(
    () => trimVisibleEntities(visibleAircraft, aircraftRenderBudget, selected?.kind === "aircraft" ? selected.id : null),
    [aircraftRenderBudget, selected, visibleAircraft]
  );
  const renderedVessels = useMemo(
    () => trimVisibleEntities(visibleVessels, vesselRenderBudget, selected?.kind === "vessel" ? selected.id : null),
    [selected, vesselRenderBudget, visibleVessels]
  );
  const renderedSatellites = useMemo(
    () => trimVisibleEntities(visibleSatellites, satelliteRenderBudget, selected?.kind === "satellite" ? selected.id : null),
    [satelliteRenderBudget, selected, visibleSatellites]
  );
  const zoomBand = useMemo(() => zoomBandLabel(cameraHeight), [cameraHeight]);
  const renderedTrackCount = renderedAircraft.length + renderedVessels.length + renderedSatellites.length;
  const aircraftLabelsEnabled = cameraHeight < 6_500_000;
  const vesselLabelsEnabled = cameraHeight < 4_200_000;
  const satelliteLabelsEnabled = cameraHeight < 7_500_000;
  const vectorsEnabled = cameraHeight < 8_500_000;

  useEffect(() => {
    viewQueryRef.current = viewQuery;
  }, [viewQuery]);

  function flyToPreset(preset: CameraPreset) {
    const viewer = viewerRef.current;
    if (!viewer) return;
    flyCameraToLocation(viewer, preset.lat, preset.lon, preset.altitude, preset.headingDeg ?? 0, preset.pitchDeg ?? -76, 1.15);
    setActivePreset(preset.key);
  }

  function zoomCamera(direction: "in" | "out") {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const height = viewer.camera.positionCartographic.height;
    const nextDelta = Math.max(35_000, height * (direction === "in" ? 0.38 : 0.62));
    if (direction === "in") {
      viewer.camera.zoomIn(nextDelta);
    } else {
      viewer.camera.zoomOut(nextDelta);
    }
  }

  function focusSelection() {
    const viewer = viewerRef.current;
    if (!viewer || !selected) return;
    if (focusEntityInViewer(viewer, selected)) {
      setActivePreset("selection");
    }
  }

  function focusTraffic() {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const entities = [...visibleAircraft, ...visibleVessels, ...visibleSatellites];
    if (entities.length === 0) return;

    const sampled = entities.slice(0, 250).map((item) =>
      "computed_lat" in item ? { lat: item.computed_lat, lon: item.computed_lon } : { lat: item.lat, lon: item.lon }
    );
    const latMin = Math.min(...sampled.map((item) => item.lat));
    const latMax = Math.max(...sampled.map((item) => item.lat));
    const lonMin = Math.min(...sampled.map((item) => item.lon));
    const lonMax = Math.max(...sampled.map((item) => item.lon));
    const lat = (latMin + latMax) / 2;
    const lon = (lonMin + lonMax) / 2;
    const span = Math.max(latMax - latMin, lonMax - lonMin);
    const altitude = Math.min(12_000_000, Math.max(1_800_000, span * 155_000));

    flyCameraToLocation(viewer, lat, lon, altitude, 0, -76, 1.15);
    setActivePreset("traffic");
  }

  useEffect(() => {
    Ion.defaultAccessToken = import.meta.env.VITE_CESIUM_ION_TOKEN ?? "";

    if (!viewerHostRef.current || viewerRef.current) {
      return;
    }

    const viewer = new Viewer(viewerHostRef.current, {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      fullscreenButton: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      infoBox: false,
      selectionIndicator: false
    });

    viewer.scene.globe.enableLighting = true;
    viewer.scene.globe.baseColor = Color.fromCssColorString("#07101a");
    viewer.scene.globe.showGroundAtmosphere = false;
    viewer.scene.backgroundColor = Color.fromCssColorString("#02060b");
    viewer.scene.fog.enabled = false;
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = false;
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(-20, 28, 22_000_000),
      duration: 0
    });
    const syncViewBounds = () => {
      setViewBounds(buildViewBounds(viewer));
      setCameraHeight(viewer.camera.positionCartographic.height);
    };
    viewer.camera.moveEnd.addEventListener(syncViewBounds);
    window.setTimeout(syncViewBounds, 0);

    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction((movement: { position: Cartesian2 }) => {
      const picked = viewer.scene.pick(movement.position);
      const entity = picked && "id" in picked ? (picked.id as Entity) : null;
      const payload = readPayload(entity, viewer.clock.currentTime);
      if (!payload) {
        return;
      }
      if (payload.kind === "aircraft") {
        setSelected({ kind: "aircraft", ...payload.data });
      } else if (payload.kind === "vessel") {
        setSelected({ kind: "vessel", ...payload.data });
      } else if (payload.kind === "satellite") {
        setSelected({ kind: "satellite", ...payload.data });
      } else if (payload.kind === "airspace") {
        setSelected({ kind: "airspace", ...payload.data });
      }
    }, ScreenSpaceEventType.LEFT_CLICK);
    handler.setInputAction((movement: { position: Cartesian2 }) => {
      const picked = viewer.scene.pick(movement.position);
      const entity = picked && "id" in picked ? (picked.id as Entity) : null;
      const payload = readPayload(entity, viewer.clock.currentTime);
      if (!payload) {
        return;
      }
      const nextSelected = toSelectedEntity(payload);
      setSelected(nextSelected);
      if (focusEntityInViewer(viewer, nextSelected)) {
        setActivePreset("selection");
      }
    }, ScreenSpaceEventType.LEFT_DOUBLE_CLICK);

    viewerRef.current = viewer;
    return () => {
      viewer.camera.moveEnd.removeEventListener(syncViewBounds);
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  async function loadOperationalData(bbox?: string | null) {
    try {
      setStatus("Synchronizing live data...");
      const [
        nextAircraft,
        nextVessels,
        nextSatellites,
        nextAirspace,
        nextVesselPresence,
        nextVesselHealth,
        nextVesselProviders,
        nextCases,
        nextWatchlists,
        nextNotes,
        nextViews
      ] = await Promise.all([
        api.getAircraftCurrent(bbox ?? undefined),
        api.getVesselsCurrent(bbox ?? undefined),
        api.getSatellitesCurrent(bbox ?? undefined),
        api.getAirspaceCurrent(),
        api.getVesselPresenceOverlay(),
        api.getVesselSourceHealth(),
        api.getVesselProviders(),
        api.getCases(),
        api.getWatchlists(),
        api.getNotes(),
        api.getSavedViews()
      ]);

      startTransition(() => {
        setAircraft(nextAircraft);
        setVessels(nextVessels);
        setSatellites(nextSatellites);
        setAirspace(nextAirspace);
        setVesselPresenceOverlays(nextVesselPresence);
        setVesselSourceHealth(nextVesselHealth);
        setVesselProviders(nextVesselProviders);
        setCases(nextCases);
        setWatchlists(nextWatchlists);
        setNotes(nextNotes);
        setSavedViews(nextViews);
        setStatus(
          `Live traffic: ${nextAircraft.length} airborne, ${nextVessels.length} maritime, ${nextSatellites.length} orbital, ${nextAirspace.length} overlays in view.`
        );
      });
    } catch {
      setStatus("API unavailable. Check Eagle Eye services and VITE_API_BASE_URL.");
    }
  }

  useEffect(() => {
    void loadOperationalData(viewQuery || null);
    const intervalId = window.setInterval(() => {
      if (timelineMode === "live") {
        void loadOperationalData(viewQuery || null);
      }
    }, 15_000);

    return () => window.clearInterval(intervalId);
  }, [timelineMode, viewQuery]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryId: number | undefined;
    let closed = false;

    const connect = () => {
      socket = connectLiveFeed((message) => {
        if (message.topic === "aircraft") {
          setAircraft((current) => {
            if (!isAircraftPayload(message.payload)) {
              return current;
            }
            const next = [...current];
            const payload = message.payload;
            const index = next.findIndex((item) => item.id === payload.id);
            if (index >= 0) next[index] = payload;
            else next.unshift(payload);
            return next.slice(0, 5000);
          });
        }

        if (message.topic === "vessel") {
          setVessels((current) => {
            if (!isVesselPayload(message.payload)) {
              return current;
            }
            const next = [...current];
            const payload = message.payload;
            const index = next.findIndex((item) => item.id === payload.id);
            if (index >= 0) next[index] = payload;
            else next.unshift(payload);
            return next.slice(0, 5000);
          });
        }

        if (message.topic === "vessel.source-health") {
          const providers = (message.payload.providers as VesselSourceHealthRecord[] | undefined) ?? [];
          if (Array.isArray(providers)) {
            setVesselSourceHealth(providers);
          }
        }

        if (message.topic === "satellite") {
          setSatellites((current) => {
            if (!isSatellitePayload(message.payload)) {
              return current;
            }
            const next = [...current];
            const payload = message.payload;
            const index = next.findIndex((item) => item.id === payload.id);
            if (index >= 0) next[index] = payload;
            else next.unshift(payload);
            return next.slice(0, 3000);
          });
        }

        if (message.topic === "airspace") {
          void loadOperationalData(viewQueryRef.current || null);
        }
      });

      socket.onopen = () => setStatus((current) => (current.includes("unavailable") ? "Live feed connected." : current));
      socket.onerror = () => setStatus("Live websocket unavailable. Retrying connection...");
      socket.onclose = () => {
        if (!closed) {
          retryId = window.setTimeout(connect, 3000);
        }
      };
    };

    connect();

    return () => {
      closed = true;
      if (retryId) window.clearTimeout(retryId);
      socket?.close();
    };
  }, []);

  useEffect(() => {
    if (!viewerRef.current) return;
    const viewer = viewerRef.current;
    viewer.entities.removeAll();

    if (layers.aircraft) {
      renderedAircraft.forEach((item) => {
        const isSelected = selectedKey === `aircraft:${item.id}`;
        const aircraftColor = aircraftColorForAircraft(item);
        const vectorDistanceNm = Math.max(12, Math.min(42, (item.velocity_kts ?? 280) / 12));
        const vectorEnd = projectTrackVector(item.lat, item.lon, item.heading_deg, vectorDistanceNm);
        viewer.entities.add({
          id: item.id,
          position: Cartesian3.fromDegrees(item.lon, item.lat, item.altitude_m ?? 0),
          point: isSelected
            ? {
                pixelSize: 7,
                color: Color.fromCssColorString(AIRCRAFT_SELECTED_COLOR).withAlpha(0.18),
                outlineColor: Color.fromCssColorString("#0a0f14").withAlpha(0.26),
                outlineWidth: 1,
                disableDepthTestDistance: Number.POSITIVE_INFINITY
              }
            : undefined,
          billboard: {
            image: aircraftIconForAircraft(item),
            verticalOrigin: VerticalOrigin.CENTER,
            rotation: CesiumMath.toRadians(item.heading_deg ?? 0),
            alignedAxis: Cartesian3.UNIT_Z,
            scale: isSelected ? 0.92 : 0.78,
            scaleByDistance: new NearFarScalar(120_000, isSelected ? 0.12 : 0.09, 22_000_000, isSelected ? 1.18 : 0.94),
            color: Color.fromCssColorString(isSelected ? AIRCRAFT_SELECTED_COLOR : aircraftColor),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label: isSelected || aircraftLabelsEnabled
            ? {
                text: aircraftLabel(item, isSelected),
                font: isSelected ? "600 13px IBM Plex Sans" : "600 11px IBM Plex Sans",
                fillColor: Color.fromCssColorString("#dbe7f4"),
                outlineColor: Color.fromCssColorString("#07111c"),
                outlineWidth: 2,
                style: LabelStyle.FILL_AND_OUTLINE,
                showBackground: true,
                backgroundColor: Color.fromCssColorString(isSelected ? "#152537" : "#0d1724").withAlpha(isSelected ? 0.92 : 0.78),
                backgroundPadding: new Cartesian2(8, 6),
                pixelOffset: new Cartesian2(0, 24),
                scale: isSelected ? 0.84 : 0.72,
                scaleByDistance: new NearFarScalar(180_000, 1, 6_000_000, 0.7),
                distanceDisplayCondition: new DistanceDisplayCondition(0, isSelected ? 12_000_000 : 3_600_000),
                disableDepthTestDistance: Number.POSITIVE_INFINITY
              }
            : undefined,
          polyline: vectorsEnabled && vectorEnd
            ? {
                positions: [
                  Cartesian3.fromDegrees(item.lon, item.lat, item.altitude_m ?? 0),
                  Cartesian3.fromDegrees(vectorEnd.lon, vectorEnd.lat, item.altitude_m ?? 0)
                ],
                width: isSelected ? 3 : 1.6,
                material: Color.fromCssColorString(isSelected ? AIRCRAFT_SELECTED_COLOR : aircraftColor).withAlpha(isSelected ? 0.9 : 0.48),
                arcType: ArcType.NONE,
                distanceDisplayCondition: new DistanceDisplayCondition(0, 9_000_000)
              }
            : undefined,
          properties: createPropertyBag({ kind: "aircraft", data: item })
        });
      });
    }

    if (layers.vessels) {
      renderedVessels.forEach((item) => {
        const isSelected = selectedKey === `vessel:${item.id}`;
        const vectorDistanceNm = Math.max(2, Math.min(12, (item.speed_kts ?? 16) / 2.2));
        const vectorEnd = projectTrackVector(item.lat, item.lon, item.heading_deg, vectorDistanceNm);
        viewer.entities.add({
          id: item.id,
          position: Cartesian3.fromDegrees(item.lon, item.lat, 0),
          point: {
            pixelSize: isSelected ? 10 : 6,
            color: Color.fromCssColorString(isSelected ? VESSEL_SELECTED_COLOR : VESSEL_COLOR).withAlpha(isSelected ? 0.32 : 0.16),
            outlineColor: Color.fromCssColorString("#0a0f14").withAlpha(0.28),
            outlineWidth: 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          billboard: {
            image: VESSEL_ICON,
            verticalOrigin: VerticalOrigin.CENTER,
            rotation: CesiumMath.toRadians(item.heading_deg ?? 0),
            alignedAxis: Cartesian3.UNIT_Z,
            scale: isSelected ? 0.72 : 0.56,
            scaleByDistance: new NearFarScalar(150_000, isSelected ? 0.24 : 0.15, 22_000_000, isSelected ? 0.9 : 0.74),
            color: Color.fromCssColorString(isSelected ? VESSEL_SELECTED_COLOR : VESSEL_COLOR),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label: (item.vessel_name?.trim() && vesselLabelsEnabled) || isSelected
            ? {
                text: vesselLabel(item, isSelected),
                font: isSelected ? "600 12px IBM Plex Sans" : "600 10px IBM Plex Sans",
                fillColor: Color.fromCssColorString("#dbe7f4"),
                outlineColor: Color.fromCssColorString("#07111c"),
                outlineWidth: 2,
                style: LabelStyle.FILL_AND_OUTLINE,
                showBackground: true,
                backgroundColor: Color.fromCssColorString("#0d1724").withAlpha(isSelected ? 0.92 : 0.76),
                backgroundPadding: new Cartesian2(8, 5),
                pixelOffset: new Cartesian2(0, 22),
                scale: isSelected ? 0.8 : 0.68,
                scaleByDistance: new NearFarScalar(150_000, 1, 5_000_000, 0.65),
                distanceDisplayCondition: new DistanceDisplayCondition(0, isSelected ? 10_000_000 : 2_500_000),
                disableDepthTestDistance: Number.POSITIVE_INFINITY
              }
            : undefined,
          polyline: vectorsEnabled && vectorEnd
            ? {
                positions: [
                  Cartesian3.fromDegrees(item.lon, item.lat, 0),
                  Cartesian3.fromDegrees(vectorEnd.lon, vectorEnd.lat, 0)
                ],
                width: isSelected ? 2.4 : 1.2,
                material: Color.fromCssColorString(isSelected ? VESSEL_SELECTED_COLOR : VESSEL_COLOR).withAlpha(isSelected ? 0.72 : 0.32),
                arcType: ArcType.NONE,
                distanceDisplayCondition: new DistanceDisplayCondition(0, 5_500_000)
              }
            : undefined,
          properties: createPropertyBag({ kind: "vessel", data: item })
        });
      });
    }

    if (layers.satellites) {
      renderedSatellites.forEach((item) => {
        const isSelected = selectedKey === `satellite:${item.id}`;
        viewer.entities.add({
          id: item.id,
          position: Cartesian3.fromDegrees(item.computed_lon, item.computed_lat, (item.computed_alt_km ?? 0) * 1000),
          point: isSelected
            ? {
                pixelSize: 9,
                color: Color.fromCssColorString(SATELLITE_SELECTED_COLOR).withAlpha(0.24),
                outlineColor: Color.fromCssColorString("#0a0f14").withAlpha(0.24),
                outlineWidth: 1,
                disableDepthTestDistance: Number.POSITIVE_INFINITY
              }
            : undefined,
          billboard: {
            image: satelliteImage,
            verticalOrigin: VerticalOrigin.CENTER,
            alignedAxis: Cartesian3.UNIT_Z,
            scale: isSelected ? 0.76 : 0.62,
            scaleByDistance: new NearFarScalar(150_000, isSelected ? 0.18 : 0.12, 22_000_000, isSelected ? 1.16 : 0.96),
            color: Color.fromCssColorString(isSelected ? SATELLITE_SELECTED_COLOR : SATELLITE_COLOR),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label: isSelected || satelliteLabelsEnabled
            ? {
                text: satelliteLabel(item, isSelected),
                font: isSelected ? "600 12px IBM Plex Sans" : "600 10px IBM Plex Sans",
                fillColor: Color.fromCssColorString("#dbe7f4"),
                outlineColor: Color.fromCssColorString("#07111c"),
                outlineWidth: 2,
                style: LabelStyle.FILL_AND_OUTLINE,
                showBackground: true,
                backgroundColor: Color.fromCssColorString("#0d1724").withAlpha(isSelected ? 0.9 : 0.74),
                backgroundPadding: new Cartesian2(8, 5),
                pixelOffset: new Cartesian2(0, 22),
                scale: isSelected ? 0.82 : 0.7,
                scaleByDistance: new NearFarScalar(150_000, 0.96, 6_500_000, 0.64),
                distanceDisplayCondition: new DistanceDisplayCondition(0, isSelected ? 14_000_000 : 4_000_000),
                disableDepthTestDistance: Number.POSITIVE_INFINITY
              }
            : undefined,
          properties: createPropertyBag({ kind: "satellite", data: item })
        });
      });
    }

    if (layers.satellites && selected?.kind === "satellite" && satelliteOrbitPoints.length > 1) {
      viewer.entities.add({
        id: `satellite:${selected.norad_cat_id}:orbit`,
        polyline: {
          positions: satelliteOrbitPoints.map((point) => Cartesian3.fromDegrees(point.lon, point.lat, pointAltitudeMeters(point))),
          width: 2.6,
          material: Color.fromCssColorString(SATELLITE_SELECTED_COLOR).withAlpha(0.9)
        }
      });
    }

    [...aircraftTracks, ...vesselTracks, ...satelliteTracks].forEach((track) => {
      if (track.points.length < 2) return;
      const isSelected = Boolean(selected && track.entity_kind === selected.kind && track.entity_id === selected.id);
      viewer.entities.add({
        id: `${track.entity_kind}:${track.entity_id}:track`,
        polyline: {
          positions: track.points.map((point) => Cartesian3.fromDegrees(point.lon, point.lat, pointAltitudeMeters(point))),
          width: isSelected ? 4 : 2.2,
          material: Color.fromCssColorString(
            track.entity_kind === "aircraft" ? AIRCRAFT_COLOR : track.entity_kind === "satellite" ? SATELLITE_COLOR : VESSEL_COLOR
          ).withAlpha(isSelected ? 0.95 : 0.55)
        }
      });
    });
  }, [
    aircraftLabelsEnabled,
    aircraftTracks,
    layers.aircraft,
    layers.satellites,
    layers.vessels,
    renderedAircraft,
    renderedSatellites,
    renderedVessels,
    satelliteLabelsEnabled,
    satelliteOrbitPoints,
    satelliteTracks,
    selected,
    selectedKey,
    vesselLabelsEnabled,
    vesselTracks,
    vectorsEnabled
  ]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const syncAirspace = async () => {
      if (airspaceSourceRef.current) {
        await viewer.dataSources.remove(airspaceSourceRef.current, true);
        airspaceSourceRef.current = null;
      }

      if (!layers.airspace || airspace.length === 0) {
        return;
      }

      const featureCollection = {
        type: "FeatureCollection",
        features: airspace
          .filter((item) => item.geometry)
          .map((item) => ({
            type: "Feature",
            geometry: item.geometry!,
            properties: {
              name: item.name,
              category: item.category,
              kind: "airspace",
              data: item
            }
          }))
      };

      const source = await GeoJsonDataSource.load(featureCollection as Parameters<typeof GeoJsonDataSource.load>[0], {
        stroke: Color.fromCssColorString("#f59e0b"),
        fill: Color.fromCssColorString("#f59e0b").withAlpha(0.12),
        strokeWidth: 2
      });

      source.entities.values.forEach((entity, index) => {
        const item = airspace[index];
        if (!item) return;
        entity.properties = createPropertyBag({
          kind: "airspace",
          data: item
        });
      });

      airspaceSourceRef.current = source;
      await viewer.dataSources.add(source);
    };

    void syncAirspace();
  }, [airspace, layers.airspace]);

  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;

    const syncPresence = async () => {
      if (vesselPresenceSourceRef.current) {
        await viewer.dataSources.remove(vesselPresenceSourceRef.current, true);
        vesselPresenceSourceRef.current = null;
      }

      if (!layers.vesselPresence || vesselPresenceOverlays.length === 0) {
        return;
      }

      const featureCollection = {
        type: "FeatureCollection",
        features: vesselPresenceOverlays.map((item) => ({
          type: "Feature",
          geometry: item.geometry,
          properties: {
            kind: "vessel_presence",
            label: item.label,
            density: item.density,
            provider: item.provider
          }
        }))
      };

      const source = await GeoJsonDataSource.load(featureCollection as Parameters<typeof GeoJsonDataSource.load>[0], {
        stroke: Color.fromCssColorString("#56c9ff").withAlpha(0.75),
        fill: Color.fromCssColorString("#56c9ff").withAlpha(0.12),
        strokeWidth: 1.5
      });

      vesselPresenceSourceRef.current = source;
      await viewer.dataSources.add(source);
    };

    void syncPresence();
  }, [layers.vesselPresence, vesselPresenceOverlays]);

  useEffect(() => {
    if (timelineMode === "live") {
      setAircraftTracks([]);
      setVesselTracks([]);
      setSatelliteTracks([]);
      if (!selected || selected.kind !== "satellite") {
        setSatelliteOrbitPoints([]);
      }
      return;
    }

    setSatelliteOrbitPoints([]);

    const params = new URLSearchParams({
      since: isoNowMinus(timelineMinutes),
      until: new Date().toISOString()
    });

    Promise.all([api.getAircraftHistory(params), api.getVesselsHistory(params), api.getSatellitesHistory(params)])
      .then(([aircraftHistory, vesselHistory, satelliteHistory]) => {
        setAircraftTracks(aircraftHistory.tracks);
        setVesselTracks(vesselHistory.tracks);
        setSatelliteTracks(satelliteHistory.tracks);
      })
      .catch(() => setStatus("Replay data unavailable. Live view remains active."));
  }, [timelineMinutes, timelineMode, replaySpeed]);

  useEffect(() => {
    if (timelineMode !== "live" || !selected) {
      setSatelliteOrbitPoints([]);
      return;
    }

    const params = new URLSearchParams({
      since: isoNowMinus(selected.kind === "satellite" ? 180 : 90),
      until: new Date().toISOString(),
      entity_id: selected.id
    });

    const loadFocusedTrack = async () => {
      try {
        if (selected.kind === "aircraft") {
          const history = await api.getAircraftHistory(params);
          setAircraftTracks(history.tracks.slice(0, 1));
          setVesselTracks([]);
          setSatelliteTracks([]);
          setSatelliteOrbitPoints([]);
          return;
        }
        if (selected.kind === "vessel") {
          const history = await api.getVesselsHistory(params);
          setAircraftTracks([]);
          setVesselTracks(history.tracks.slice(0, 1));
          setSatelliteTracks([]);
          setSatelliteOrbitPoints([]);
          return;
        }
        if (selected.kind === "satellite") {
          const orbitParams = new URLSearchParams({
            minutes_ahead: "120",
            step_seconds: "120",
          });
          const [history, orbit] = await Promise.all([
            api.getSatellitesHistory(params),
            api.getSatelliteOrbit(selected.norad_cat_id, orbitParams),
          ]);
          setAircraftTracks([]);
          setVesselTracks([]);
          setSatelliteTracks(history.tracks.slice(0, 1));
          setSatelliteOrbitPoints(orbit.points);
          return;
        }
        setAircraftTracks([]);
        setVesselTracks([]);
        setSatelliteTracks([]);
        setSatelliteOrbitPoints([]);
      } catch {
        setStatus("Focused track history is unavailable right now.");
      }
    };

    void loadFocusedTrack();
    const intervalId = window.setInterval(() => void loadFocusedTrack(), 30_000);
    return () => window.clearInterval(intervalId);
  }, [selected, timelineMode]);

  async function runSearch() {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    try {
      const results = await api.search(searchQuery.trim());
      setSearchResults(results);
      setStatus(`Search returned ${results.length} result${results.length === 1 ? "" : "s"}.`);
    } catch {
      setStatus("Search failed. Confirm the API is reachable from the browser.");
    }
  }

  async function createCase() {
    const title = window.prompt("Case title");
    if (!title) return;
    try {
      const created = await api.createCase({ title, status: "active", priority: "medium" });
      setCases((current) => [created, ...current]);
    } catch {
      setStatus("Unable to create case while the API is unavailable.");
    }
  }

  async function createWatchlist() {
    const name = window.prompt("Watchlist name");
    if (!name) return;
    try {
      const created = await api.createWatchlist({ name, color: "#6ee7ff" });
      setWatchlists((current) => [created, ...current]);
    } catch {
      setStatus("Unable to create watchlist while the API is unavailable.");
    }
  }

  async function createNote() {
    const body = window.prompt("Analyst note");
    if (!body || !selected) return;
    try {
      const created = await api.createNote({
        body,
        entity_id: selected.id,
        entity_kind: selected.kind
      });
      setNotes((current) => [created, ...current]);
    } catch {
      setStatus("Unable to create note while the API is unavailable.");
    }
  }

  async function saveView() {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const cartographic = viewer.camera.positionCartographic;
    try {
      const created = await api.createSavedView({
        name: `Saved View ${savedViews.length + 1}`,
        center_lat: CesiumMath.toDegrees(cartographic.latitude),
        center_lon: CesiumMath.toDegrees(cartographic.longitude),
        center_altitude: cartographic.height,
        heading_deg: CesiumMath.toDegrees(viewer.camera.heading),
        pitch_deg: CesiumMath.toDegrees(viewer.camera.pitch),
        roll_deg: CesiumMath.toDegrees(viewer.camera.roll),
        layers
      });
      setSavedViews((current) => [created, ...current]);
    } catch {
      setStatus("Unable to save view while the API is unavailable.");
    }
  }

  function flyToSavedView(view: SavedViewRecord) {
    const viewer = viewerRef.current;
    if (!viewer) return;
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(view.center_lon, view.center_lat, view.center_altitude),
      orientation: {
        heading: CesiumMath.toRadians(view.heading_deg),
        pitch: CesiumMath.toRadians(view.pitch_deg),
        roll: CesiumMath.toRadians(view.roll_deg)
      }
    });
    setLayers((current) => ({ ...current, ...view.layers }));
  }

  return (
    <div className="app-shell">
      <aside className="sidebar left">
        <div className="panel">
          <div className="panel-header">
            <span>Sources</span>
            <span className="muted">{status}</span>
          </div>
          <div className="source-list">
            <div className="source-row">
              <strong>OpenSky</strong>
              <span>{renderedAircraft.length} rendered</span>
            </div>
            <div className="source-row">
              <strong>AISStream</strong>
              <span>{renderedVessels.length} rendered · {primaryVesselHealth?.health_state ?? "unknown"}</span>
            </div>
            <div className="source-row">
              <strong>Maritime Providers</strong>
              <span>{vesselProviders.filter((item) => item.enabled).length} enabled</span>
            </div>
            <div className="source-row">
              <strong>Vessel Presence</strong>
              <span>{vesselPresenceOverlays.length} overlays</span>
            </div>
            <div className="source-row">
              <strong>CelesTrak</strong>
              <span>{renderedSatellites.length} rendered</span>
            </div>
            <div className="source-row">
              <strong>FAA TFR</strong>
              <span>{airspace.length} overlays</span>
            </div>
            <div className="source-row disabled">
              <strong>Webcams</strong>
              <span>Catalog only in v1.5</span>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span>Watchlists</span>
            <button onClick={() => void createWatchlist()}>New</button>
          </div>
          <div className="stack-list">
            {watchlists.map((item) => (
              <button key={item.id} className="list-card">
                <span>{item.name}</span>
                <small>{item.entities.length} tracked entities</small>
              </button>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span>Saved Views</span>
            <button onClick={() => void saveView()}>Save</button>
          </div>
          <div className="stack-list">
            {savedViews.map((view) => (
              <button key={view.id} className="list-card" onClick={() => flyToSavedView(view)}>
                <span>{view.name}</span>
                <small>{view.description || `${view.center_lat.toFixed(2)}, ${view.center_lon.toFixed(2)}`}</small>
              </button>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <span>Cases</span>
            <button onClick={() => void createCase()}>New</button>
          </div>
          <div className="stack-list">
            {cases.map((item) => (
              <button key={item.id} className="list-card">
                <span>{item.title}</span>
                <small>{item.status.toUpperCase()} · {item.priority.toUpperCase()}</small>
              </button>
            ))}
          </div>
        </div>
      </aside>

      <main className="center-stage">
        <header className="topbar panel">
          <div className="command-bar">
            <input
              value={searchQuery}
              placeholder="Search callsign, ICAO24, MMSI, NORAD ID, place name, or coordinates"
              onChange={(event) => setSearchQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void runSearch();
                }
              }}
            />
            <button onClick={() => void runSearch()}>Search</button>
          </div>
          <div className="search-results">
            {searchResults.slice(0, 5).map((result) => (
              <button
                key={`${result.kind}:${result.id}`}
                className="search-result"
                onClick={() => {
                  if (result.location && viewerRef.current) {
                    flyCameraToLocation(viewerRef.current, result.location.lat, result.location.lon, 1_500_000, 0, -68, 1.15);
                    setActivePreset("search");
                  }
                }}
              >
                <strong>{result.label}</strong>
                <small>{result.subtitle || result.kind}</small>
              </button>
            ))}
          </div>
        </header>

        <section className="globe-shell panel">
          <div ref={viewerHostRef} className="globe-host" />
          <div className="tracker-hud">
            <div className="tracker-badge">LIVE TRAFFIC PICTURE</div>
            <div className="tracker-metrics">
              <div className="tracker-metric">
                <strong>{renderedAircraft.length.toLocaleString()}</strong>
                <span>Aircraft rendered</span>
              </div>
              <div className="tracker-metric">
                <strong>{renderedVessels.length.toLocaleString()}</strong>
                <span>Vessels rendered</span>
              </div>
              <div className="tracker-metric">
                <strong>{renderedSatellites.length.toLocaleString()}</strong>
                <span>Satellites rendered</span>
              </div>
              <div className="tracker-metric">
                <strong>{formatCameraAltitude(cameraHeight)}</strong>
                <span>Camera altitude</span>
              </div>
            </div>
            <div className="tracker-focus">
              <span className="muted">Focus</span>
              <strong>{selected ? entityLabel(selected) : "Global traffic"}</strong>
            </div>
            <div className="tracker-status-line">
              <span>{zoomBand} view</span>
              <span>{viewWindowLabel(viewBounds)}</span>
              <span>{renderedTrackCount.toLocaleString()} tracks drawn</span>
            </div>
            <div className="tracker-preset-strip">
              {cameraPresets.map((preset) => (
                <button
                  key={preset.key}
                  className={`tracker-preset ${activePreset === preset.key ? "active" : ""}`}
                  onClick={() => flyToPreset(preset)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="tracker-tip">Double-click a track to dive in. Traffic fits the current in-view picture.</div>
          </div>
          <div className="camera-rail">
            <button className="camera-action primary" onClick={() => focusTraffic()}>
              Traffic
            </button>
            <button className="camera-action" onClick={() => focusSelection()} disabled={!selected}>
              Selected
            </button>
            <button className="camera-action" onClick={() => flyToPreset(cameraPresets[0])}>
              Home
            </button>
            <div className="camera-zoom">
              <button className="camera-action zoom" onClick={() => zoomCamera("in")}>
                +
              </button>
              <button className="camera-action zoom" onClick={() => zoomCamera("out")}>
                -
              </button>
            </div>
          </div>
          <div className="layer-strip">
            {layerDefinitions.map((layer) => (
              <label
                key={layer.key}
                className={`layer-chip ${layer.disabled ? "disabled" : ""}`}
                style={{ "--layer-color": layer.color } as CSSProperties}
              >
                <input
                  type="checkbox"
                  checked={layers[layer.key]}
                  disabled={layer.disabled}
                  onChange={() => setLayers((current) => ({ ...current, [layer.key]: !current[layer.key] }))}
                />
                <span>{layer.label}</span>
              </label>
            ))}
          </div>
        </section>

        <footer className="timeline panel">
          <div className="timeline-controls">
            <button className={timelineMode === "live" ? "active" : ""} onClick={() => setTimelineMode("live")}>
              Live
            </button>
            <button className={timelineMode === "paused" ? "active" : ""} onClick={() => setTimelineMode("paused")}>
              Pause
            </button>
            <button className={timelineMode === "replay" ? "active" : ""} onClick={() => setTimelineMode("replay")}>
              Replay
            </button>
            <select value={replaySpeed} onChange={(event) => setReplaySpeed(Number(event.target.value))}>
              <option value={1}>1x</option>
              <option value={5}>5x</option>
              <option value={15}>15x</option>
              <option value={60}>60x</option>
            </select>
          </div>
          <div className="timeline-scrubber">
            <span>Window</span>
            <input
              type="range"
              min={15}
              max={720}
              step={15}
              value={timelineMinutes}
              onChange={(event) => setTimelineMinutes(Number(event.target.value))}
            />
            <strong>{timelineMinutes} min</strong>
          </div>
        </footer>
      </main>

      <aside className="sidebar right">
        <div className="panel detail-header">
          <div className="eyebrow">Selected Entity</div>
          <h2>{entityLabel(selected)}</h2>
          {selected ? <p>{selected.kind.toUpperCase()} · {selected.source}</p> : <p>Pick a track, vessel, or overlay on the globe.</p>}
          <div className="detail-actions">
            <button onClick={() => focusSelection()} disabled={!selected}>
              Focus Track
            </button>
            <button onClick={() => flyToPreset(cameraPresets[0])}>
              Global Reset
            </button>
          </div>
        </div>

        <div className="panel tab-strip">
          {detailTabs.map((tab) => (
            <button key={tab} className={detailTab === tab ? "active" : ""} onClick={() => setDetailTab(tab)}>
              {tab}
            </button>
          ))}
        </div>

        <div className="panel detail-panel">
          {detailTab === "details" && (
            <div className="detail-grid">
              {selected ? (
                <>
                  <div><span>Identifier</span><strong>{selected.id}</strong></div>
                  <div><span>Source</span><strong>{selected.source}</strong></div>
                  {"observed_at" in selected ? <div><span>Observed</span><strong>{selected.observed_at}</strong></div> : null}
                  {"computed_lat" in selected ? <div><span>Coordinates</span><strong>{selected.computed_lat.toFixed(3)}, {selected.computed_lon.toFixed(3)}</strong></div> : null}
                  {"lat" in selected ? <div><span>Coordinates</span><strong>{selected.lat.toFixed(3)}, {selected.lon.toFixed(3)}</strong></div> : null}
                  {"altitude_m" in selected ? <div><span>Altitude</span><strong>{formatAltitudeFeet(selected.altitude_m) ?? "n/a"}</strong></div> : null}
                  {"computed_alt_km" in selected ? <div><span>Altitude</span><strong>{formatAltitudeKm(selected.computed_alt_km != null ? selected.computed_alt_km * 1000 : null) ?? "n/a"}</strong></div> : null}
                  {"velocity_kts" in selected ? <div><span>Speed</span><strong>{formatKnots(selected.velocity_kts) ?? "n/a"}</strong></div> : null}
                  {"computed_velocity_kms" in selected ? <div><span>Speed</span><strong>{formatVelocityKms(selected.computed_velocity_kms) ?? "n/a"}</strong></div> : null}
                  {"speed_kts" in selected ? <div><span>Speed</span><strong>{formatKnots(selected.speed_kts) ?? "n/a"}</strong></div> : null}
                  {"heading_deg" in selected ? <div><span>Heading</span><strong>{selected.heading_deg ?? "n/a"}°</strong></div> : null}
                  {"registration" in selected ? <div><span>Registration</span><strong>{selected.registration ?? "n/a"}</strong></div> : null}
                  {"operator" in selected ? <div><span>Operator</span><strong>{selected.operator ?? "n/a"}</strong></div> : null}
                  {"icao24" in selected ? <div><span>Category</span><strong>{selected.aircraft_category ?? resolveAircraftCategory(selected)}</strong></div> : null}
                  {"vessel_type" in selected ? <div><span>Type</span><strong>{selected.vessel_type ?? "n/a"}</strong></div> : null}
                  {"callsign" in selected ? <div><span>Callsign</span><strong>{selected.callsign ?? "n/a"}</strong></div> : null}
                  {"nav_status" in selected ? <div><span>Nav Status</span><strong>{selected.nav_status ?? "n/a"}</strong></div> : null}
                  {"destination" in selected ? <div><span>Destination</span><strong>{selected.destination ?? "n/a"}</strong></div> : null}
                  {"draught_m" in selected ? <div><span>Draught</span><strong>{selected.draught_m != null ? `${selected.draught_m.toFixed(1)} m` : "n/a"}</strong></div> : null}
                  {"stale" in selected ? <div><span>Track Freshness</span><strong>{selected.stale ? "STALE" : "FRESH"}</strong></div> : null}
                  {"norad_cat_id" in selected ? <div><span>NORAD</span><strong>{selected.norad_cat_id}</strong></div> : null}
                  {"international_designator" in selected ? <div><span>Intl Designator</span><strong>{selected.international_designator ?? "n/a"}</strong></div> : null}
                  {"group_name" in selected ? <div><span>Group</span><strong>{selected.group_name ?? "n/a"}</strong></div> : null}
                  {"orbit_class" in selected ? <div><span>Orbit</span><strong>{selected.orbit_class ?? "n/a"}</strong></div> : null}
                  {"epoch" in selected ? <div><span>Epoch</span><strong>{selected.epoch ?? "n/a"}</strong></div> : null}
                  {"object_type" in selected ? <div><span>Object Type</span><strong>{selected.object_type ?? "n/a"}</strong></div> : null}
                </>
              ) : (
                <p className="muted">Analyst context appears here when an entity is selected.</p>
              )}
            </div>
          )}

          {detailTab === "relationships" && (
            <div className="stack-list">
              {relatedCases.map((item) => (
                <div key={item.id} className="list-card static">
                  <span>{item.title}</span>
                  <small>Case</small>
                </div>
              ))}
              {relatedWatchlists.map((item) => (
                <div key={item.id} className="list-card static">
                  <span>{item.name}</span>
                  <small>Watchlist</small>
                </div>
              ))}
              {!relatedCases.length && !relatedWatchlists.length && <p className="muted">No linked cases or watchlists.</p>}
            </div>
          )}

              {detailTab === "timeline" && (
                <div className="stack-list">
                  {[...aircraftTracks, ...vesselTracks, ...satelliteTracks]
                    .filter((track) => !selected || track.entity_id === selected.id)
                    .slice(0, 8)
                    .map((track) => (
                      <div key={track.entity_id} className="list-card static">
                        <span>{track.label}</span>
                        <small>{track.points.length} observations</small>
                      </div>
                    ))}
                  {!aircraftTracks.length && !vesselTracks.length && !satelliteTracks.length && (
                    <p className="muted">Switch to replay mode or select a live track to inspect movement history.</p>
                  )}
                </div>
              )}

          {detailTab === "notes" && (
            <div className="notes-pane">
              <button onClick={() => void createNote()}>Add Note</button>
              <div className="stack-list">
                {selectedNotes.map((note) => (
                  <div key={note.id} className="list-card static">
                    <span>{note.body}</span>
                    <small>{note.created_at}</small>
                  </div>
                ))}
                {!selectedNotes.length && <p className="muted">No notes attached to the selected entity.</p>}
              </div>
            </div>
          )}

          {detailTab === "sources" && (
            <div className="stack-list">
              {selected ? (
                <>
                  <div className="list-card static">
                    <span>{selected.source}</span>
                    <small>Confidence {"source_confidence" in selected ? selected.source_confidence : 1}</small>
                  </div>
                  {"source_record_id" in selected ? (
                    <div className="list-card static">
                      <span>Provider Record</span>
                      <small>{selected.source_record_id ?? "n/a"}</small>
                    </div>
                  ) : null}
                  {"merged_confidence" in selected ? (
                    <div className="list-card static">
                      <span>Merged Confidence</span>
                      <small>{selected.merged_confidence ?? "n/a"}</small>
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="muted">Source provenance is shown for tracked entities and overlays.</p>
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
