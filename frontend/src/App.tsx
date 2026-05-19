import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { api } from "./api";
import type { Alert, Item, SortMode, StateFilter, TimeWindow, View } from "./types";
import { Sidebar } from "./components/Sidebar";
import { ItemList } from "./components/ItemList";
import { DigestView } from "./components/DigestView";
import { AlertModal } from "./components/AlertModal";
import { ConnectGmailBanner } from "./components/ConnectGmailBanner";
import { ThemeToggle } from "./components/ThemeToggle";
import { ViewModeToggle } from "./components/ViewModeToggle";
import { useViewMode } from "./hooks/useViewMode";

const TIME_WINDOWS: { id: TimeWindow; label: string; hours: number | null }[] = [
  { id: "all", label: "All time", hours: null },
  { id: "today", label: "Today", hours: 24 },
  { id: "week", label: "This week", hours: 24 * 7 },
  { id: "month", label: "This month", hours: 24 * 30 },
];

const SORT_OPTIONS: { id: SortMode; label: string }[] = [
  { id: "newest", label: "Newest first" },
  { id: "oldest", label: "Oldest first" },
  { id: "source", label: "By source" },
];

export default function App() {
  const qc = useQueryClient();
  const [view, setView] = useState<View>({ kind: "inbox" });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Alert | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);
  const [timeWindow, setTimeWindow] = useState<TimeWindow>("all");
  const [sortMode, setSortMode] = useState<SortMode>("newest");
  const { mode: viewMode, setMode: setViewMode, cycle: cycleViewMode } = useViewMode();

  // Keyboard: `v` cycles density.
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const inField = ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName ?? "");
      if (!inField && e.key === "v") {
        e.preventDefault();
        cycleViewMode();
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [cycleViewMode]);

  const alertsQ = useQuery({
    queryKey: ["alerts"],
    queryFn: api.listAlerts,
  });

  const googleQ = useQuery({
    queryKey: ["google", "status"],
    queryFn: api.googleStatus,
  });

  const itemsParams = useMemo(() => {
    const hours = TIME_WINDOWS.find((t) => t.id === timeWindow)?.hours ?? null;
    const base: {
      alert_id?: number;
      state: StateFilter;
      sort: SortMode;
      since_hours?: number;
      limit: number;
    } = {
      state: "inbox",
      sort: sortMode,
      limit: 500,
    };
    if (hours !== null) base.since_hours = hours;
    if (view.kind === "alert") return { ...base, alert_id: view.alertId };
    if (view.kind === "saved") return { ...base, state: "saved" as StateFilter };
    if (view.kind === "hidden") return { ...base, state: "hidden" as StateFilter };
    return base;
  }, [view, timeWindow, sortMode]);

  const itemsQ = useQuery({
    queryKey: ["items", itemsParams],
    queryFn: () => api.listItems(itemsParams),
    enabled: view.kind !== "digest",
  });

  const digestQ = useQuery({
    queryKey: ["digest", view.kind === "digest" ? view.window : null],
    queryFn: () =>
      view.kind === "digest" && view.window === "today"
        ? api.digestToday()
        : api.digestWeek(),
    enabled: view.kind === "digest",
  });

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["alerts"] });
    qc.invalidateQueries({ queryKey: ["items"] });
    qc.invalidateQueries({ queryKey: ["digest"] });
  };

  const stateMut = useMutation({
    mutationFn: (args: { id: string; data: { read?: boolean; saved?: boolean; hidden?: boolean } }) =>
      api.patchItemState(args.id, args.data),
    onSuccess: invalidateAll,
  });

  const bulkMut = useMutation({
    mutationFn: (args: { ids: string[]; action: "read" | "unread" | "save" | "unsave" | "hide" | "unhide" }) =>
      api.bulkState(args.ids, args.action),
    onSuccess: invalidateAll,
  });

  const pollAllMut = useMutation({
    mutationFn: () => api.pollNow(),
    onSuccess: invalidateAll,
  });

  const upsertMut = useMutation({
    mutationFn: async (data: {
      name: string;
      description: string;
      subject_match: string;
      color: string;
      icon: string;
    }) => {
      if (editing) return api.updateAlert(editing.id, data);
      return api.createAlert(data);
    },
    onSuccess: () => {
      invalidateAll();
      setModalOpen(false);
      setEditing(null);
      setModalError(null);
    },
    onError: (e: Error) => setModalError(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (a: Alert) => api.deleteAlert(a.id),
    onSuccess: () => {
      invalidateAll();
      setModalOpen(false);
      setEditing(null);
      if (view.kind === "alert") setView({ kind: "inbox" });
    },
  });

  const totalUnread = useMemo(
    () => (alertsQ.data ?? []).reduce((acc, a) => acc + a.unread_count, 0),
    [alertsQ.data],
  );

  const knownCategories = useMemo(() => {
    const set = new Set<string>();
    for (const a of alertsQ.data ?? []) {
      const c = (a.category || "").trim();
      if (c) set.add(c);
    }
    return [...set].sort();
  }, [alertsQ.data]);

  const handleOpen = (it: Item) => {
    if (!it.state?.read_at) {
      stateMut.mutate({ id: it.id, data: { read: true } });
    }
  };
  const handleToggleRead = (it: Item) =>
    stateMut.mutate({ id: it.id, data: { read: !it.state?.read_at } });
  const handleToggleSaved = (it: Item) =>
    stateMut.mutate({ id: it.id, data: { saved: !it.state?.saved_at } });
  const handleToggleHidden = (it: Item) =>
    stateMut.mutate({ id: it.id, data: { hidden: !it.state?.hidden_at } });

  const currentTitle = (() => {
    if (view.kind === "inbox") return "Inbox";
    if (view.kind === "saved") return "Saved";
    if (view.kind === "hidden") return "Hidden";
    if (view.kind === "digest") return view.window === "today" ? "Today" : "This week";
    const a = (alertsQ.data ?? []).find((x) => x.id === view.alertId);
    return a?.name ?? "Alert";
  })();

  return (
    <div className="h-full flex bg-zinc-50 dark:bg-zinc-950">
      <Sidebar
        alerts={alertsQ.data ?? []}
        view={view}
        onSelectView={setView}
        onAddAlert={() => {
          setEditing(null);
          setModalError(null);
          setModalOpen(true);
        }}
        onEditAlert={(a) => {
          setEditing(a);
          setModalError(null);
          setModalOpen(true);
        }}
        totalUnread={totalUnread}
      />

      <main className="flex-1 overflow-y-auto scrollbar-thin">
        <header className="px-6 py-3 border-b border-zinc-200 dark:border-zinc-800 sticky top-0 bg-zinc-50/80 dark:bg-zinc-950/80 backdrop-blur z-10">
          <div className="flex items-center gap-2 mb-2">
            <h1 className="text-xl font-semibold flex-1">{currentTitle}</h1>
            <ViewModeToggle mode={viewMode} onChange={setViewMode} />
            <button
              onClick={() => pollAllMut.mutate()}
              disabled={pollAllMut.isPending}
              className="p-2 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500 disabled:opacity-50"
              title="Poll Gmail now"
            >
              <RefreshCw size={18} className={pollAllMut.isPending ? "animate-spin" : ""} />
            </button>
            <ThemeToggle />
          </div>
          {view.kind !== "digest" && (
            <div className="flex items-center gap-3 text-sm">
              <label className="flex items-center gap-1.5 text-zinc-500">
                <span className="text-xs">Window</span>
                <select
                  value={timeWindow}
                  onChange={(e) => setTimeWindow(e.target.value as TimeWindow)}
                  className="bg-transparent border border-zinc-300 dark:border-zinc-700 rounded-md px-2 py-1 text-sm"
                >
                  {TIME_WINDOWS.map((t) => (
                    <option key={t.id} value={t.id}>{t.label}</option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-1.5 text-zinc-500">
                <span className="text-xs">Sort</span>
                <select
                  value={sortMode}
                  onChange={(e) => setSortMode(e.target.value as SortMode)}
                  className="bg-transparent border border-zinc-300 dark:border-zinc-700 rounded-md px-2 py-1 text-sm"
                >
                  {SORT_OPTIONS.map((s) => (
                    <option key={s.id} value={s.id}>{s.label}</option>
                  ))}
                </select>
              </label>
              <span className="ml-auto text-xs text-zinc-500">
                {itemsQ.data ? `${itemsQ.data.length} item${itemsQ.data.length === 1 ? "" : "s"}` : ""}
              </span>
            </div>
          )}
        </header>

        <ConnectGmailBanner />

        <div className={viewMode === "text" ? "px-6 py-4 max-w-5xl mx-auto" : "p-6 max-w-3xl mx-auto"}>
          {view.kind === "digest" ? (
            <DigestView
              digest={digestQ.data}
              isLoading={digestQ.isLoading}
              mode={viewMode}
              onToggleRead={handleToggleRead}
              onToggleSaved={handleToggleSaved}
              onToggleHidden={handleToggleHidden}
              onOpen={handleOpen}
              onMarkGroupRead={(_aid, items) =>
                bulkMut.mutate({ ids: items.map((i) => i.id), action: "read" })
              }
            />
          ) : (
            <ItemList
              items={itemsQ.data}
              isLoading={itemsQ.isLoading}
              mode={viewMode}
              emptyMessage={
                view.kind === "saved"
                  ? "No saved items yet."
                  : view.kind === "hidden"
                  ? "No hidden items."
                  : !googleQ.data?.connected
                  ? "Connect Gmail above to start receiving alerts."
                  : (alertsQ.data ?? []).length === 0
                  ? "Waiting for Google Alerts emails. Alert buckets will appear here automatically once one of your Google Alert digests lands in Gmail (hit the refresh button above to poll now)."
                  : "Nothing new. Hit the refresh button above to poll Gmail."
              }
              onToggleRead={handleToggleRead}
              onToggleSaved={handleToggleSaved}
              onToggleHidden={handleToggleHidden}
              onOpen={handleOpen}
            />
          )}
        </div>
      </main>

      <AlertModal
        open={modalOpen}
        initial={editing}
        knownCategories={knownCategories}
        onClose={() => {
          setModalOpen(false);
          setEditing(null);
          setModalError(null);
        }}
        onSubmit={(data) => upsertMut.mutateAsync(data).then(() => {})}
        onDelete={async (a) => {
          if (window.confirm(`Delete "${a.name}" and all its items?`)) {
            await deleteMut.mutateAsync(a);
          }
        }}
        error={modalError}
      />
    </div>
  );
}
