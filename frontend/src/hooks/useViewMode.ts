import { useEffect, useState } from "react";

export type ViewMode = "comfortable" | "compact" | "list" | "text";

const STORAGE_KEY = "crbox-alerts:viewmode";
const ORDER: ViewMode[] = ["comfortable", "compact", "list", "text"];

function detectInitial(): ViewMode {
  if (typeof window === "undefined") return "comfortable";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (ORDER.includes(stored as ViewMode)) return stored as ViewMode;
  return "comfortable";
}

export function useViewMode() {
  const [mode, setMode] = useState<ViewMode>(detectInitial);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, mode);
  }, [mode]);

  const cycle = () => {
    setMode((m) => ORDER[(ORDER.indexOf(m) + 1) % ORDER.length]);
  };

  return { mode, setMode, cycle };
}
