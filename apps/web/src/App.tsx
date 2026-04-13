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
  NoteRecord,
  SavedViewRecord,
  SearchResult,
  TimelineTrack,
  Vessel,
  WatchlistRecord
} from "@eagle-eye/shared-types";
import { detailTabs, layerDefinitions } from "@eagle-eye/ui";
import { api, connectLiveFeed } from "./lib/api";

type SelectedEntity =
  | ({ kind: "aircraft" } & Aircraft)
  | ({ kind: "vessel" } & Vessel)
  | ({ kind: "airspace" } & AirspaceOverlay)
  | null;

type GlobeEntityPayload =
  | { kind: "aircraft"; data: Aircraft }
  | { kind: "vessel"; data: Vessel }
  | { kind: "airspace"; data: AirspaceOverlay };

type LayerState = Record<string, boolean>;

const defaultLayers: LayerState = {
  aircraft: true,
  vessels: true,
  airspace: true,
  webcams: false
};

const AIRCRAFT_COLOR = "#ffd54a";
const AIRCRAFT_SELECTED_COLOR = "#fff4b3";
const VESSEL_COLOR = "#6ee7ff";
const VESSEL_SELECTED_COLOR = "#b6f4ff";

const AIRCRAFT_ICON = `data:image/svg+xml;utf8,${encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
    <path fill="#0c1016" fill-opacity="0.45" d="M32 8l8 17 16 8v5l-16 5-8 15-8-15-16-5v-5l16-8z"/>
    <path
      fill="#ffd54a"
      stroke="#061019"
      stroke-width="2"
      stroke-linejoin="round"
      d="M32 2l5 16 17 6v7l-16 4-7 27-5-1 4-26-9-2 1 10-4 1-4-14-13-4v-7l17-6 5-16z"
    />
  </svg>
`)}`;

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

function entityLabel(entity: SelectedEntity): string {
  if (!entity) return "No selection";
  if (entity.kind === "aircraft") return entity.callsign?.trim() || entity.icao24;
  if (entity.kind === "vessel") return entity.vessel_name?.trim() || entity.mmsi;
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

  const secondary = [formatAltitudeFeet(item.altitude_m), formatKnots(item.velocity_kts)].filter(Boolean).join(" • ");
  return secondary ? `${primary.toUpperCase()}\n${secondary}` : primary.toUpperCase();
}

function vesselLabel(item: Vessel, isSelected: boolean): string {
  const primary = item.vessel_name?.trim() || item.mmsi;
  if (!isSelected) {
    return primary;
  }

  const secondary = [item.vessel_type?.trim(), formatKnots(item.speed_kts)].filter(Boolean).join(" • ");
  return secondary ? `${primary}\n${secondary}` : primary;
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

export default function App() {
  const viewerRef = useRef<Viewer | null>(null);
  const viewerHostRef = useRef<HTMLDivElement | null>(null);
  const airspaceSourceRef = useRef<GeoJsonDataSource | null>(null);
  const [layers, setLayers] = useState<LayerState>(defaultLayers);
  const [selected, setSelected] = useState<SelectedEntity>(null);
  const [detailTab, setDetailTab] = useState<(typeof detailTabs)[number]>("details");
  const [aircraft, setAircraft] = useState<Aircraft[]>([]);
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [airspace, setAirspace] = useState<AirspaceOverlay[]>([]);
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
  const [status, setStatus] = useState("Loading operational picture...");

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
  const selectedKey = selected ? `${selected.kind}:${selected.id}` : null;

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
    if (viewer.scene.skyAtmosphere) {
      viewer.scene.skyAtmosphere.show = false;
    }
    if (viewer.scene.skyBox) {
      viewer.scene.skyBox.show = false;
    }
    if (viewer.scene.sun) {
      viewer.scene.sun.show = false;
    }
    if (viewer.scene.moon) {
      viewer.scene.moon.show = false;
    }
    viewer.scene.fog.enabled = false;
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = false;
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(-20, 28, 22_000_000),
      duration: 0
    });

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
      } else if (payload.kind === "airspace") {
        setSelected({ kind: "airspace", ...payload.data });
      }
    }, ScreenSpaceEventType.LEFT_CLICK);

    viewerRef.current = viewer;
    return () => {
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  async function loadOperationalData() {
    try {
      setStatus("Synchronizing live data...");
      const [nextAircraft, nextVessels, nextAirspace, nextCases, nextWatchlists, nextNotes, nextViews] = await Promise.all([
        api.getAircraftCurrent(),
        api.getVesselsCurrent(),
        api.getAirspaceCurrent(),
        api.getCases(),
        api.getWatchlists(),
        api.getNotes(),
        api.getSavedViews()
      ]);

      startTransition(() => {
        setAircraft(nextAircraft);
        setVessels(nextVessels);
        setAirspace(nextAirspace);
        setCases(nextCases);
        setWatchlists(nextWatchlists);
        setNotes(nextNotes);
        setSavedViews(nextViews);
        setStatus(`Live traffic: ${nextAircraft.length} airborne, ${nextVessels.length} maritime, ${nextAirspace.length} overlays.`);
      });
    } catch {
      setStatus("API unavailable. Check Eagle Eye services and VITE_API_BASE_URL.");
    }
  }

  useEffect(() => {
    void loadOperationalData();
    const intervalId = window.setInterval(() => {
      if (timelineMode === "live") {
        void loadOperationalData();
      }
    }, 15_000);

    return () => window.clearInterval(intervalId);
  }, [timelineMode]);

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

        if (message.topic === "airspace") {
          void loadOperationalData();
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
      aircraft.forEach((item) => {
        const isSelected = selectedKey === `aircraft:${item.id}`;
        const vectorDistanceNm = Math.max(12, Math.min(42, (item.velocity_kts ?? 280) / 12));
        const vectorEnd = projectTrackVector(item.lat, item.lon, item.heading_deg, vectorDistanceNm);
        viewer.entities.add({
          id: item.id,
          position: Cartesian3.fromDegrees(item.lon, item.lat, item.altitude_m ?? 0),
          point: {
            pixelSize: isSelected ? 18 : 12,
            color: Color.fromCssColorString(isSelected ? AIRCRAFT_SELECTED_COLOR : AIRCRAFT_COLOR).withAlpha(isSelected ? 0.38 : 0.18),
            outlineColor: Color.fromCssColorString("#0a0f14").withAlpha(0.3),
            outlineWidth: isSelected ? 2 : 1,
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          billboard: {
            image: AIRCRAFT_ICON,
            verticalOrigin: VerticalOrigin.CENTER,
            rotation: CesiumMath.toRadians(item.heading_deg ?? 0),
            alignedAxis: Cartesian3.UNIT_Z,
            scale: isSelected ? 1.24 : 0.96,
            scaleByDistance: new NearFarScalar(200_000, 1.35, 24_000_000, 0.7),
            color: Color.fromCssColorString(isSelected ? AIRCRAFT_SELECTED_COLOR : AIRCRAFT_COLOR),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label: {
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
              },
          polyline: vectorEnd
            ? {
                positions: [
                  Cartesian3.fromDegrees(item.lon, item.lat, item.altitude_m ?? 0),
                  Cartesian3.fromDegrees(vectorEnd.lon, vectorEnd.lat, item.altitude_m ?? 0)
                ],
                width: isSelected ? 3 : 1.6,
                material: Color.fromCssColorString(isSelected ? AIRCRAFT_SELECTED_COLOR : AIRCRAFT_COLOR).withAlpha(isSelected ? 0.9 : 0.48),
                arcType: ArcType.NONE,
                distanceDisplayCondition: new DistanceDisplayCondition(0, 9_000_000)
              }
            : undefined,
          properties: createPropertyBag({ kind: "aircraft", data: item })
        });
      });
    }

    if (layers.vessels) {
      vessels.forEach((item) => {
        const isSelected = selectedKey === `vessel:${item.id}`;
        const vectorDistanceNm = Math.max(2, Math.min(12, (item.speed_kts ?? 16) / 2.2));
        const vectorEnd = projectTrackVector(item.lat, item.lon, item.heading_deg, vectorDistanceNm);
        viewer.entities.add({
          id: item.id,
          position: Cartesian3.fromDegrees(item.lon, item.lat, 0),
          point: {
            pixelSize: isSelected ? 14 : 10,
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
            scale: isSelected ? 1.06 : 0.84,
            scaleByDistance: new NearFarScalar(200_000, 1.2, 24_000_000, 0.6),
            color: Color.fromCssColorString(isSelected ? VESSEL_SELECTED_COLOR : VESSEL_COLOR),
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label: item.vessel_name?.trim() || isSelected
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
          polyline: vectorEnd
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

    [...aircraftTracks, ...vesselTracks].forEach((track) => {
      if (track.points.length < 2) return;
      const isSelected = Boolean(selected && track.entity_kind === selected.kind && track.entity_id === selected.id);
      viewer.entities.add({
        id: `${track.entity_kind}:${track.entity_id}:track`,
        polyline: {
          positions: track.points.map((point) => Cartesian3.fromDegrees(point.lon, point.lat, point.altitude_m ?? 0)),
          width: isSelected ? 4 : 2.2,
          material: Color.fromCssColorString(track.entity_kind === "aircraft" ? AIRCRAFT_COLOR : VESSEL_COLOR).withAlpha(
            isSelected ? 0.95 : 0.55
          )
        }
      });
    });
  }, [aircraft, vessels, aircraftTracks, vesselTracks, layers.aircraft, layers.vessels, selected, selectedKey]);

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
    if (timelineMode === "live") {
      setAircraftTracks([]);
      setVesselTracks([]);
      return;
    }

    const params = new URLSearchParams({
      since: isoNowMinus(timelineMinutes),
      until: new Date().toISOString()
    });

    Promise.all([api.getAircraftHistory(params), api.getVesselsHistory(params)])
      .then(([aircraftHistory, vesselHistory]) => {
        setAircraftTracks(aircraftHistory.tracks);
        setVesselTracks(vesselHistory.tracks);
      })
      .catch(() => setStatus("Replay data unavailable. Live view remains active."));
  }, [timelineMinutes, timelineMode, replaySpeed]);

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
              <span>{aircraft.length} aircraft</span>
            </div>
            <div className="source-row">
              <strong>AISStream</strong>
              <span>{vessels.length} vessels</span>
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
              placeholder="Search callsign, ICAO24, MMSI, place name, or coordinates"
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
                    viewerRef.current.camera.flyTo({
                      destination: Cartesian3.fromDegrees(result.location.lon, result.location.lat, 1_500_000)
                    });
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
                <strong>{aircraft.length.toLocaleString()}</strong>
                <span>Aircraft</span>
              </div>
              <div className="tracker-metric">
                <strong>{vessels.length.toLocaleString()}</strong>
                <span>Vessels</span>
              </div>
              <div className="tracker-metric">
                <strong>{airspace.length.toLocaleString()}</strong>
                <span>Airspace</span>
              </div>
            </div>
            <div className="tracker-focus">
              <span className="muted">Focus</span>
              <strong>{selected ? entityLabel(selected) : "Global traffic"}</strong>
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
                  {"lat" in selected ? <div><span>Coordinates</span><strong>{selected.lat.toFixed(3)}, {selected.lon.toFixed(3)}</strong></div> : null}
                  {"altitude_m" in selected ? <div><span>Altitude</span><strong>{formatAltitudeFeet(selected.altitude_m) ?? "n/a"}</strong></div> : null}
                  {"velocity_kts" in selected ? <div><span>Speed</span><strong>{formatKnots(selected.velocity_kts) ?? "n/a"}</strong></div> : null}
                  {"speed_kts" in selected ? <div><span>Speed</span><strong>{formatKnots(selected.speed_kts) ?? "n/a"}</strong></div> : null}
                  {"heading_deg" in selected ? <div><span>Heading</span><strong>{selected.heading_deg ?? "n/a"}°</strong></div> : null}
                  {"registration" in selected ? <div><span>Registration</span><strong>{selected.registration ?? "n/a"}</strong></div> : null}
                  {"operator" in selected ? <div><span>Operator</span><strong>{selected.operator ?? "n/a"}</strong></div> : null}
                  {"vessel_type" in selected ? <div><span>Type</span><strong>{selected.vessel_type ?? "n/a"}</strong></div> : null}
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
              {[...aircraftTracks, ...vesselTracks]
                .filter((track) => !selected || track.entity_id === selected.id)
                .slice(0, 8)
                .map((track) => (
                  <div key={track.entity_id} className="list-card static">
                    <span>{track.label}</span>
                    <small>{track.points.length} observations</small>
                  </div>
                ))}
              {!aircraftTracks.length && !vesselTracks.length && <p className="muted">Switch to replay mode to inspect movement history.</p>}
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
                <div className="list-card static">
                  <span>{selected.source}</span>
                  <small>Confidence {"source_confidence" in selected ? selected.source_confidence : 1}</small>
                </div>
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
