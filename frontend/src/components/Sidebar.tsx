import type { ReactNode } from "react";
import { useState } from "react";
import {
  Bell, BellOff, BookmarkCheck, Calendar, CalendarDays,
  ChevronDown, ChevronRight, Inbox, Pencil, Plus, X,
} from "lucide-react";
import type { Alert, View } from "../types";
import { classNames } from "../lib/format";

interface Props {
  alerts: Alert[];
  view: View;
  onSelectView: (v: View) => void;
  onAddAlert: () => void;
  onEditAlert: (a: Alert) => void;
  totalUnread: number;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

const COLLAPSED_KEY = "crbox-alerts:collapsed-categories";
const UNCATEGORIZED = "Uncategorized";

function loadCollapsed(): Set<string> {
  try {
    const raw = window.localStorage.getItem(COLLAPSED_KEY);
    if (!raw) return new Set();
    return new Set(JSON.parse(raw));
  } catch {
    return new Set();
  }
}

function saveCollapsed(s: Set<string>) {
  try {
    window.localStorage.setItem(COLLAPSED_KEY, JSON.stringify([...s]));
  } catch {
    // ignore
  }
}

function groupByCategory(alerts: Alert[]): { category: string; items: Alert[] }[] {
  const map = new Map<string, Alert[]>();
  for (const a of alerts) {
    const key = (a.category || "").trim() || UNCATEGORIZED;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(a);
  }
  return [...map.entries()]
    .map(([category, items]) => ({
      category,
      items: items.sort((x, y) =>
        x.sort_order - y.sort_order || x.name.localeCompare(y.name),
      ),
    }))
    .sort((a, b) => {
      // Uncategorized always last; otherwise alphabetical.
      if (a.category === UNCATEGORIZED) return 1;
      if (b.category === UNCATEGORIZED) return -1;
      return a.category.localeCompare(b.category);
    });
}

export function Sidebar({
  alerts, view, onSelectView, onAddAlert, onEditAlert, totalUnread,
  mobileOpen, onMobileClose,
}: Props) {
  const [collapsed, setCollapsed] = useState<Set<string>>(loadCollapsed);

  const toggleCategory = (cat: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      saveCollapsed(next);
      return next;
    });
  };

  const groups = groupByCategory(alerts);

  // On mobile, picking any view dismisses the drawer.
  const select = (v: View) => {
    onSelectView(v);
    onMobileClose();
  };

  return (
    <>
      {/* Mobile backdrop */}
      <div
        className={classNames(
          "fixed inset-0 bg-black/40 z-20 md:hidden transition-opacity",
          mobileOpen ? "opacity-100" : "opacity-0 pointer-events-none",
        )}
        onClick={onMobileClose}
      />
      <aside
        className={classNames(
          "bg-zinc-50 dark:bg-zinc-950 w-72 shrink-0 border-r border-zinc-200 dark:border-zinc-800 flex flex-col h-full overflow-hidden",
          // Desktop: normal flex child. Mobile: fixed slide-in drawer.
          "fixed top-0 bottom-0 left-0 z-30 transform transition-transform md:relative md:transform-none md:translate-x-0 md:z-auto",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 flex items-center gap-2">
          <span className="text-2xl">🔔</span>
          <h1 className="font-semibold text-lg flex-1">crbox-alerts</h1>
          <button
            onClick={onMobileClose}
            className="md:hidden p-1.5 rounded-md hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>

      <nav className="flex-1 overflow-y-auto scrollbar-thin px-2 py-3">
        <SectionLabel>Views</SectionLabel>
        <NavRow
          icon={<Inbox size={16} />}
          label="Inbox"
          active={view.kind === "inbox"}
          onClick={() => select({ kind: "inbox" })}
          badge={totalUnread}
        />
        <NavRow
          icon={<Calendar size={16} />}
          label="Today"
          active={view.kind === "digest" && view.window === "today"}
          onClick={() => select({ kind: "digest", window: "today" })}
        />
        <NavRow
          icon={<CalendarDays size={16} />}
          label="This week"
          active={view.kind === "digest" && view.window === "week"}
          onClick={() => select({ kind: "digest", window: "week" })}
        />
        <NavRow
          icon={<BookmarkCheck size={16} />}
          label="Saved"
          active={view.kind === "saved"}
          onClick={() => select({ kind: "saved" })}
        />
        <NavRow
          icon={<BellOff size={16} />}
          label="Hidden"
          active={view.kind === "hidden"}
          onClick={() => select({ kind: "hidden" })}
        />

        <div className="mt-5 flex items-center justify-between px-2 pb-1">
          <SectionLabel>Alerts</SectionLabel>
          <button
            onClick={onAddAlert}
            className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-zinc-800 text-zinc-500"
            title="Add alert"
          >
            <Plus size={14} />
          </button>
        </div>

        {alerts.length === 0 && (
          <p className="text-xs text-zinc-500 px-2 py-2">
            No alerts yet. They'll auto-appear once Gmail starts polling.
          </p>
        )}

        {groups.map((g) => {
          const isCollapsed = collapsed.has(g.category);
          const groupUnread = g.items.reduce((acc, a) => acc + a.unread_count, 0);
          return (
            <div key={g.category} className="mt-2">
              <button
                onClick={() => toggleCategory(g.category)}
                className="w-full flex items-center gap-1 px-2 py-1 text-[10px] uppercase tracking-wide font-semibold text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
              >
                {isCollapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
                <span className="flex-1 text-left truncate">{g.category}</span>
                <span className="text-[10px] text-zinc-500 tabular-nums">
                  {groupUnread > 0 ? groupUnread : g.items.length}
                </span>
              </button>

              {!isCollapsed && g.items.map((a) => (
                <div key={a.id} className="group flex items-stretch">
                  <button
                    onClick={() => select({ kind: "alert", alertId: a.id })}
                    className={classNames(
                      "flex-1 flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-left",
                      view.kind === "alert" && view.alertId === a.id
                        ? "bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-200"
                        : "hover:bg-zinc-100 dark:hover:bg-zinc-800",
                    )}
                  >
                    <span className="text-base leading-none w-4 text-center">
                      {a.icon || <Bell size={14} />}
                    </span>
                    <span className="flex-1 truncate">{a.name}</span>
                    {a.unread_count > 0 && (
                      <span className="text-xs tabular-nums px-1.5 py-0.5 rounded bg-zinc-200 dark:bg-zinc-700">
                        {a.unread_count}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => onEditAlert(a)}
                    className="px-1 opacity-0 group-hover:opacity-100 transition-opacity text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
                    title="Edit alert"
                  >
                    <Pencil size={12} />
                  </button>
                </div>
              ))}
            </div>
          );
        })}
      </nav>
      </aside>
    </>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-[10px] uppercase tracking-wide font-semibold text-zinc-500 px-2 py-1">
      {children}
    </div>
  );
}

function NavRow({
  icon, label, active, onClick, badge,
}: {
  icon: ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
  badge?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={classNames(
        "w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-sm",
        active
          ? "bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-200"
          : "hover:bg-zinc-100 dark:hover:bg-zinc-800",
      )}
    >
      <span className="text-zinc-500">{icon}</span>
      <span className="flex-1 text-left">{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="text-xs tabular-nums px-1.5 py-0.5 rounded bg-zinc-200 dark:bg-zinc-700">
          {badge}
        </span>
      )}
    </button>
  );
}
