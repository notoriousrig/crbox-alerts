import { CheckCheck, Loader2 } from "lucide-react";
import type { Digest, Item } from "../types";
import type { ViewMode } from "../hooks/useViewMode";
import { ItemCard } from "./ItemCard";

interface Props {
  digest: Digest | undefined;
  isLoading: boolean;
  mode: ViewMode;
  onToggleRead: (item: Item) => void;
  onToggleSaved: (item: Item) => void;
  onToggleHidden: (item: Item) => void;
  onOpen: (item: Item) => void;
  onMarkGroupRead: (alertId: number, items: Item[]) => void;
}

export function DigestView({
  digest, isLoading, mode,
  onToggleRead, onToggleSaved, onToggleHidden, onOpen, onMarkGroupRead,
}: Props) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-zinc-500">
        <Loader2 className="animate-spin mr-2" size={18} /> Loading…
      </div>
    );
  }
  if (!digest || digest.total_items === 0) {
    return (
      <div className="text-center text-zinc-500 py-16">
        <p>Nothing new in this window.</p>
      </div>
    );
  }

  const gap = mode === "text" ? "gap-0.5" : mode === "list" ? "gap-1.5" : mode === "compact" ? "gap-2" : "gap-3";

  return (
    <div className="flex flex-col gap-8">
      {digest.groups.map((group) => (
        <section key={group.alert.id}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-lg">
              <span className="mr-2">{group.alert.icon}</span>
              {group.alert.name}
              <span className="ml-2 text-sm font-normal text-zinc-500">
                {group.items.length} {group.items.length === 1 ? "item" : "items"}
              </span>
            </h2>
            <button
              onClick={() => onMarkGroupRead(group.alert.id, group.items)}
              className="text-sm flex items-center gap-1 text-zinc-500 hover:text-brand-600 dark:hover:text-brand-400"
              title="Mark all read in this group"
            >
              <CheckCheck size={14} /> Mark all read
            </button>
          </div>
          <div className={`flex flex-col ${gap}`}>
            {group.items.map((it) => (
              <ItemCard
                key={it.id}
                item={it}
                mode={mode}
                onToggleRead={onToggleRead}
                onToggleSaved={onToggleSaved}
                onToggleHidden={onToggleHidden}
                onOpen={onOpen}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
