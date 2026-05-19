export interface Alert {
  id: number;
  name: string;
  description: string;
  subject_match: string;
  color: string;
  icon: string;
  sort_order: number;
  last_fetched_at: string | null;
  last_status: number | null;
  last_error: string;
  created_at: string;
  unread_count: number;
  total_count: number;
}

export interface GoogleStatus {
  connected: boolean;
  email: string;
  scopes: string[];
  last_polled_at: string | null;
}

export interface ItemState {
  read_at: string | null;
  saved_at: string | null;
  hidden_at: string | null;
}

export interface Item {
  id: string;
  alert_id: number;
  alert_name: string;
  alert_color: string;
  alert_icon: string;
  title: string;
  snippet: string;
  source_domain: string;
  link: string;
  published_at: string;
  seen_at: string;
  state: ItemState | null;
}

export interface DigestGroup {
  alert: Alert;
  items: Item[];
}

export interface Digest {
  window: "today" | "week";
  groups: DigestGroup[];
  total_items: number;
}

export type StateFilter = "inbox" | "unread" | "read" | "saved" | "hidden" | "all";

export type BulkAction = "read" | "unread" | "save" | "unsave" | "hide" | "unhide";

export type View =
  | { kind: "inbox" }
  | { kind: "alert"; alertId: number }
  | { kind: "saved" }
  | { kind: "hidden" }
  | { kind: "digest"; window: "today" | "week" };
