import { AlignJustify, LayoutGrid, List, Rows3 } from "lucide-react";
import type { ViewMode } from "../hooks/useViewMode";

interface Props {
  mode: ViewMode;
  onChange: (m: ViewMode) => void;
}

const OPTIONS: { id: ViewMode; icon: typeof LayoutGrid; label: string }[] = [
  { id: "comfortable", icon: LayoutGrid, label: "Comfortable" },
  { id: "compact", icon: Rows3, label: "Compact" },
  { id: "list", icon: List, label: "List" },
  { id: "text", icon: AlignJustify, label: "Text only" },
];

export function ViewModeToggle({ mode, onChange }: Props) {
  return (
    <div className="flex items-center rounded-lg bg-zinc-200/60 dark:bg-zinc-800/60 p-0.5">
      {OPTIONS.map(({ id, icon: Icon, label }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`p-1.5 rounded-md transition ${
            mode === id
              ? "bg-white dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 shadow-sm"
              : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
          }`}
          title={`${label} view (v to cycle)`}
        >
          <Icon size={16} />
        </button>
      ))}
    </div>
  );
}
