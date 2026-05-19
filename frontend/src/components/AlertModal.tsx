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
    subject_match: string;
    color: string;
    icon: string;
  }) => Promise<void>;
  onDelete?: (a: Alert) => Promise<void>;
  error: string | null;
}

export function AlertModal({ open, initial, onClose, onSubmit, onDelete, error }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [subjectMatch, setSubjectMatch] = useState("");
  const [icon, setIcon] = useState("🔔");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(initial?.name ?? "");
    setDescription(initial?.description ?? "");
    setSubjectMatch(initial?.subject_match ?? "");
    setIcon(initial?.icon ?? "🔔");
    setSubmitting(false);
  }, [open, initial]);

  if (!open) return null;

  const submit = async () => {
    setSubmitting(true);
    try {
      await onSubmit({
        name,
        description,
        subject_match: subjectMatch,
        color: "brand",
        icon,
      });
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
            Name this alert to match the search query you set up in{" "}
            <a href="https://www.google.com/alerts" target="_blank" rel="noreferrer" className="underline">
              Google Alerts
            </a>
            . crbox-alerts buckets incoming emails by matching this name (or the
            optional Subject match override) against each email's Subject line.
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
          <Field
            label="Subject match (optional)"
            hint="Substring to match against the email Subject line. Defaults to the name above. Useful if your Google Alert query contains punctuation."
          >
            <input
              value={subjectMatch}
              onChange={(e) => setSubjectMatch(e.target.value)}
              placeholder={name || "leave blank to use the name"}
              className="w-full px-3 py-2 rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950"
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
              disabled={!name.trim() || submitting}
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

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-zinc-500 mb-1 block">{label}</span>
      {children}
      {hint && <span className="text-xs text-zinc-500 mt-1 block">{hint}</span>}
    </label>
  );
}
