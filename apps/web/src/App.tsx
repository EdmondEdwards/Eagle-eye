import {
  Cartesian2,
  Cartesian3,
  Color,
  Entity,
  GeoJsonDataSource,
  Ion,
  JulianDate,
  Math as CesiumMath,
  PinBuilder,
  PropertyBag,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  VerticalOrigin,
  Viewer
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { startTransition, useEffect, useMemo, useRef, useState } from "react";
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

function isoNowMinus(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

function entityLabel(entity: SelectedEntity): string {
  if (!entity) return "No selection";
  if (entity.kind === "aircraft") return entity.callsign?.trim() || entity.icao24;
  if (entity.kind === "vessel") return entity.vessel_name?.trim() || entity.mmsi;
  return entity.name;
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
        setStatus(`Tracking ${nextAircraft.length} aircraft, ${nextVessels.length} vessels, ${nextAirspace.length} overlays.`);
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
            return next.slice(0, 1200);
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
            return next.slice(0, 1200);
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

    const pinBuilder = new PinBuilder();
    if (layers.aircraft) {
      aircraft.forEach((item) => {
        viewer.entities.add({
          id: item.id,
          position: Cartesian3.fromDegrees(item.lon, item.lat, item.altitude_m ?? 0),
          billboard: {
            image: pinBuilder.fromColor(Color.fromCssColorString("#6ee7ff"), 28).toDataURL(),
            verticalOrigin: VerticalOrigin.BOTTOM
          },
          properties: createPropertyBag({ kind: "aircraft", data: item })
        });
      });
    }

    if (layers.vessels) {
      vessels.forEach((item) => {
        viewer.entities.add({
          id: item.id,
          position: Cartesian3.fromDegrees(item.lon, item.lat, 0),
          billboard: {
            image: pinBuilder.fromColor(Color.fromCssColorString("#4ade80"), 26).toDataURL(),
            verticalOrigin: VerticalOrigin.BOTTOM
          },
          properties: createPropertyBag({ kind: "vessel", data: item })
        });
      });
    }

    [...aircraftTracks, ...vesselTracks].forEach((track) => {
      if (track.points.length < 2) return;
      viewer.entities.add({
        id: `${track.entity_kind}:${track.entity_id}:track`,
        polyline: {
          positions: track.points.map((point) => Cartesian3.fromDegrees(point.lon, point.lat, point.altitude_m ?? 0)),
          width: 2,
          material: Color.fromCssColorString(track.entity_kind === "aircraft" ? "#6ee7ff" : "#4ade80")
        }
      });
    });
  }, [aircraft, vessels, aircraftTracks, vesselTracks, layers.aircraft, layers.vessels]);

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
          <div className="layer-strip">
            {layerDefinitions.map((layer) => (
              <label key={layer.key} className={`layer-chip ${layer.disabled ? "disabled" : ""}`}>
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
                  {"heading_deg" in selected ? <div><span>Heading</span><strong>{selected.heading_deg ?? "n/a"}°</strong></div> : null}
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
