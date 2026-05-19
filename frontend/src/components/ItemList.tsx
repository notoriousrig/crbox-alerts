import { Loader2 } from "lucide-react";
import type { Item } from "../types";
import { ItemCard } from "./ItemCard";

interface Props {
  items: Item[] | undefined;
  isLoading: boolean;
  emptyMessage: string;
  onToggleRead: (item: Item) => void;
  onToggleSaved: (item: Item) => void;
  onToggleHidden: (item: Item) => void;
  onOpen: (item: Item) => void;
}

export function ItemList({
  items, isLoading, emptyMessage,
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
  return (
    <div className="flex flex-col gap-3">
      {items.map((it) => (
        <ItemCard
          key={it.id}
          item={it}
          onToggleRead={onToggleRead}
          onToggleSaved={onToggleSaved}
          onToggleHidden={onToggleHidden}
          onOpen={onOpen}
        />
      ))}
    </div>
  );
}
