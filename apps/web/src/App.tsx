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
  EntityRecord,
  EventRecord,
  GlobeViewState,
  RelationshipRecord,
  SatelliteFovResponse,
  TimeState,
  ViewQueryResponse,
  WatchlistRecord,
  WorkspaceRecord
} from "@eagle-eye/shared-types";
import { layerDefinitions } from "@eagle-eye/ui";
import { api, connectLiveFeed } from "./lib/api";

type LayerState = Record<string, boolean>;
type Selection = { kind: "entity" | "cluster" | "event"; id: string } | null;

const initialLayers: LayerState = Object.fromEntries(layerDefinitions.map((layer) => [layer.key, true]));
const timeModes: TimeState["mode"][] = ["live", "paused", "replay", "simulate"];

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
  const [cases, setCases] = useState<Array<Record<string, unknown>>>([]);
  const [notes, setNotes] = useState<Array<Record<string, unknown>>>([]);
  const [tags, setTags] = useState<Array<Record<string, unknown>>>([]);
  const [aois, setAois] = useState<AoiRecord[]>([]);
  const [recentEvents, setRecentEvents] = useState<EventRecord[]>([]);
  const [relationships, setRelationships] = useState<RelationshipRecord[]>([]);
  const [selectedSatelliteFov, setSelectedSatelliteFov] = useState<SatelliteFovResponse | null>(null);
  const [followSelected, setFollowSelected] = useState(false);
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

  async function loadSidebarData() {
    const [workspaceRows, watchlistRows, caseRows, noteRows, tagRows, aoiRows, liveEvents] = await Promise.all([
      api.getWorkspaces(),
      api.getWatchlists(),
      api.getCases(),
      api.getNotes(),
      api.getTags(),
      api.getAois(),
      api.getEvents()
    ]);
    setWorkspaces(workspaceRows);
    setWatchlists(watchlistRows);
    setCases(caseRows as Array<Record<string, unknown>>);
    setNotes(noteRows as Array<Record<string, unknown>>);
    setTags(tagRows as Array<Record<string, unknown>>);
    setAois(aoiRows);
    setRecentEvents(liveEvents);
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
    if (!payload) return;
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
      .then(setTimeState)
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

    for (const entity of viewData.entities) {
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
      const point = pointFromGeometry(selectedEntity.geometry);
      if (point) {
        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(point.lon, point.lat, 1_800_000),
          duration: 0.8
        });
      }
    }
  }, [followSelected, selectedEntity, selectedSatelliteFov, selection, viewData]);

  useEffect(() => {
    if (!selectedEntity) {
      setSelectedSatelliteFov(null);
      refreshRelationships([]).catch(() => undefined);
      return;
    }
    refreshRelationships([selectedEntity.id]).catch(() => undefined);
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
      time_context: timeState,
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
        </section>

        <section className="card">
          <div className="section-row">
            <h2>Workspaces</h2>
            <button onClick={saveWorkspace}>Save</button>
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
        </div>
      </main>

      <aside className="panel right-panel">
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
          </div>
        </section>

        <section className="card">
          <h2>Events</h2>
          <div className="stack-list">
            {(selectedEntity ? recentEvents.filter((event) => event.entity_id === selectedEntity.id) : recentEvents)
              .slice(0, 6)
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

        <section className="card">
          <h2>Relationships</h2>
          <div className="stack-list">
            {relationships.slice(0, 6).map((relationship) => (
              <div key={relationship.id} className="list-row static">
                <strong>{relationship.relationship_type}</strong>
                <span>
                  {relationship.source_id} → {relationship.target_id}
                </span>
              </div>
            ))}
          </div>
        </section>

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
        </div>
      </footer>
    </div>
  );
}

export default App;
