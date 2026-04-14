import type {
  AoiRecord,
  CaseRecord,
  EventRecord,
  GlobeViewState,
  LiveEnvelope,
  NoteRecord,
  RelationshipRecord,
  SatelliteFovResponse,
  SatellitePassResponse,
  TagRecord,
  TimeState,
  ViewQueryResponse,
  WatchlistRecord,
  WorkspaceRecord
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
  getTimeState: () => requestJson<TimeState>("/api/time/state"),
  setTimeState: (payload: Partial<TimeState> & { action?: string }) =>
    requestJson<TimeState>("/api/time/set", { method: "POST", body: JSON.stringify(payload) }),
  queryView: (payload: GlobeViewState) =>
    requestJson<ViewQueryResponse>("/api/view/query", { method: "POST", body: JSON.stringify(payload) }),
  getEvents: () => requestJson<EventRecord[]>("/api/events/live"),
  getRelationships: (selectedIds?: string[]) =>
    requestJson<RelationshipRecord[]>(
      `/api/relationships${selectedIds?.length ? `?selected_ids=${encodeURIComponent(selectedIds.join(","))}` : ""}`
    ),
  getCases: () => requestJson<CaseRecord[]>("/api/cases"),
  createCase: (payload: Partial<CaseRecord>) =>
    requestJson<CaseRecord>("/api/cases", { method: "POST", body: JSON.stringify(payload) }),
  getWorkspaces: () => requestJson<WorkspaceRecord[]>("/api/workspaces"),
  createWorkspace: (payload: Partial<WorkspaceRecord>) =>
    requestJson<WorkspaceRecord>("/api/workspaces", { method: "POST", body: JSON.stringify(payload) }),
  updateWorkspace: (workspaceId: string, payload: Record<string, unknown>) =>
    requestJson<WorkspaceRecord>(`/api/workspaces/${workspaceId}`, { method: "PUT", body: JSON.stringify(payload) }),
  getWatchlists: () => requestJson<WatchlistRecord[]>("/api/watchlists"),
  createWatchlist: (payload: Partial<WatchlistRecord>) =>
    requestJson<WatchlistRecord>("/api/watchlists", { method: "POST", body: JSON.stringify(payload) }),
  addWatchlistEntity: (watchlistId: string, payload: Record<string, unknown>) =>
    requestJson<WatchlistRecord>(`/api/watchlists/${watchlistId}/entities`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getNotes: () => requestJson<NoteRecord[]>("/api/notes"),
  createNote: (payload: Partial<NoteRecord>) =>
    requestJson<NoteRecord>("/api/notes", { method: "POST", body: JSON.stringify(payload) }),
  getTags: () => requestJson<TagRecord[]>("/api/tags"),
  createTag: (payload: Partial<TagRecord>) =>
    requestJson<TagRecord>("/api/tags", { method: "POST", body: JSON.stringify(payload) }),
  getAois: () => requestJson<AoiRecord[]>("/api/aois"),
  createAoi: (payload: Record<string, unknown>) =>
    requestJson<AoiRecord>("/api/aois", { method: "POST", body: JSON.stringify(payload) }),
  getAoiEvents: (aoiId: string) => requestJson<EventRecord[]>(`/api/aois/${aoiId}/events`),
  getAoiPasses: (aoiId: string) => requestJson<Array<Record<string, unknown>>>(`/api/aois/${aoiId}/passes`),
  getSatelliteFov: (satelliteId: string) => requestJson<SatelliteFovResponse>(`/api/satellites/${satelliteId}/fov`),
  getSatellitePasses: (satelliteId: string, params: URLSearchParams) =>
    requestJson<SatellitePassResponse>(`/api/satellites/${satelliteId}/passes?${params.toString()}`)
};

export function connectLiveFeed(onMessage: (message: LiveEnvelope) => void): WebSocket {
  const socket = new WebSocket(websocketUrl());
  socket.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data) as LiveEnvelope);
    } catch {
      // Ignore malformed messages.
    }
  };
  return socket;
}
