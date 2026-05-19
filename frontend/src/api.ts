import type {
  Alert,
  BulkAction,
  Digest,
  GoogleStatus,
  Item,
  ItemState,
  StateFilter,
} from "./types";

const BASE = "/api";

async function req<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  let body: BodyInit | null | undefined = init?.body;
  if (init?.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const resp = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
    body,
    credentials: "include",
  });
  if (!resp.ok) {
    let detail = "";
    try {
      const data = await resp.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data);
    } catch {
      detail = await resp.text();
    }
    throw new Error(`${resp.status} ${resp.statusText}: ${detail}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

export const api = {
  me: () => req<{ email: string }>("/me"),

  // Alerts
  listAlerts: () => req<Alert[]>("/alerts"),
  createAlert: (data: {
    name: string;
    description?: string;
    subject_match?: string;
    color?: string;
    icon?: string;
    sort_order?: number;
  }) => req<Alert>("/alerts", { method: "POST", json: data }),
  updateAlert: (id: number, data: Partial<Alert>) =>
    req<Alert>(`/alerts/${id}`, { method: "PATCH", json: data }),
  deleteAlert: (id: number) =>
    req<void>(`/alerts/${id}`, { method: "DELETE" }),
  pollNow: () =>
    req<{ messages_seen: number; items_new: number; error: string }>(
      "/alerts/poll",
      { method: "POST" },
    ),

  // Google OAuth
  googleStatus: () => req<GoogleStatus>("/auth/google/status"),
  googleStart: (returnTo: string = "/") =>
    req<{ authorization_url: string }>(
      `/auth/google/start?return_to=${encodeURIComponent(returnTo)}`,
    ),
  googleDisconnect: () =>
    req<void>("/auth/google/disconnect", { method: "POST" }),

  // Items
  listItems: (params: {
    alert_id?: number;
    state?: StateFilter;
    since_hours?: number;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params.alert_id !== undefined) qs.set("alert_id", String(params.alert_id));
    if (params.state) qs.set("state", params.state);
    if (params.since_hours !== undefined) qs.set("since_hours", String(params.since_hours));
    if (params.limit !== undefined) qs.set("limit", String(params.limit));
    if (params.offset !== undefined) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return req<Item[]>(`/items${q ? "?" + q : ""}`);
  },
  patchItemState: (id: string, data: { read?: boolean; saved?: boolean; hidden?: boolean }) =>
    req<ItemState>(`/items/${id}/state`, { method: "PATCH", json: data }),
  bulkState: (ids: string[], action: BulkAction) =>
    req<void>("/items/bulk-state", { method: "POST", json: { ids, action } }),

  // Digest
  digestToday: () => req<Digest>("/digest/today"),
  digestWeek: () => req<Digest>("/digest/week"),
};
