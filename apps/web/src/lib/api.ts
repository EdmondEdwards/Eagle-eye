import type {
  Aircraft,
  AirspaceOverlay,
  CaseRecord,
  LiveEnvelope,
  NoteRecord,
  SavedViewRecord,
    SearchResult,
    Satellite,
    TagRecord,
  TimelineResponse,
  Vessel,
  WatchlistRecord
} from "@eagle-eye/shared-types";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function websocketUrl(): string {
  const url = new URL(apiBaseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/live";
  return url.toString();
}

export const api = {
  getAircraftCurrent: (bbox?: string) =>
    requestJson<Aircraft[]>(`/api/aircraft/current?limit=5000${bbox ? `&bbox=${encodeURIComponent(bbox)}` : ""}`),
  getAircraftHistory: (params: URLSearchParams) =>
    requestJson<TimelineResponse>(`/api/aircraft/history?${params.toString()}`),
  getVesselsCurrent: (bbox?: string) =>
    requestJson<Vessel[]>(`/api/vessels/current?limit=5000${bbox ? `&bbox=${encodeURIComponent(bbox)}` : ""}`),
  getVesselsHistory: (params: URLSearchParams) =>
    requestJson<TimelineResponse>(`/api/vessels/history?${params.toString()}`),
  getSatellitesCurrent: (bbox?: string) =>
    requestJson<Satellite[]>(`/api/satellites/current?limit=2500${bbox ? `&bbox=${encodeURIComponent(bbox)}` : ""}`),
  getSatellitesHistory: (params: URLSearchParams) =>
    requestJson<TimelineResponse>(`/api/satellites/history?${params.toString()}`),
  getAirspaceCurrent: () => requestJson<AirspaceOverlay[]>("/api/airspace/current"),
  getCases: () => requestJson<CaseRecord[]>("/api/cases"),
  createCase: (payload: Partial<CaseRecord>) =>
    requestJson<CaseRecord>("/api/cases", { method: "POST", body: JSON.stringify(payload) }),
  getWatchlists: () => requestJson<WatchlistRecord[]>("/api/watchlists"),
  createWatchlist: (payload: Partial<WatchlistRecord>) =>
    requestJson<WatchlistRecord>("/api/watchlists", { method: "POST", body: JSON.stringify(payload) }),
  getNotes: () => requestJson<NoteRecord[]>("/api/notes"),
  createNote: (payload: Partial<NoteRecord>) =>
    requestJson<NoteRecord>("/api/notes", { method: "POST", body: JSON.stringify(payload) }),
  getTags: () => requestJson<TagRecord[]>("/api/tags"),
  createTag: (payload: Partial<TagRecord>) =>
    requestJson<TagRecord>("/api/tags", { method: "POST", body: JSON.stringify(payload) }),
  getSavedViews: () => requestJson<SavedViewRecord[]>("/api/saved-views"),
  createSavedView: (payload: Partial<SavedViewRecord>) =>
    requestJson<SavedViewRecord>("/api/saved-views", { method: "POST", body: JSON.stringify(payload) }),
  search: (query: string) => requestJson<SearchResult[]>(`/api/search?q=${encodeURIComponent(query)}`)
};

export function connectLiveFeed(onMessage: (message: LiveEnvelope) => void): WebSocket {
  const socket = new WebSocket(websocketUrl());
  socket.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data) as LiveEnvelope);
    } catch {
      // Ignore malformed frames from a noisy network edge.
    }
  };
  return socket;
}
