import { Loader2 } from "lucide-react";
import type { Item } from "../types";
import type { ViewMode } from "../hooks/useViewMode";
import { ItemCard } from "./ItemCard";

interface Props {
  items: Item[] | undefined;
  isLoading: boolean;
  mode: ViewMode;
  emptyMessage: string;
  onToggleRead: (item: Item) => void;
  onToggleSaved: (item: Item) => void;
  onToggleHidden: (item: Item) => void;
  onOpen: (item: Item) => void;
}

export function ItemList({
  items, isLoading, mode, emptyMessage,
  onToggleRead, onToggleSaved, onToggleHidden, onOpen,
}: Props) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-zinc-500">
        <Loader2 className="animate-spin mr-2" size={18} /> Loading…
      </div>
    );
  }
  if (!items || items.length === 0) {
    return (
      <div className="text-center text-zinc-500 py-16">
        <p>{emptyMessage}</p>
      </div>
    );
  }
  const gap = mode === "text" ? "gap-0.5" : mode === "list" ? "gap-1.5" : mode === "compact" ? "gap-2" : "gap-3";
  return (
    <div className={`flex flex-col ${gap}`}>
      {items.map((it) => (
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
  );
}
