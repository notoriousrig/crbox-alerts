import type { ReactNode } from "react";
import { Bell, BellOff, BookmarkCheck, Calendar, CalendarDays, Inbox, Pencil, Plus } from "lucide-react";
import type { Alert, View } from "../types";
import { classNames } from "../lib/format";

interface Props {
  alerts: Alert[];
  view: View;
  onSelectView: (v: View) => void;
  onAddAlert: () => void;
  onEditAlert: (a: Alert) => void;
  totalUnread: number;
}

export function Sidebar({ alerts, view, onSelectView, onAddAlert, onEditAlert, totalUnread }: Props) {
  return (
    <aside className="w-72 shrink-0 border-r border-zinc-200 dark:border-zinc-800 flex flex-col h-full overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 flex items-center gap-2">
        <span className="text-2xl">🔔</span>
        <h1 className="font-semibold text-lg">crbox-alerts</h1>
      </div>

      <nav className="flex-1 overflow-y-auto scrollbar-thin px-2 py-3">
        <SectionLabel>Views</SectionLabel>
        <NavRow
          icon={<Inbox size={16} />}
          label="Inbox"
          active={view.kind === "inbox"}
          onClick={() => onSelectView({ kind: "inbox" })}
          badge={totalUnread}
        />
        <NavRow
          icon={<Calendar size={16} />}
          label="Today"
          active={view.kind === "digest" && view.window === "today"}
          onClick={() => onSelectView({ kind: "digest", window: "today" })}
        />
        <NavRow
          icon={<CalendarDays size={16} />}
          label="This week"
          active={view.kind === "digest" && view.window === "week"}
          onClick={() => onSelectView({ kind: "digest", window: "week" })}
        />
        <NavRow
          icon={<BookmarkCheck size={16} />}
          label="Saved"
          active={view.kind === "saved"}
          onClick={() => onSelectView({ kind: "saved" })}
        />
        <NavRow
          icon={<BellOff size={16} />}
          label="Hidden"
          active={view.kind === "hidden"}
          onClick={() => onSelectView({ kind: "hidden" })}
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
            No alerts yet. Add one with the + button.
          </p>
        )}

        {alerts.map((a) => (
          <div key={a.id} className="group flex items-stretch">
            <button
              onClick={() => onSelectView({ kind: "alert", alertId: a.id })}
              className={classNames(
                "flex-1 flex items-center gap-2 px-2 py-1.5 rounded-md text-sm text-left",
                view.kind === "alert" && view.alertId === a.id
                  ? "bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-200"
                  : "hover:bg-zinc-100 dark:hover:bg-zinc-800",
              )}
            >
              <span className="text-base leading-none w-4 text-center">{a.icon || <Bell size={14} />}</span>
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
      </nav>
    </aside>
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
