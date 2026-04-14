import type {
  AoiRecord,
  AoiUpdate,
  CaseRecord,
  CaseUpdate,
  EntityTimelineResponse,
  EventRecord,
  GlobeViewState,
  InvestigationBundle,
  LiveEnvelope,
  NoteRecord,
  NoteUpdate,
  RelationshipRecord,
  SatelliteFovResponse,
  SatellitePassResponse,
  SourceStatusRecord,
  TagRecord,
  TimeState,
  ViewQueryResponse,
  WatchlistRecord,
  WatchlistUpdate,
  WorkspaceRecord
} from "@eagle-eye/shared-types";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").trim();

function normalizedBaseUrl(): string {
  if (!apiBaseUrl) return "";
  return apiBaseUrl.endsWith("/") ? apiBaseUrl.slice(0, -1) : apiBaseUrl;
}

function buildUrl(path: string): string {
  const base = normalizedBaseUrl();
  if (!base) return path;
  if (base.startsWith("http://") || base.startsWith("https://")) {
    return `${base}${path}`;
  }
  return `${base}${path}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const requestUrl = buildUrl(path);
  const response = await fetch(requestUrl, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${path}`);
  }
  return response.json() as Promise<T>;
}

export function websocketUrl(): string {
  const base = normalizedBaseUrl();
  if (base.startsWith("http://") || base.startsWith("https://")) {
    const url = new URL(base);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = "/ws/live";
    return url.toString();
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/live`;
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
  getSourceStatus: () => requestJson<SourceStatusRecord[]>("/api/sources/status"),
  investigateEntity: (entityId: string) => requestJson<InvestigationBundle>(`/api/investigate/${encodeURIComponent(entityId)}`),
  getEntityTimeline: (entityId: string, params?: URLSearchParams) =>
    requestJson<EntityTimelineResponse>(
      `/api/entities/${encodeURIComponent(entityId)}/timeline${params ? `?${params.toString()}` : ""}`
    ),
  getCases: () => requestJson<CaseRecord[]>("/api/cases"),
  createCase: (payload: Partial<CaseRecord>) =>
    requestJson<CaseRecord>("/api/cases", { method: "POST", body: JSON.stringify(payload) }),
  updateCase: (caseId: string, payload: CaseUpdate) =>
    requestJson<CaseRecord>(`/api/cases/${caseId}`, { method: "PUT", body: JSON.stringify(payload) }),
  getWorkspaces: () => requestJson<WorkspaceRecord[]>("/api/workspaces"),
  createWorkspace: (payload: Partial<WorkspaceRecord>) =>
    requestJson<WorkspaceRecord>("/api/workspaces", { method: "POST", body: JSON.stringify(payload) }),
  updateWorkspace: (workspaceId: string, payload: Record<string, unknown>) =>
    requestJson<WorkspaceRecord>(`/api/workspaces/${workspaceId}`, { method: "PUT", body: JSON.stringify(payload) }),
  getWatchlists: () => requestJson<WatchlistRecord[]>("/api/watchlists"),
  createWatchlist: (payload: Partial<WatchlistRecord>) =>
    requestJson<WatchlistRecord>("/api/watchlists", { method: "POST", body: JSON.stringify(payload) }),
  updateWatchlist: (watchlistId: string, payload: WatchlistUpdate) =>
    requestJson<WatchlistRecord>(`/api/watchlists/${watchlistId}`, { method: "PUT", body: JSON.stringify(payload) }),
  addWatchlistEntity: (watchlistId: string, payload: Record<string, unknown>) =>
    requestJson<WatchlistRecord>(`/api/watchlists/${watchlistId}/entities`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  removeWatchlistEntity: (watchlistId: string, entityId: string) =>
    requestJson<WatchlistRecord>(
      `/api/watchlists/${watchlistId}/entities?entity_id=${encodeURIComponent(entityId)}`,
      { method: "DELETE" }
    ),
  getNotes: () => requestJson<NoteRecord[]>("/api/notes"),
  createNote: (payload: Partial<NoteRecord>) =>
    requestJson<NoteRecord>("/api/notes", { method: "POST", body: JSON.stringify(payload) }),
  updateNote: (noteId: string, payload: NoteUpdate) =>
    requestJson<NoteRecord>(`/api/notes/${noteId}`, { method: "PUT", body: JSON.stringify(payload) }),
  getTags: () => requestJson<TagRecord[]>("/api/tags"),
  createTag: (payload: Partial<TagRecord>) =>
    requestJson<TagRecord>("/api/tags", { method: "POST", body: JSON.stringify(payload) }),
  getAois: () => requestJson<AoiRecord[]>("/api/aois"),
  createAoi: (payload: Record<string, unknown>) =>
    requestJson<AoiRecord>("/api/aois", { method: "POST", body: JSON.stringify(payload) }),
  updateAoi: (aoiId: string, payload: AoiUpdate) =>
    requestJson<AoiRecord>(`/api/aois/${aoiId}`, { method: "PUT", body: JSON.stringify(payload) }),
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
