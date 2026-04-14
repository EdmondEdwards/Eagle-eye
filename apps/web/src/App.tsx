import {
  Cartesian2,
  Cartesian3,
  Color,
  Ion,
  JulianDate,
  LabelStyle,
  Math as CesiumMath,
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
  AoiRecord,
  CaseRecord,
  EntityRecord,
  EventRecord,
  GlobeViewState,
  InvestigationBundle,
  NoteRecord,
  RelationshipRecord,
  SatelliteFovResponse,
  SourceStatusRecord,
  TagRecord,
  TimeState,
  ViewQueryResponse,
  WatchlistRecord,
  WorkspaceRecord
} from "@eagle-eye/shared-types";
import { layerDefinitions } from "@eagle-eye/ui";
import { api, connectLiveFeed } from "./lib/api";

type LayerState = Record<string, boolean>;
type Selection = { kind: "entity" | "cluster" | "event"; id: string } | null;

type RightTab = "selection" | "events" | "relationships" | "investigation";

const initialLayers: LayerState = Object.fromEntries(layerDefinitions.map((layer) => [layer.key, true]));
const timeModes: TimeState["mode"][] = ["live", "paused", "replay", "simulate"];
const cameraPresets = [
  { key: "global", label: "Global", lon: -20, lat: 24, height: 19_000_000 },
  { key: "atlantic", label: "Atlantic", lon: -35, lat: 35, height: 7_500_000 },
  { key: "europe", label: "Europe", lon: 12, lat: 50, height: 5_400_000 },
  { key: "indo", label: "Indo-Pacific", lon: 118, lat: 11, height: 8_400_000 }
] as const;

function formatDate(iso?: string | null): string {
  if (!iso) return "n/a";
  return new Date(iso).toLocaleString();
}

function normalizeLongitude(value: number): number {
  return ((value + 540) % 360) - 180;
}

function viewModeFromTime(mode: TimeState["mode"]): GlobeViewState["mode"] {
  if (mode === "simulate") return "simulate";
  if (mode === "replay" || mode === "paused") return "replay";
  return "live";
}

function buildViewState(
  viewer: Viewer,
  timeState: TimeState,
  layers: LayerState,
  selectedEntities: string[],
  selectedAois: string[]
): GlobeViewState | null {
  const rectangle = viewer.camera.computeViewRectangle(viewer.scene.globe.ellipsoid);
  if (!rectangle) return null;
  const enabledLayers = Object.entries(layers)
    .filter(([, enabled]) => enabled)
    .map(([key]) => key);

  return {
    west: normalizeLongitude(CesiumMath.toDegrees(rectangle.west)),
    south: CesiumMath.toDegrees(rectangle.south),
    east: normalizeLongitude(CesiumMath.toDegrees(rectangle.east)),
    north: CesiumMath.toDegrees(rectangle.north),
    camera_height: viewer.camera.positionCartographic.height,
    heading: CesiumMath.toDegrees(viewer.camera.heading),
    pitch: CesiumMath.toDegrees(viewer.camera.pitch),
    roll: CesiumMath.toDegrees(viewer.camera.roll),
    timestamp: timeState.current_timestamp,
    mode: viewModeFromTime(timeState.mode),
    enabled_layers: enabledLayers,
    selected_entities: selectedEntities,
    selected_aois: selectedAois
  };
}

function pointFromGeometry(geometry?: { type: string; coordinates?: unknown } | null): { lon: number; lat: number } | null {
  if (!geometry?.coordinates || geometry.type !== "Point") return null;
  const coords = geometry.coordinates as [number, number];
  return { lon: coords[0], lat: coords[1] };
}

function polygonHierarchy(geometry?: { type: string; coordinates?: unknown } | null): Cartesian3[] | null {
  if (!geometry?.coordinates || geometry.type !== "Polygon") return null;
  const firstRing = (geometry.coordinates as number[][][])[0];
  return firstRing.map(([lon, lat]) => Cartesian3.fromDegrees(lon, lat));
}

function detailRows(record?: EntityRecord | EventRecord | RelationshipRecord | null): Array<[string, string]> {
  if (!record) return [];
  return Object.entries(record)
    .filter(([, value]) => value !== null && value !== undefined && typeof value !== "object")
    .map(([key, value]) => [key, String(value)]);
}

function selectionPoint(entity?: EntityRecord | null): { lon: number; lat: number } | null {
  return pointFromGeometry(entity?.geometry);
}

function timelineStats(bundle?: InvestigationBundle | null): {
  historyCount: number;
  predictedCount: number;
  first?: string;
  last?: string;
} {
  const history = bundle?.timeline?.history ?? [];
  const predicted = bundle?.timeline?.predicted ?? [];
  return {
    historyCount: history.length,
    predictedCount: predicted.length,
    first: history[0]?.observed_at,
    last: predicted[predicted.length - 1]?.observed_at ?? history[history.length - 1]?.observed_at
  };
}

function App() {
  const globeRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const refreshTimerRef = useRef<number | null>(null);

  const [timeState, setTimeState] = useState<TimeState | null>(null);
  const [layers, setLayers] = useState<LayerState>(initialLayers);
  const [viewData, setViewData] = useState<ViewQueryResponse | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceRecord[]>([]);
  const [watchlists, setWatchlists] = useState<WatchlistRecord[]>([]);
  const [sourceStatus, setSourceStatus] = useState<SourceStatusRecord[]>([]);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [notes, setNotes] = useState<NoteRecord[]>([]);
  const [tags, setTags] = useState<TagRecord[]>([]);
  const [aois, setAois] = useState<AoiRecord[]>([]);
  const [recentEvents, setRecentEvents] = useState<EventRecord[]>([]);
  const [relationships, setRelationships] = useState<RelationshipRecord[]>([]);
  const [bundle, setBundle] = useState<InvestigationBundle | null>(null);
  const [selectedSatelliteFov, setSelectedSatelliteFov] = useState<SatelliteFovResponse | null>(null);
  const [followSelected, setFollowSelected] = useState(false);
  const [eventSeverityFilter, setEventSeverityFilter] = useState<"all" | "low" | "medium" | "high">("all");
  const [entitySearch, setEntitySearch] = useState("");
  const [activeRightTab, setActiveRightTab] = useState<RightTab>("selection");
  const [statusText, setStatusText] = useState("Waiting for backend");
  const [socketOnline, setSocketOnline] = useState(false);

  const selectedEntity = useMemo(
    () => viewData?.entities.find((entity) => entity.id === selection?.id) ?? null,
    [selection, viewData]
  );
  const selectedEvent = useMemo(
    () => viewData?.events.find((event) => event.id === selection?.id) ?? null,
    [selection, viewData]
  );
  const selectedAoiIds = useMemo(
    () => aois.map((aoi) => aoi.id),
    [aois]
  );
  const bundleTimeline = useMemo(() => timelineStats(bundle), [bundle]);
  const filteredEntities = useMemo(() => {
    const query = entitySearch.trim().toLowerCase();
    if (!query) return viewData?.entities ?? [];
    return (viewData?.entities ?? []).filter((entity) => {
      const haystack = `${entity.label} ${JSON.stringify(entity.properties)}`.toLowerCase();
      return haystack.includes(query);
    });
  }, [entitySearch, viewData]);
  const filteredEvents = useMemo(() => {
    const rows = selectedEntity ? recentEvents.filter((event) => event.entity_id === selectedEntity.id) : recentEvents;
    if (eventSeverityFilter === "all") return rows;
    return rows.filter((event) => event.severity === eventSeverityFilter);
  }, [eventSeverityFilter, recentEvents, selectedEntity]);
  const selectedCluster = useMemo(
    () => (selection?.kind === "cluster" ? viewData?.clusters.find((item) => item.id === selection.id) ?? null : null),
    [selection, viewData]
  );

  async function loadSidebarData() {
    const results = await Promise.allSettled([
      api.getWorkspaces(),
      api.getWatchlists(),
      api.getSourceStatus(),
      api.getCases(),
      api.getNotes(),
      api.getTags(),
      api.getAois(),
      api.getEvents()
    ]);

    const [
      workspaceRows,
      watchlistRows,
      sourceRows,
      caseRows,
      noteRows,
      tagRows,
      aoiRows,
      liveEvents
    ] = results;

    if (workspaceRows.status === "fulfilled") setWorkspaces(workspaceRows.value);
    if (watchlistRows.status === "fulfilled") setWatchlists(watchlistRows.value);
    if (sourceRows.status === "fulfilled") setSourceStatus(sourceRows.value);
    if (caseRows.status === "fulfilled") setCases(caseRows.value);
    if (noteRows.status === "fulfilled") setNotes(noteRows.value);
    if (tagRows.status === "fulfilled") setTags(tagRows.value);
    if (aoiRows.status === "fulfilled") setAois(aoiRows.value);
    if (liveEvents.status === "fulfilled") setRecentEvents(liveEvents.value);

    const failures = results
      .filter((result): result is PromiseRejectedResult => result.status === "rejected")
      .map((result) => String(result.reason));

    if (failures.length > 0) {
      setStatusText(`Partial backend mismatch: ${failures[0]}`);
    }
  }

  async function refreshRelationships(selectedIds: string[]) {
    const rows = await api.getRelationships(selectedIds);
    setRelationships(rows);
  }

  async function refreshView() {
    if (!viewerRef.current || !timeState) return;
    const payload = buildViewState(
      viewerRef.current,
      timeState,
      layers,
      selectedEntity ? [selectedEntity.id] : [],
      selectedAoiIds
    );
    if (!payload) {
      setStatusText("Camera initializing");
      return;
    }
    const response = await api.queryView(payload);
    startTransition(() => {
      setViewData(response);
      setStatusText(
        `${response.stats.entities} entities, ${response.stats.events} events, ${response.stats.clusters} clusters`
      );
    });
  }

  function scheduleRefresh(delay = 250) {
    if (refreshTimerRef.current) {
      window.clearTimeout(refreshTimerRef.current);
    }
    refreshTimerRef.current = window.setTimeout(() => {
      refreshView().catch((error: unknown) => setStatusText(String(error)));
    }, delay);
  }

  useEffect(() => {
    api
      .getTimeState()
      .then((state) => {
        setTimeState(state);
        setStatusText("Backend connected");
      })
      .catch((error: unknown) => setStatusText(String(error)));
    loadSidebarData().catch((error: unknown) => setStatusText(String(error)));
  }, []);

  useEffect(() => {
    if (!globeRef.current || viewerRef.current) return;
    Ion.defaultAccessToken = import.meta.env.CESIUM_ION_TOKEN ?? "";
    const viewer = new Viewer(globeRef.current, {
      animation: false,
      baseLayerPicker: false,
      geocoder: false,
      timeline: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      homeButton: false,
      infoBox: false,
      selectionIndicator: false
    });
    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(-20, 24, 19_000_000)
    });
    viewerRef.current = viewer;
    window.setTimeout(() => scheduleRefresh(50), 400);

    const handler = new ScreenSpaceEventHandler(viewer.canvas);
    handler.setInputAction((movement: { position: Cartesian2 }) => {
      const picked = viewer.scene.pick(movement.position) as Entity | undefined;
      const payload = (picked?.properties?.payload?.getValue?.(JulianDate.now()) ?? null) as
        | { kind: "entity" | "cluster" | "event"; id: string }
        | null;
      if (payload) setSelection(payload);
    }, ScreenSpaceEventType.LEFT_CLICK);

    viewer.camera.moveEnd.addEventListener(() => scheduleRefresh(150));
    return () => {
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!timeState) return;
    scheduleRefresh(10);
  }, [timeState, layers]);

  useEffect(() => {
    if (!timeState) return;
    const socket = connectLiveFeed((message) => {
      if (message.topic === "view.invalidate" || message.topic === "events") {
        scheduleRefresh(150);
        loadSidebarData().catch(() => undefined);
      }
      if (message.topic === "heartbeat") setSocketOnline(true);
    });
    socket.onopen = () => setSocketOnline(true);
    socket.onclose = () => setSocketOnline(false);
    return () => socket.close();
  }, [timeState]);

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
    if (!viewerRef.current || !viewData) return;
    const viewer = viewerRef.current;
    viewer.entities.removeAll();

    for (const cluster of viewData.clusters) {
      viewer.entities.add({
        id: cluster.id,
        position: Cartesian3.fromDegrees(cluster.lon, cluster.lat),
        point: {
          pixelSize: 12 + Math.min(cluster.count, 24),
          color:
            cluster.entity_kind === "aircraft"
              ? Color.fromCssColorString("#ffd54a")
              : cluster.entity_kind === "vessel"
                ? Color.fromCssColorString("#6ee7ff")
                : Color.fromCssColorString("#9af6b0"),
          outlineColor: Color.BLACK,
          outlineWidth: 1
        },
        label: {
          text: `${cluster.count}`,
          font: "600 12px IBM Plex Sans",
          fillColor: Color.WHITE,
          style: LabelStyle.FILL_AND_OUTLINE,
          verticalOrigin: VerticalOrigin.BOTTOM,
          pixelOffset: new Cartesian2(0, -12)
        },
        properties: {
          payload: { kind: "cluster", id: cluster.id }
        }
      });
    }

    for (const event of viewData.events) {
      const point = pointFromGeometry(event.geometry ?? undefined);
      if (!point) continue;
      viewer.entities.add({
        id: event.id,
        position: Cartesian3.fromDegrees(point.lon, point.lat),
        point: {
          pixelSize: 10,
          color: Color.fromCssColorString("#ff6b6b"),
          outlineColor: Color.WHITE,
          outlineWidth: 1
        },
        label: {
          text: event.title,
          font: "500 11px IBM Plex Sans",
          fillColor: Color.fromCssColorString("#ffd7d7"),
          verticalOrigin: VerticalOrigin.TOP,
          pixelOffset: new Cartesian2(0, 10)
        },
        properties: {
          payload: { kind: "event", id: event.id }
        }
      });
    }

    for (const entity of filteredEntities) {
      const point = pointFromGeometry(entity.geometry);
      const polygon = polygonHierarchy(entity.geometry);
      const color =
        entity.entity_kind === "aircraft"
          ? "#ffd54a"
          : entity.entity_kind === "vessel"
            ? "#6ee7ff"
            : entity.entity_kind === "satellite"
              ? "#9af6b0"
              : entity.entity_kind === "aoi"
                ? "#f8e16c"
                : "#ff9b3d";

      if (point) {
        viewer.entities.add({
          id: entity.id,
          position: Cartesian3.fromDegrees(point.lon, point.lat),
          point: {
            pixelSize: selection?.id === entity.id ? 12 : 8,
            color: Color.fromCssColorString(color),
            outlineColor: Color.BLACK,
            outlineWidth: 1
          },
          label: {
            text: entity.label,
            font: selection?.id === entity.id ? "600 13px IBM Plex Sans" : "500 11px IBM Plex Sans",
            fillColor: Color.WHITE,
            show: selection?.id === entity.id,
            verticalOrigin: VerticalOrigin.TOP,
            pixelOffset: new Cartesian2(0, 10)
          },
          properties: {
            payload: { kind: "entity", id: entity.id }
          }
        });
      }

      if (polygon) {
        viewer.entities.add({
          id: `${entity.id}:polygon`,
          polygon: {
            hierarchy: polygon,
            material: Color.fromCssColorString(color).withAlpha(entity.entity_kind === "aoi" ? 0.18 : 0.12),
            outline: true,
            outlineColor: Color.fromCssColorString(color)
          },
          properties: {
            payload: { kind: "entity", id: entity.id }
          }
        });
      }

      if (selection?.id === entity.id && entity.predicted_path.length > 1) {
        viewer.entities.add({
          id: `${entity.id}:prediction`,
          polyline: {
            positions: entity.predicted_path.map((item) => Cartesian3.fromDegrees(item.lon, item.lat, item.altitude_m ?? 0)),
            width: 2,
            material: new PolylineDashMaterialProperty({
              color: Color.fromCssColorString(color),
              dashLength: 16
            })
          }
        });
      }
    }

    if (selectedEntity && bundle?.timeline?.history?.length && selection?.kind === "entity") {
      viewer.entities.add({
        id: `${selectedEntity.id}:history`,
        polyline: {
          positions: bundle.timeline.history.map((item) => Cartesian3.fromDegrees(item.lon, item.lat, item.altitude_m ?? 0)),
          width: 3,
          material: Color.fromCssColorString("#6ee7ff").withAlpha(0.72)
        }
      });
    }

    if (selectedSatelliteFov?.footprint) {
      const hierarchy = polygonHierarchy(selectedSatelliteFov.footprint);
      if (hierarchy) {
        viewer.entities.add({
          id: `${selectedSatelliteFov.satellite_id}:fov`,
          polygon: {
            hierarchy,
            material: Color.fromCssColorString("#9af6b0").withAlpha(0.12),
            outline: true,
            outlineColor: Color.fromCssColorString("#9af6b0")
          }
        });
      }
    }

    if (followSelected && selectedEntity) {
      const point = selectionPoint(selectedEntity);
      if (point) {
        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(point.lon, point.lat, 1_800_000),
          duration: 0.8
        });
      }
    }
  }, [filteredEntities, followSelected, selectedEntity, selectedSatelliteFov, selection, viewData]);

  useEffect(() => {
    if (!selectedEntity) {
      setSelectedSatelliteFov(null);
      setBundle(null);
      refreshRelationships([]).catch(() => undefined);
      return;
    }
    refreshRelationships([selectedEntity.id]).catch(() => undefined);
    api.investigateEntity(selectedEntity.id).then(setBundle).catch(() => setBundle(null));
    if (selectedEntity.entity_kind === "satellite") {
      api.getSatelliteFov(selectedEntity.id).then(setSelectedSatelliteFov).catch(() => setSelectedSatelliteFov(null));
    } else {
      setSelectedSatelliteFov(null);
    }
  }, [selectedEntity]);

  useEffect(() => {
    if (!timeState || timeState.status !== "playing") return;
    const interval = window.setInterval(() => {
      api.getTimeState().then(setTimeState).catch(() => undefined);
      if (timeState.mode === "live") scheduleRefresh(25);
    }, 2500);
    return () => window.clearInterval(interval);
  }, [timeState]);

  async function patchTime(update: Record<string, unknown>) {
    const next = await api.setTimeState(update);
    setTimeState(next);
  }

  async function saveWorkspace() {
    if (!viewerRef.current || !timeState) return;
    const name = window.prompt("Workspace name", `Workspace ${new Date().toLocaleTimeString()}`);
    if (!name) return;
    const camera = viewerRef.current.camera;
    await api.createWorkspace({
      name,
      description: "Saved from Eagle Eye v2",
      camera: {
        lon: CesiumMath.toDegrees(camera.positionCartographic.longitude),
        lat: CesiumMath.toDegrees(camera.positionCartographic.latitude),
        height: camera.positionCartographic.height,
        heading: CesiumMath.toDegrees(camera.heading),
        pitch: CesiumMath.toDegrees(camera.pitch),
        roll: CesiumMath.toDegrees(camera.roll)
      },
      time_context: timeState as unknown as Record<string, unknown>,
      layers,
      selected_entities: selectedEntity ? [selectedEntity.id] : [],
      selected_aois: selectedAoiIds
    });
    await loadSidebarData();
  }

  async function createQuickCase() {
    const title = window.prompt("Case title", selectedEntity ? `Investigate ${selectedEntity.label}` : "New case");
    if (!title) return;
    await api.createCase({
      title,
      summary: selectedEvent?.summary ?? (selectedEntity ? `Focused on ${selectedEntity.label}` : "Analyst-created case"),
      entities: selectedEntity ? [{ entity_kind: selectedEntity.entity_kind, entity_id: selectedEntity.id }] : []
    });
    await loadSidebarData();
  }

  async function addQuickNote() {
    const body = window.prompt("Note");
    if (!body) return;
    await api.createNote({
      body,
      entity_kind: selectedEntity?.entity_kind,
      entity_id: selectedEntity?.id
    });
    await loadSidebarData();
  }

  async function addWatchlist() {
    const name = window.prompt("Watchlist name", "Priority monitor");
    if (!name) return;
    const created = await api.createWatchlist({ name, color: "#6ee7ff" });
    if (selectedEntity) {
      await api.addWatchlistEntity(created.id, {
        entity_kind: selectedEntity.entity_kind,
        entity_id: selectedEntity.id,
        label: selectedEntity.label
      });
    }
    await loadSidebarData();
  }

  async function renameTopWatchlist() {
    const current = bundle?.watchlists?.[0] ?? watchlists[0];
    if (!current) return;
    const name = window.prompt("Rename watchlist", current.name);
    if (!name) return;
    await api.updateWatchlist(current.id, { name });
    await loadSidebarData();
    if (selectedEntity) api.investigateEntity(selectedEntity.id).then(setBundle).catch(() => undefined);
  }

  async function removeSelectionFromWatchlist() {
    const current = bundle?.watchlists?.[0];
    if (!current || !selectedEntity) return;
    await api.removeWatchlistEntity(current.id, selectedEntity.id);
    await loadSidebarData();
    api.investigateEntity(selectedEntity.id).then(setBundle).catch(() => undefined);
  }

  async function editLatestNote() {
    const current = bundle?.notes?.[0];
    if (!current) return;
    const body = window.prompt("Edit note", current.body);
    if (!body) return;
    await api.updateNote(current.id, { body });
    await loadSidebarData();
    if (selectedEntity) api.investigateEntity(selectedEntity.id).then(setBundle).catch(() => undefined);
  }

  async function renameAoi() {
    const current = bundle?.entity?.entity_kind === "aoi" ? bundle.entity : bundle?.aois?.[0];
    if (!current) return;
    const initialName = "label" in current ? current.label : current.name;
    const name = window.prompt("AOI name", initialName);
    if (!name) return;
    await api.updateAoi(current.id, { name });
    await loadSidebarData();
    if (selectedEntity) api.investigateEntity(selectedEntity.id).then(setBundle).catch(() => undefined);
  }

  async function updateCaseStatus() {
    const current = cases[0] ?? null;
    if (!current?.id) return;
    const status = window.prompt(`Update status for ${current.title ?? "case"}`, current.status ?? "active");
    if (!status) return;
    await api.updateCase(current.id, { status });
    await loadSidebarData();
  }

  async function createAoiFromSelection() {
    if (!selectedEntity) return;
    const point = pointFromGeometry(selectedEntity.geometry);
    if (!point) return;
    const name = window.prompt("AOI name", `${selectedEntity.label} AOI`);
    if (!name) return;
    await api.createAoi({
      name,
      description: "Circle AOI from selected entity",
      geometry_type: "circle",
      center: { lat: point.lat, lon: point.lon },
      radius_m: 150000,
      geometry: {
        type: "Polygon",
        coordinates: [[
          [point.lon - 1, point.lat - 1],
          [point.lon + 1, point.lat - 1],
          [point.lon + 1, point.lat + 1],
          [point.lon - 1, point.lat + 1],
          [point.lon - 1, point.lat - 1]
        ]]
      },
      tags: [selectedEntity.entity_kind]
    });
    await loadSidebarData();
  }

  return (
    <div className="app-shell">
      <aside className="panel left-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Eagle Eye</p>
            <h1>v2 Intelligence Desk</h1>
          </div>
          <span className={`pill ${socketOnline ? "online" : ""}`}>{socketOnline ? "Live bus" : "Offline"}</span>
        </div>

        <section className="card">
          <h2>Sources</h2>
          <p className="muted">Database-first viewport rendering. Globe only requests what the camera can see.</p>
          <input
            value={entitySearch}
            onChange={(event) => setEntitySearch(event.target.value)}
            placeholder="Search visible entities"
          />
          <div className="layer-grid">
            {layerDefinitions.map((layer) => (
              <button
                key={layer.key}
                className={`layer-chip ${layers[layer.key] ? "active" : ""}`}
                onClick={() => setLayers((current) => ({ ...current, [layer.key]: !current[layer.key] }))}
              >
                <span style={{ backgroundColor: layer.color }} />
                {layer.label}
              </button>
            ))}
          </div>
          <div className="stack-list compact">
            {sourceStatus.slice(0, 6).map((source) => (
              <div key={source.key} className="list-row static">
                <strong>{source.label}</strong>
                <span>
                  {source.status} • {source.item_count} items
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="section-row">
            <h2>Workspaces</h2>
            <button onClick={saveWorkspace}>Save</button>
          </div>
          <div className="preset-row">
            {cameraPresets.map((preset) => (
              <button
                key={preset.key}
                onClick={() =>
                  viewerRef.current?.camera.flyTo({
                    destination: Cartesian3.fromDegrees(preset.lon, preset.lat, preset.height),
                    duration: 0.9
                  })
                }
              >
                {preset.label}
              </button>
            ))}
          </div>
          <div className="stack-list">
            {workspaces.slice(0, 6).map((workspace) => (
              <button
                key={workspace.id}
                className="list-row"
                onClick={() => {
                  const camera = workspace.camera as Record<string, number>;
                  viewerRef.current?.camera.flyTo({
                    destination: Cartesian3.fromDegrees(camera.lon ?? -20, camera.lat ?? 20, camera.height ?? 8_000_000)
                  });
                  patchTime(workspace.time_context as Record<string, unknown>).catch(() => undefined);
                  const nextLayers = (workspace.layers as Record<string, boolean>) ?? initialLayers;
                  setLayers((current) => ({ ...current, ...nextLayers }));
                }}
              >
                <strong>{workspace.name}</strong>
                <span>{formatDate(workspace.updated_at)}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="section-row">
            <h2>Watchlists</h2>
            <button onClick={addWatchlist}>New</button>
          </div>
          <div className="stack-list">
            {watchlists.slice(0, 5).map((watchlist) => (
              <div key={watchlist.id} className="list-row static">
                <strong>{watchlist.name}</strong>
                <span>{watchlist.entities.length} entities</span>
              </div>
            ))}
          </div>
        </section>

        <section className="card">
          <h2>Live Events</h2>
          <div className="stack-list compact">
            {recentEvents.slice(0, 5).map((event) => (
              <button key={event.id} className="list-row" onClick={() => setSelection({ kind: "event", id: event.id })}>
                <strong>{event.title}</strong>
                <span>{event.category}</span>
              </button>
            ))}
          </div>
        </section>
      </aside>

      <main className="globe-stage">
        <div className="top-strip">
          <div>
            <p className="eyebrow">Status</p>
            <h2>{statusText}</h2>
          </div>
          <div className="metric-row">
            <div className="metric-card">
              <span>Mode</span>
              <strong>{timeState?.mode ?? "loading"}</strong>
            </div>
            <div className="metric-card">
              <span>Clock</span>
              <strong>{formatDate(timeState?.current_timestamp)}</strong>
            </div>
            <div className="metric-card">
              <span>Follow</span>
              <strong>{followSelected ? "On" : "Off"}</strong>
            </div>
          </div>
        </div>
        <div ref={globeRef} className="globe-canvas" />
        <div className="floating-actions">
          <button onClick={() => setFollowSelected((value) => !value)}>{followSelected ? "Unfollow" : "Follow"}</button>
          <button onClick={createQuickCase}>Create case</button>
          <button onClick={addQuickNote}>Add note</button>
          <button onClick={createAoiFromSelection} disabled={!selectedEntity}>
            AOI from selection
          </button>
          <button onClick={updateCaseStatus}>Update case</button>
        </div>
      </main>

      <aside className="panel right-panel">
        <section className="card">
          <div className="tab-row">
            {(["selection", "events", "relationships", "investigation"] as RightTab[]).map((tab) => (
              <button
                key={tab}
                className={activeRightTab === tab ? "tab-active" : ""}
                onClick={() => setActiveRightTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
        </section>

        {activeRightTab === "selection" ? (
        <section className="card">
          <div className="section-row">
            <h2>Selection</h2>
            <button onClick={() => setSelection(null)}>Clear</button>
          </div>
          <div className="detail-block">
            <h3>{selectedEntity?.label ?? selectedEvent?.title ?? "No active selection"}</h3>
            <p className="muted">
              {selectedEntity
                ? `${selectedEntity.entity_kind} • observed ${formatDate(selectedEntity.observed_at)}`
                : selectedEvent
                  ? `${selectedEvent.category} • ${formatDate(selectedEvent.start_time)}`
                  : "Click an entity, AOI, event, or cluster on the globe."}
            </p>
            {detailRows(selectedEntity ?? selectedEvent).slice(0, 10).map(([key, value]) => (
              <div key={key} className="kv-row">
                <span>{key}</span>
                <strong>{value}</strong>
              </div>
            ))}
            {selectedSatelliteFov ? (
              <div className="fov-card">
                <span>Sensor swath</span>
                <strong>{selectedSatelliteFov.swath_km.toFixed(0)} km</strong>
              </div>
            ) : null}
            {bundle?.watchlists?.length ? (
              <div className="badge-row">
                {bundle.watchlists.map((watchlist) => (
                  <span key={watchlist.id} className="info-badge">
                    {watchlist.name}
                  </span>
                ))}
              </div>
            ) : null}
            <div className="action-row">
              <button onClick={renameTopWatchlist} disabled={!bundle?.watchlists?.length}>
                Rename watchlist
              </button>
              <button onClick={removeSelectionFromWatchlist} disabled={!bundle?.watchlists?.length || !selectedEntity}>
                Remove from watchlist
              </button>
              <button onClick={editLatestNote} disabled={!bundle?.notes?.length}>
                Edit note
              </button>
              <button onClick={renameAoi} disabled={!bundle?.aois?.length && bundle?.entity?.entity_kind !== "aoi"}>
                Rename AOI
              </button>
            </div>
          </div>
        </section>
        ) : null}

        {activeRightTab === "events" ? (
        <section className="card">
          <div className="section-row">
            <h2>Events</h2>
            <select value={eventSeverityFilter} onChange={(event) => setEventSeverityFilter(event.target.value as typeof eventSeverityFilter)}>
              <option value="all">all</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </div>
          <div className="stack-list">
            {filteredEvents
              .slice(0, 8)
              .map((event) => (
                <button key={event.id} className="list-row" onClick={() => setSelection({ kind: "event", id: event.id })}>
                  <strong>{event.title}</strong>
                  <span>
                    {event.severity} • {formatDate(event.start_time)}
                  </span>
                </button>
              ))}
          </div>
        </section>
        ) : null}

        {activeRightTab === "relationships" ? (
        <section className="card">
          <h2>Relationships</h2>
          <div className="stack-list">
            {(bundle?.relationships ?? relationships).slice(0, 6).map((relationship) => (
              <div key={relationship.id} className="list-row static">
                <strong>{relationship.relationship_type}</strong>
                <span>
                  {relationship.source_id} → {relationship.target_id}
                </span>
              </div>
            ))}
          </div>
        </section>
        ) : null}

        {activeRightTab === "investigation" ? (
        <section className="card">
          <h2>Investigation</h2>
          <div className="stack-list">
            {selectedCluster ? (
              <div className="note-card">
                <strong>Cluster drill-in</strong>
                <p>{selectedCluster.count} tracks in cluster.</p>
                <p>{selectedCluster.sample_ids.slice(0, 4).join(", ")}</p>
              </div>
            ) : null}
            {bundle?.aois?.slice(0, 4).map((aoi) => (
              <div key={aoi.id} className="list-row static">
                <strong>{aoi.name}</strong>
                <span>{aoi.geometry_type}</span>
              </div>
            ))}
            {bundle?.notes?.slice(0, 3).map((note) => (
              <div key={note.id} className="note-card">
                <strong>{note.author}</strong>
                <p>{note.body}</p>
              </div>
            ))}
            {bundle?.aoi_events?.slice(0, 3).map((event) => (
              <div key={event.id} className="note-card">
                <strong>{event.title}</strong>
                <p>{event.category} • {formatDate(event.start_time)}</p>
              </div>
            ))}
            {bundle?.satellite_passes?.slice(0, 2).map((passWindow, index) => (
              <div key={index} className="note-card">
                <strong>{String(passWindow["aoi_name"] ?? "AOI pass window")}</strong>
                <p>{Array.isArray(passWindow["passes"]) ? `${passWindow["passes"].length} predicted passes` : "Pass analysis ready"}</p>
              </div>
            ))}
            {bundle?.aoi_passes?.slice(0, 2).map((windowItem, index) => (
              <div key={`aoi-pass-${index}`} className="note-card">
                <strong>{String(windowItem["name"] ?? windowItem["satellite_id"] ?? "Satellite pass")}</strong>
                <p>{Array.isArray(windowItem["passes"]) ? `${windowItem["passes"].length} pass windows` : "Pass analysis ready"}</p>
              </div>
            ))}
            {!bundle?.aois?.length && !bundle?.notes?.length && !bundle?.satellite_passes?.length ? (
              <p className="muted">Select an entity to open its investigation bundle.</p>
            ) : null}
          </div>
        </section>
        ) : null}

        <section className="card mini-grid">
          <div>
            <h2>Cases</h2>
            <strong>{cases.length}</strong>
          </div>
          <div>
            <h2>Notes</h2>
            <strong>{notes.length}</strong>
          </div>
          <div>
            <h2>Tags</h2>
            <strong>{tags.length}</strong>
          </div>
          <div>
            <h2>AOIs</h2>
            <strong>{aois.length}</strong>
          </div>
        </section>
      </aside>

      <footer className="timeline-bar">
        <div className="timeline-left">
          <span className="eyebrow">Time Engine</span>
          <div className="control-row">
            <button onClick={() => patchTime({ action: "step_back" })}>- Step</button>
            <button onClick={() => patchTime({ action: timeState?.status === "paused" ? "play" : "pause" })}>
              {timeState?.status === "paused" ? "Play" : "Pause"}
            </button>
            <button onClick={() => patchTime({ action: "step_forward" })}>+ Step</button>
            <select value={timeState?.mode ?? "live"} onChange={(event) => patchTime({ mode: event.target.value })}>
              {timeModes.map((mode) => (
                <option key={mode} value={mode}>
                  {mode}
                </option>
              ))}
            </select>
            <select
              value={String(timeState?.playback_speed ?? 1)}
              onChange={(event) => patchTime({ playback_speed: Number(event.target.value) })}
            >
              {[0.25, 1, 5, 20, 60].map((speed) => (
                <option key={speed} value={speed}>
                  {speed}x
                </option>
              ))}
            </select>
          </div>
          <div className="timeline-summary">
            <div className="timeline-stat">
              <span>History</span>
              <strong>{bundleTimeline.historyCount}</strong>
            </div>
            <div className="timeline-stat">
              <span>Forecast</span>
              <strong>{bundleTimeline.predictedCount}</strong>
            </div>
            <div className="timeline-stat wide">
              <span>Track Window</span>
              <strong>
                {bundleTimeline.first ? `${formatDate(bundleTimeline.first)} → ${formatDate(bundleTimeline.last)}` : "Select an entity"}
              </strong>
            </div>
          </div>
        </div>
        <div className="timeline-right">
          <div className="scrub-card">
            <span>Jump to UTC</span>
            <input
              type="datetime-local"
              onChange={(event) => {
                if (!event.target.value) return;
                patchTime({ action: "jump", current_timestamp: new Date(event.target.value).toISOString() });
              }}
            />
          </div>
          <div className="scrub-card">
            <span>Selected entities</span>
            <strong>{selectedEntity ? 1 : 0}</strong>
          </div>
          <div className="scrub-card timeline-card">
            <span>Replay Trace</span>
            <div className="trace-row">
              {(bundle?.timeline?.history ?? []).slice(-12).map((point, index) => (
                <span
                  key={`h-${index}-${point.observed_at}`}
                  className="trace-dot history"
                  title={formatDate(point.observed_at)}
                />
              ))}
              {(bundle?.timeline?.predicted ?? []).slice(0, 8).map((point, index) => (
                <span
                  key={`p-${index}-${point.observed_at}`}
                  className="trace-dot future"
                  title={formatDate(point.observed_at)}
                />
              ))}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
