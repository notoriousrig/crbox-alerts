import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { api } from "./api";
import type { Alert, Item, StateFilter, View } from "./types";
import { Sidebar } from "./components/Sidebar";
import { ItemList } from "./components/ItemList";
import { DigestView } from "./components/DigestView";
import { AlertModal } from "./components/AlertModal";
import { ConnectGmailBanner } from "./components/ConnectGmailBanner";
import { ThemeToggle } from "./components/ThemeToggle";

export default function App() {
  const qc = useQueryClient();
  const [view, setView] = useState<View>({ kind: "inbox" });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Alert | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);

  const alertsQ = useQuery({
    queryKey: ["alerts"],
    queryFn: api.listAlerts,
  });

  const itemsParams = useMemo(() => {
    if (view.kind === "alert") return { alert_id: view.alertId, state: "inbox" as StateFilter };
    if (view.kind === "saved") return { state: "saved" as StateFilter };
    if (view.kind === "hidden") return { state: "hidden" as StateFilter };
    return { state: "inbox" as StateFilter };
  }, [view]);

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
        <header className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center gap-2 sticky top-0 bg-zinc-50/80 dark:bg-zinc-950/80 backdrop-blur z-10">
          <h1 className="text-xl font-semibold flex-1">{currentTitle}</h1>
          <button
            onClick={() => pollAllMut.mutate()}
            disabled={pollAllMut.isPending}
            className="p-2 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500 disabled:opacity-50"
            title="Poll Gmail now"
          >
            <RefreshCw size={18} className={pollAllMut.isPending ? "animate-spin" : ""} />
          </button>
          <ThemeToggle />
        </header>

        <ConnectGmailBanner />

        <div className="p-6 max-w-3xl mx-auto">
          {view.kind === "digest" ? (
            <DigestView
              digest={digestQ.data}
              isLoading={digestQ.isLoading}
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
              emptyMessage={
                view.kind === "saved"
                  ? "No saved items yet."
                  : view.kind === "hidden"
                  ? "No hidden items."
                  : (alertsQ.data ?? []).length === 0
                  ? "Add your first Google Alert with the + button on the left."
                  : "Nothing here. Try the refresh button above."
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
