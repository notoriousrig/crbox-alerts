import { X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import type { Alert } from "../types";

interface Props {
  open: boolean;
  initial?: Alert | null;
  onClose: () => void;
  onSubmit: (data: {
    name: string;
    description: string;
    feed_url: string;
    color: string;
    icon: string;
  }) => Promise<void>;
  onDelete?: (a: Alert) => Promise<void>;
  error: string | null;
}

export function AlertModal({ open, initial, onClose, onSubmit, onDelete, error }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [feedUrl, setFeedUrl] = useState("");
  const [icon, setIcon] = useState("🔔");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(initial?.name ?? "");
    setDescription(initial?.description ?? "");
    setFeedUrl(initial?.feed_url ?? "");
    setIcon(initial?.icon ?? "🔔");
    setSubmitting(false);
  }, [open, initial]);

  if (!open) return null;

  const submit = async () => {
    setSubmitting(true);
    try {
      await onSubmit({ name, description, feed_url: feedUrl, color: "brand", icon });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-40 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white dark:bg-zinc-900 rounded-2xl shadow-modal w-full max-w-lg p-5 border border-zinc-200 dark:border-zinc-800"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-lg">
            {initial ? "Edit alert" : "Add Google Alert"}
          </h2>
          <button onClick={onClose} className="p-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800">
            <X size={18} />
          </button>
        </div>

        {!initial && (
          <p className="text-sm text-zinc-500 mb-4">
            In <a href="https://www.google.com/alerts" target="_blank" rel="noreferrer" className="underline">Google Alerts</a>,
            click the pencil on an alert → "Show options" → set
            <span className="font-medium"> Deliver to: RSS feed</span> → save → copy the RSS feed URL and paste it below.
          </p>
        )}

        <div className="space-y-3">
          <Field label="Name">
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. AI regulation"
              className="w-full px-3 py-2 rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950"
            />
          </Field>
          <Field label="Feed URL">
            <input
              value={feedUrl}
              onChange={(e) => setFeedUrl(e.target.value)}
              placeholder="https://www.google.com/alerts/feeds/…"
              className="w-full px-3 py-2 rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 font-mono text-xs"
            />
          </Field>
          <Field label="Icon (emoji, optional)">
            <input
              value={icon}
              onChange={(e) => setIcon(e.target.value)}
              maxLength={4}
              className="w-20 px-3 py-2 rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 text-center"
            />
          </Field>
          <Field label="Description (optional)">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950"
            />
          </Field>
        </div>

        {error && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
        )}

        <div className="flex items-center justify-between mt-5">
          {initial && onDelete && (
            <button
              onClick={() => onDelete(initial)}
              className="text-sm text-red-600 hover:underline"
            >
              Delete
            </button>
          )}
          <div className="ml-auto flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded-md text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={!name.trim() || !feedUrl.trim() || submitting}
              className="px-3 py-1.5 rounded-md text-sm bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {submitting ? "Saving…" : initial ? "Save" : "Add alert"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-zinc-500 mb-1 block">{label}</span>
      {children}
    </label>
  );
}
