import {
  Cartesian2,
  Cartesian3,
  Color,
  EllipsoidTerrainProvider,
  ImageryLayer,
  Ion,
  JulianDate,
  LabelStyle,
  Math as CesiumMath,
  OpenStreetMapImageryProvider,
  PolylineDashMaterialProperty,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  VerticalOrigin,
  Viewer,
  type Entity
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import type {
  EntityRecord,
  EventRecord,
  GlobeViewState,
  InvestigationBundle,
  SatelliteFovResponse,
  TimeState,
  ViewQueryResponse
} from "@eagle-eye/shared-types";
import { layerDefinitions } from "@eagle-eye/ui";
import { EagleEyeLayout } from "./components/eagle-eye/EagleEyeLayout";
import { api, connectLiveFeed } from "./lib/api";

type LayerState = Record<string, boolean>;
type Selection = { kind: "entity" | "cluster" | "event"; id: string } | null;
type LayerPresetName = "All Layers" | "Space + Events" | "Surface + Alerts" | "Tracks Only";
type MapPresetName = "Global" | "Atlantic" | "Europe" | "Indo-Pacific";

const initialLayers: LayerState = Object.fromEntries(layerDefinitions.map((layer) => [layer.key, true]));

function normalizeLongitude(value: number): number {
  return ((value + 540) % 360) - 180;
}

function clampLatitude(value: number): number {
  return Math.max(-85, Math.min(85, value));
}

function fallbackViewBounds(viewer: Viewer): Pick<GlobeViewState, "west" | "south" | "east" | "north"> {
  const camera = viewer.camera.positionCartographic;
  const centerLon = normalizeLongitude(CesiumMath.toDegrees(camera.longitude));
  const centerLat = clampLatitude(CesiumMath.toDegrees(camera.latitude));
  const spanLat = Math.min(140, Math.max(18, camera.height / 125_000));
  const spanLon = Math.min(220, Math.max(24, spanLat * 1.6));
  return {
    west: normalizeLongitude(centerLon - spanLon / 2),
    south: clampLatitude(centerLat - spanLat / 2),
    east: normalizeLongitude(centerLon + spanLon / 2),
    north: clampLatitude(centerLat + spanLat / 2)
  };
}

function buildViewState(
  viewer: Viewer,
  timeState: TimeState,
  layers: LayerState,
  selectedEntities: string[],
  modeOverride?: GlobeViewState["mode"]
): GlobeViewState | null {
  const rectangle = viewer.camera.computeViewRectangle(viewer.scene.globe.ellipsoid);
  const bounds = rectangle
    ? {
        west: normalizeLongitude(CesiumMath.toDegrees(rectangle.west)),
        south: clampLatitude(CesiumMath.toDegrees(rectangle.south)),
        east: normalizeLongitude(CesiumMath.toDegrees(rectangle.east)),
        north: clampLatitude(CesiumMath.toDegrees(rectangle.north))
      }
    : fallbackViewBounds(viewer);

  return {
    west: bounds.west,
    south: bounds.south,
    east: bounds.east,
    north: bounds.north,
    camera_height: viewer.camera.positionCartographic.height,
    heading: CesiumMath.toDegrees(viewer.camera.heading),
    pitch: CesiumMath.toDegrees(viewer.camera.pitch),
    roll: CesiumMath.toDegrees(viewer.camera.roll),
    timestamp: timeState.current_timestamp,
    mode: modeOverride ?? (timeState.mode === "simulate" ? "simulate" : timeState.mode === "replay" || timeState.mode === "paused" ? "replay" : "live"),
    enabled_layers: Object.entries(layers)
      .filter(([, enabled]) => enabled)
      .map(([key]) => key),
    selected_entities: selectedEntities,
    selected_aois: []
  };
}

function pointFromGeometry(geometry?: { type: string; coordinates?: unknown } | null): { lon: number; lat: number } | null {
  if (!geometry?.coordinates || geometry.type !== "Point") return null;
  const coords = geometry.coordinates as [number, number];
  return { lon: coords[0], lat: coords[1] };
}

function polygonHierarchy(geometry?: { type: string; coordinates?: unknown } | null): Cartesian3[] | null {
  if (!geometry?.coordinates) return null;
  if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") return null;
  const firstRing =
    geometry.type === "Polygon"
      ? (geometry.coordinates as number[][][])[0]
      : (geometry.coordinates as number[][][][])[0]?.[0];
  if (!firstRing) return null;
  return firstRing.map(([lon, lat]) => Cartesian3.fromDegrees(lon, lat));
}

function geometryCenter(geometry?: { type: string; coordinates?: unknown } | null): { lon: number; lat: number } | null {
  const point = pointFromGeometry(geometry);
  if (point) return point;
  if (!geometry?.coordinates || (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon")) return null;
  const ring =
    geometry.type === "Polygon"
      ? (geometry.coordinates as number[][][])[0]
      : (geometry.coordinates as number[][][][])[0]?.[0];
  if (!ring?.length) return null;
  const sums = ring.reduce(
    (acc, [lon, lat]) => ({ lon: acc.lon + lon, lat: acc.lat + lat }),
    { lon: 0, lat: 0 }
  );
  return { lon: sums.lon / ring.length, lat: sums.lat / ring.length };
}

function eventColor(event: EventRecord): string {
  const category = event.category.toLowerCase();
  const source = event.source.toLowerCase();
  if (source === "firms") return "#ff5d33";
  if (source === "nws") {
    if (event.severity === "high") return "#ff5f61";
    if (event.severity === "medium") return "#ffb347";
    return "#57a8ff";
  }
  if (category.includes("storm")) return "#58c7ff";
  if (category.includes("launch")) return "#ffaa4d";
  return "#ff7d4d";
}

function formatUtc(iso?: string | null): string {
  if (!iso) return "--";
  const date = new Date(iso);
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    hour12: false
  }).format(date);
}

function formatUtcDateTime(iso?: string | null): string {
  if (!iso) return "--";
  const date = new Date(iso);
  const datePart = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "UTC"
  }).format(date);
  const timePart = new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
    hour12: false
  }).format(date);
  return `${datePart} ${timePart} UTC`;
}

function formatRelativePass(iso?: string | null): string {
  if (!iso) return "--";
  const diffMs = new Date(iso).getTime() - Date.now();
  if (!Number.isFinite(diffMs)) return "--";
  const totalSeconds = Math.max(0, Math.round(diffMs / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `In ${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

function selectedLabel(entity: EntityRecord | null, event: EventRecord | null): string {
  if (entity) return entity.label;
  if (event) return event.title;
  return "NO OBJECT SELECTED";
}

function identifierRows(entity: EntityRecord | null, bundle: InvestigationBundle | null): string[] {
  if (!entity) return [];
  const props = entity.properties ?? {};
  const candidates = [
    typeof props.registration === "string" ? props.registration : null,
    typeof props.callsign === "string" ? props.callsign : null,
    typeof props.icao24 === "string" ? props.icao24 : null,
    typeof props.norad_cat_id === "string" ? props.norad_cat_id : null,
    bundle?.watchlists?.[0]?.name ?? null
  ].filter((value): value is string => Boolean(value));
  return Array.from(new Set(candidates)).slice(0, 3);
}

function App() {
  const globeRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const refreshTimerRef = useRef<number | null>(null);
  const refreshInFlightRef = useRef(false);

  const [timeState, setTimeState] = useState<TimeState | null>(null);
  const [layers, setLayers] = useState<LayerState>(initialLayers);
  const [viewData, setViewData] = useState<ViewQueryResponse | null>(null);
  const [recentEvents, setRecentEvents] = useState<EventRecord[]>([]);
  const [selection, setSelection] = useState<Selection>(null);
  const [bundle, setBundle] = useState<InvestigationBundle | null>(null);
  const [satelliteFov, setSatelliteFov] = useState<SatelliteFovResponse | null>(null);
  const [socketOnline, setSocketOnline] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const [followSelected, setFollowSelected] = useState(false);
  const [trajectoryEnabled, setTrajectoryEnabled] = useState(false);
  const [showMoreInfo, setShowMoreInfo] = useState(false);
  const [activeTrack, setActiveTrack] = useState<"aircraft" | "maritime" | "satellites" | "alerts" | null>(null);
  const [effectiveViewMode, setEffectiveViewMode] = useState<"live" | "replay">("live");
  const [layerLabel, setLayerLabel] = useState<LayerPresetName>("All Layers");
  const [mapLabel, setMapLabel] = useState<MapPresetName>("Global");
  const [statusText, setStatusText] = useState("Connecting to backend");
  const [cameraHeight, setCameraHeight] = useState(19_000_000);
  const [isViewLoading, setIsViewLoading] = useState(true);

  const selectedEntity = useMemo(
    () => (selection?.kind === "entity" ? viewData?.entities.find((entity) => entity.id === selection.id) ?? null : null),
    [selection, viewData]
  );
  const selectedEvent = useMemo(
    () => (selection?.kind === "event" ? recentEvents.find((event) => event.id === selection.id) ?? viewData?.events.find((event) => event.id === selection.id) ?? null : null),
    [recentEvents, selection, viewData]
  );

  const filteredEntities = useMemo(() => {
    const query = searchValue.trim().toLowerCase();
    if (!query) return viewData?.entities ?? [];
    return (viewData?.entities ?? []).filter((entity) => {
      const haystack = `${entity.label} ${JSON.stringify(entity.properties)}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [searchValue, viewData]);

  const trackCounts = useMemo(() => {
    const rows = viewData?.entities ?? [];
    return {
      aircraft: rows.filter((entity) => entity.entity_kind === "aircraft").length,
      maritime: rows.filter((entity) => entity.entity_kind === "vessel").length,
      satellites: rows.filter((entity) => entity.entity_kind === "satellite").length,
      alerts: recentEvents.length
    };
  }, [recentEvents.length, viewData?.entities]);

  const selectedIdentifiers = useMemo(() => identifierRows(selectedEntity, bundle), [bundle, selectedEntity]);

  const timelineEvents = useMemo(() => (recentEvents.length ? recentEvents.slice(0, 3) : (viewData?.events ?? []).slice(0, 3)), [recentEvents, viewData?.events]);
  const runtimeStatus = useMemo(() => {
    if (!timeState) {
      return { label: "SYNC", tone: "connecting" as const };
    }
    if (timeState.mode === "paused") {
      return { label: "PAUSED", tone: "paused" as const };
    }
    if (timeState.mode === "replay" || effectiveViewMode === "replay") {
      return { label: "REPLAY", tone: "replay" as const };
    }
    if (socketOnline) {
      return { label: "LIVE", tone: "live" as const };
    }
    return { label: "OFFLINE", tone: "offline" as const };
  }, [effectiveViewMode, socketOnline, timeState]);

  useEffect(() => {
    api
      .getTimeState()
      .then(setTimeState)
      .catch((error: unknown) => setStatusText(String(error)));

    api
      .getEvents()
      .then((rows) => {
        setRecentEvents(rows);
        setStatusText(`Loaded ${rows.length} live events`);
      })
      .catch((error: unknown) => setStatusText(String(error)));
  }, []);

  function scheduleRefresh(delay = 250) {
    if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = window.setTimeout(() => {
      if (!viewerRef.current || !timeState || refreshInFlightRef.current) return;
      const requestedMode = timeState.mode === "live" ? "live" : "replay";
      const payload = buildViewState(viewerRef.current, timeState, layers, selectedEntity ? [selectedEntity.id] : [], requestedMode);
      if (!payload) return;
      refreshInFlightRef.current = true;
      setIsViewLoading(true);
      api
        .queryView(payload)
        .then(async (response) => {
          const isEmpty = response.entities.length === 0 && response.events.length === 0 && response.clusters.length === 0;
          if (isEmpty && requestedMode === "live" && timeState.current_timestamp) {
            const replayPayload = { ...payload, mode: "replay" as const, timestamp: timeState.current_timestamp };
            try {
              const replayResponse = await api.queryView(replayPayload);
              const replayHasData = replayResponse.entities.length > 0 || replayResponse.events.length > 0 || replayResponse.clusters.length > 0;
              if (replayHasData) {
                startTransition(() => {
                  setEffectiveViewMode("replay");
                  setViewData(replayResponse);
                  setStatusText(
                    `No fresh live rows; showing replay snapshot with ${replayResponse.entities.length} tracks and ${replayResponse.events.length} events`
                  );
                });
                return;
              }
            } catch {
              // Keep the live response if replay fallback also fails.
            }
          }
          startTransition(() => {
            setEffectiveViewMode(requestedMode);
            setViewData(response);
            setStatusText(
              isEmpty
                ? `No ${requestedMode} data returned for the current viewport`
                : `${response.entities.length} tracks, ${response.events.length} in-view events, ${response.clusters.length} clusters`
            );
          });
        })
        .catch((error: unknown) => setStatusText(String(error)))
        .finally(() => {
          refreshInFlightRef.current = false;
          setIsViewLoading(false);
        });
    }, Math.max(120, delay));
  }

  useEffect(() => {
    if (!globeRef.current || viewerRef.current) return;
    const ionToken = import.meta.env.VITE_CESIUM_ION_TOKEN ?? import.meta.env.CESIUM_ION_TOKEN ?? "";
    Ion.defaultAccessToken = ionToken;
    const viewer = new Viewer(globeRef.current, {
      animation: false,
      baseLayerPicker: false,
      fullscreenButton: false,
      geocoder: false,
      timeline: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      homeButton: false,
      infoBox: false,
      selectionIndicator: false,
      scene3DOnly: true,
      terrainProvider: new EllipsoidTerrainProvider(),
      baseLayer: new ImageryLayer(
        new OpenStreetMapImageryProvider({
          url: "https://tile.openstreetmap.org/"
        })
      ),
      requestRenderMode: true,
      maximumRenderTimeChange: Infinity
    });

    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewer.scene.globe.baseColor = Color.fromCssColorString("#040911");
    if (viewer.scene.skyAtmosphere) {
      viewer.scene.skyAtmosphere.hueShift = 0.1;
      viewer.scene.skyAtmosphere.saturationShift = -0.2;
      viewer.scene.skyAtmosphere.brightnessShift = -0.4;
    }
    const handler = new ScreenSpaceEventHandler(viewer.canvas);
    handler.setInputAction((movement: { position: Cartesian2 }) => {
      const picked = viewer.scene.pick(movement.position) as Entity | undefined;
      const payload = (picked?.properties?.payload?.getValue?.(JulianDate.now()) ?? null) as Selection;
      if (payload) setSelection(payload);
    }, ScreenSpaceEventType.LEFT_CLICK);

    const onMoveEnd = () => {
      setCameraHeight(viewer.camera.positionCartographic.height);
      scheduleRefresh(180);
    };

    viewer.camera.moveEnd.addEventListener(onMoveEnd);
    viewerRef.current = viewer;
    window.setTimeout(() => {
      applyMapPreset("Global", 0);
      scheduleRefresh(400);
    }, 0);

    return () => {
      viewer.camera.moveEnd.removeEventListener(onMoveEnd);
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
    };
  }, [layers, timeState]);

  useEffect(() => {
    if (!timeState) return;
    scheduleRefresh(60);
  }, [layers, timeState]);

  useEffect(() => {
    if (!selectedEntity) return;
    scheduleRefresh(80);
  }, [selectedEntity?.id]);

  useEffect(() => {
    if (!timeState) return;
    const socket = connectLiveFeed((message) => {
      if (message.topic === "view.invalidate" || message.topic === "events") {
        scheduleRefresh(180);
        api.getEvents().then(setRecentEvents).catch(() => undefined);
      }
      if (message.topic === "heartbeat") setSocketOnline(true);
    });
    socket.onopen = () => setSocketOnline(true);
    socket.onclose = () => setSocketOnline(false);
    return () => socket.close();
  }, [timeState]);

  useEffect(() => {
    if (!timeState || timeState.status !== "playing") return;
    const interval = window.setInterval(() => {
      api.getTimeState().then(setTimeState).catch(() => undefined);
      scheduleRefresh(100);
    }, 3000);
    return () => window.clearInterval(interval);
  }, [timeState]);

  useEffect(() => {
    if (selection || !viewData) return;
    const satellite = viewData.entities.find((entity) => entity.entity_kind === "satellite");
    const entityFallback = satellite ?? viewData.entities[0];
    if (entityFallback) {
      setSelection({ kind: "entity", id: entityFallback.id });
      return;
    }
    if (viewData.events[0]) {
      setSelection({ kind: "event", id: viewData.events[0].id });
    }
  }, [selection, viewData]);

  useEffect(() => {
    if (!searchValue.trim()) return;
    const match = filteredEntities[0];
    if (!match) return;
    setSelection({ kind: "entity", id: match.id });
  }, [filteredEntities, searchValue]);

  useEffect(() => {
    if (selection?.kind !== "cluster" || !viewData || !viewerRef.current) return;
    const cluster = viewData.clusters.find((item) => item.id === selection.id);
    if (!cluster) return;
    viewerRef.current.camera.flyTo({
      destination: Cartesian3.fromDegrees(cluster.lon, cluster.lat, 1_600_000),
      duration: 0.9
    });
    window.setTimeout(() => setSelection(null), 950);
  }, [selection, viewData]);

  useEffect(() => {
    if (!selectedEntity) {
      setBundle(null);
      setSatelliteFov(null);
      return;
    }
    api.investigateEntity(selectedEntity.id).then(setBundle).catch(() => setBundle(null));
    if (selectedEntity.entity_kind === "satellite") {
      api.getSatelliteFov(selectedEntity.id).then(setSatelliteFov).catch(() => setSatelliteFov(null));
    } else {
      setSatelliteFov(null);
    }
  }, [selectedEntity]);

  useEffect(() => {
    if (!viewerRef.current || !viewData) return;
    const viewer = viewerRef.current;
    viewer.entities.removeAll();
    const showDenseLabels = cameraHeight < 6_500_000;
    const showContextLabels = cameraHeight < 10_000_000;

    for (const cluster of viewData.clusters.slice(0, cameraHeight >= 12_000_000 ? 120 : 180)) {
      viewer.entities.add({
        id: cluster.id,
        position: Cartesian3.fromDegrees(cluster.lon, cluster.lat),
        point: {
          pixelSize: 14 + Math.min(cluster.count, 26),
          color:
            cluster.entity_kind === "aircraft"
              ? Color.fromCssColorString("#58c7ff")
              : cluster.entity_kind === "vessel"
                ? Color.fromCssColorString("#6eff97")
                : Color.fromCssColorString("#ffaa4d"),
          outlineColor: Color.WHITE.withAlpha(0.9),
          outlineWidth: 2,
          disableDepthTestDistance: Number.POSITIVE_INFINITY
        },
        label:
          showContextLabels
            ? {
                text: `${cluster.count}`,
                font: "600 12px IBM Plex Sans",
                fillColor: Color.WHITE,
                style: LabelStyle.FILL_AND_OUTLINE,
                verticalOrigin: VerticalOrigin.BOTTOM,
                pixelOffset: new Cartesian2(0, -14),
                disableDepthTestDistance: Number.POSITIVE_INFINITY
              }
            : undefined,
        properties: { payload: { kind: "cluster", id: cluster.id } }
      });
    }

    for (const event of viewData.events.slice(0, cameraHeight >= 12_000_000 ? 40 : 80)) {
      const point = geometryCenter(event.geometry ?? undefined);
      const polygon = polygonHierarchy(event.geometry ?? undefined);
      const color = eventColor(event);
      if (point) {
        viewer.entities.add({
          id: event.id,
          position: Cartesian3.fromDegrees(point.lon, point.lat),
          point: {
            pixelSize: selection?.id === event.id ? 13 : 10,
            color: Color.fromCssColorString(color),
            outlineColor: Color.WHITE,
            outlineWidth: 2,
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label:
            selection?.id === event.id || showDenseLabels
              ? {
                  text: event.title,
                  font: "600 11px IBM Plex Sans",
                  fillColor: Color.WHITE,
                  style: LabelStyle.FILL_AND_OUTLINE,
                  verticalOrigin: VerticalOrigin.TOP,
                  pixelOffset: new Cartesian2(0, 10),
                  disableDepthTestDistance: Number.POSITIVE_INFINITY
                }
              : undefined,
          properties: { payload: { kind: "event", id: event.id } }
        });
      }
      if (polygon) {
        viewer.entities.add({
          id: `${event.id}:polygon`,
          polygon: {
            hierarchy: polygon,
            material: Color.fromCssColorString(color).withAlpha(0.12),
            outline: true,
            outlineColor: Color.fromCssColorString(color)
          },
          properties: { payload: { kind: "event", id: event.id } }
        });
      }
    }

    for (const entity of filteredEntities.slice(0, cameraHeight >= 12_000_000 ? 550 : cameraHeight >= 7_000_000 ? 900 : 1400)) {
      const point = pointFromGeometry(entity.geometry);
      const polygon = polygonHierarchy(entity.geometry);
      const color =
        entity.entity_kind === "aircraft"
          ? "#58c7ff"
          : entity.entity_kind === "vessel"
            ? "#6eff97"
            : entity.entity_kind === "satellite"
              ? "#ffaa4d"
              : "#eaf4ff";

      if (point) {
        viewer.entities.add({
          id: entity.id,
          position: Cartesian3.fromDegrees(point.lon, point.lat),
          point: {
            pixelSize: selection?.id === entity.id ? 14 : 9,
            color: Color.fromCssColorString(color),
            outlineColor: Color.WHITE.withAlpha(selection?.id === entity.id ? 1 : 0.85),
            outlineWidth: selection?.id === entity.id ? 2.5 : 2,
            disableDepthTestDistance: Number.POSITIVE_INFINITY
          },
          label:
            selection?.id === entity.id || (showDenseLabels && entity === filteredEntities[0])
              ? {
                  text: entity.label,
                  font: "600 12px IBM Plex Sans",
                  fillColor: Color.WHITE,
                  show: true,
                  style: LabelStyle.FILL_AND_OUTLINE,
                  verticalOrigin: VerticalOrigin.TOP,
                  pixelOffset: new Cartesian2(0, 12),
                  disableDepthTestDistance: Number.POSITIVE_INFINITY
                }
              : undefined,
          properties: { payload: { kind: "entity", id: entity.id } }
        });
      }

      if (polygon) {
        viewer.entities.add({
          id: `${entity.id}:polygon`,
          polygon: {
            hierarchy: polygon,
            material: Color.fromCssColorString(color).withAlpha(0.08),
            outline: true,
            outlineColor: Color.fromCssColorString(color)
          },
          properties: { payload: { kind: "entity", id: entity.id } }
        });
      }

      if (trajectoryEnabled && selection?.id === entity.id && entity.predicted_path.length > 1) {
        viewer.entities.add({
          id: `${entity.id}:prediction`,
          polyline: {
            positions: entity.predicted_path.map((item) => Cartesian3.fromDegrees(item.lon, item.lat, item.altitude_m ?? 0)),
            width: 2,
            material: new PolylineDashMaterialProperty({
              color: Color.fromCssColorString(color),
              dashLength: 18
            })
          }
        });
      }
    }

    if (trajectoryEnabled && selectedEntity && bundle?.timeline?.history?.length) {
      viewer.entities.add({
        id: `${selectedEntity.id}:history`,
        polyline: {
          positions: bundle.timeline.history.map((item) => Cartesian3.fromDegrees(item.lon, item.lat, item.altitude_m ?? 0)),
          width: 2.5,
          material: Color.fromCssColorString("#58c7ff").withAlpha(0.7)
        }
      });
    }

    if (satelliteFov?.footprint) {
      const hierarchy = polygonHierarchy(satelliteFov.footprint);
      if (hierarchy) {
        viewer.entities.add({
          id: `${satelliteFov.satellite_id}:fov`,
          polygon: {
            hierarchy,
            material: Color.fromCssColorString("#6eff97").withAlpha(0.08),
            outline: true,
            outlineColor: Color.fromCssColorString("#6eff97")
          }
        });
      }
    }

    viewer.scene.requestRender();
  }, [bundle, cameraHeight, filteredEntities, satelliteFov, selection, selectedEntity, viewData]);

  useEffect(() => {
    if (!followSelected || !selectedEntity || !viewerRef.current) return;
    const point = pointFromGeometry(selectedEntity.geometry);
    if (!point) return;
    viewerRef.current.camera.flyTo({
      destination: Cartesian3.fromDegrees(point.lon, point.lat, 1_800_000),
      duration: 0.35
    });
  }, [followSelected, selectedEntity]);

  function resetGlobalMap() {
    applyMapPreset("Global");
    scheduleRefresh(120);
  }

  function flyToEntity(entity: EntityRecord | null) {
    const viewer = viewerRef.current;
    if (!viewer || !entity) return;
    const point = pointFromGeometry(entity.geometry);
    if (!point) return;
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(point.lon, point.lat, entity.entity_kind === "satellite" ? 4_200_000 : 1_800_000),
      duration: 0.8
    });
  }

  function flyToEvent(event: EventRecord) {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const point = geometryCenter(event.geometry ?? undefined);
    if (!point) return;
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(point.lon, point.lat, 3_500_000),
      duration: 0.8
    });
  }

  function handleTrackClick(track: "aircraft" | "maritime" | "satellites" | "alerts") {
    setActiveTrack(track);
    if (track === "aircraft") {
      setLayers((current) => ({ ...current, aircraft: !current.aircraft }));
    } else if (track === "maritime") {
      setLayers((current) => ({ ...current, vessels: !current.vessels }));
    } else if (track === "satellites") {
      setLayers((current) => ({ ...current, satellites: !current.satellites }));
    } else {
      setLayers((current) => ({ ...current, events: !current.events, eonet: !current.eonet, firms: !current.firms, nws: !current.nws }));
    }
  }

  function handleFilterClick(value: string) {
    setSearchValue(value);
    const match = (viewData?.entities ?? []).find((entity) => {
      const haystack = `${entity.label} ${JSON.stringify(entity.properties)}`.toLowerCase();
      return haystack.includes(value.toLowerCase());
    });
    if (match) {
      setSelection({ kind: "entity", id: match.id });
      flyToEntity(match);
    }
  }

  function handleFilterActionClick(value: string) {
    handleFilterClick(value);
    setShowMoreInfo(true);
  }

  function handleTimelineEventClick(event: EventRecord) {
    setSelection({ kind: "event", id: event.id });
    flyToEvent(event);
    setShowMoreInfo(true);
  }

  function applyMapPreset(name: MapPresetName, duration = 0.8) {
    const viewer = viewerRef.current;
    if (!viewer) return;

    setMapLabel(name);
    if (name === "Global") {
      viewer.camera.flyTo({
        destination: Cartesian3.fromDegrees(14, 18, 26_000_000),
        orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
        duration
      });
      return;
    }
    if (name === "Atlantic") {
      viewer.camera.flyTo({
        destination: Cartesian3.fromDegrees(-35, 25, 15_000_000),
        orientation: { heading: 0, pitch: CesiumMath.toRadians(-72), roll: 0 },
        duration
      });
      return;
    }
    if (name === "Europe") {
      viewer.camera.flyTo({
        destination: Cartesian3.fromDegrees(14, 46, 8_500_000),
        orientation: { heading: 0, pitch: CesiumMath.toRadians(-65), roll: 0 },
        duration
      });
      return;
    }
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(120, 10, 13_000_000),
      orientation: { heading: 0, pitch: CesiumMath.toRadians(-70), roll: 0 },
      duration
    });
  }

  function applyLayerPreset(name: LayerPresetName) {
    setLayerLabel(name);
    if (name === "All Layers") {
      setLayers({ ...initialLayers });
      setStatusText("Layer preset: all");
      return;
    }
    if (name === "Space + Events") {
      setLayers((current) => ({
        ...current,
        aircraft: false,
        vessels: false,
        satellites: true,
        airspace: false,
        aois: true,
        events: true,
        eonet: true,
        firms: true,
        nws: true
      }));
      setStatusText("Layer preset: space + events");
      return;
    }
    if (name === "Surface + Alerts") {
      setLayers((current) => ({
        ...current,
        aircraft: true,
        vessels: true,
        satellites: false,
        airspace: true,
        aois: true,
        events: true,
        eonet: true,
        firms: true,
        nws: true
      }));
      setStatusText("Layer preset: surface + alerts");
      return;
    }
    setLayers((current) => ({
      ...current,
      aircraft: true,
      vessels: true,
      satellites: true,
      airspace: false,
      aois: false,
      events: false,
      eonet: false,
      firms: false,
      nws: false
    }));
    setStatusText("Layer preset: tracks only");
  }

  return (
    <EagleEyeLayout
      setGlobeRef={(node) => {
        globeRef.current = node;
      }}
      statusLabel={runtimeStatus.label}
      statusTone={runtimeStatus.tone}
      utcDisplay={`${formatUtcDateTime(timeState?.current_timestamp)}${effectiveViewMode === "replay" ? " · REPLAY" : ""}`}
      searchValue={searchValue}
      onSearchChange={setSearchValue}
      layerLabel={layerLabel}
      mapLabel={mapLabel}
      layerOptions={[
        { label: "All Layers", onSelect: () => applyLayerPreset("All Layers") },
        { label: "Space + Events", onSelect: () => applyLayerPreset("Space + Events") },
        { label: "Surface + Alerts", onSelect: () => applyLayerPreset("Surface + Alerts") },
        { label: "Tracks Only", onSelect: () => applyLayerPreset("Tracks Only") }
      ]}
      mapOptions={[
        { label: "Global", onSelect: () => applyMapPreset("Global") },
        { label: "Atlantic", onSelect: () => applyMapPreset("Atlantic") },
        { label: "Europe", onSelect: () => applyMapPreset("Europe") },
        { label: "Indo-Pacific", onSelect: () => applyMapPreset("Indo-Pacific") },
        { label: "Reset View", onSelect: resetGlobalMap }
      ]}
      trackCounts={trackCounts}
      filterValues={selectedIdentifiers}
      activeTrack={activeTrack}
      onTrackClick={handleTrackClick}
      onFilterClick={handleFilterClick}
      onFilterActionClick={handleFilterActionClick}
      selectedTitle={selectedLabel(selectedEntity, selectedEvent)}
      selectedEntity={selectedEntity}
      selectedEvent={selectedEvent}
      bundle={bundle}
      satelliteFov={satelliteFov}
      followSelected={followSelected}
      onToggleFollow={() => setFollowSelected((value) => !value)}
      onToggleTrajectory={() => setTrajectoryEnabled((value) => !value)}
      onMoreInfo={() => setShowMoreInfo((value) => !value)}
      trajectoryEnabled={trajectoryEnabled}
      showMoreInfo={showMoreInfo}
      timelineEvents={timelineEvents}
      onTimelineEventClick={handleTimelineEventClick}
      loading={isViewLoading}
      statusText={statusText}
      passLabel={formatRelativePass(bundle?.timeline?.predicted?.[0]?.observed_at ?? satelliteFov?.timestamp)}
      nextPassUtc={formatUtc(bundle?.timeline?.predicted?.[0]?.observed_at ?? satelliteFov?.timestamp)}
    />
  );
}

export default App;
