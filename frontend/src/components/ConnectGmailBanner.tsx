import { Mail, Loader2 } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../api";
import { timeAgo } from "../lib/format";

export function ConnectGmailBanner() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const statusQ = useQuery({
    queryKey: ["google", "status"],
    queryFn: api.googleStatus,
    refetchInterval: 60_000,
  });

  const connect = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const { authorization_url } = await api.googleStart(window.location.pathname);
      window.location.href = authorization_url;
    } catch (e) {
      setError((e as Error).message);
      setSubmitting(false);
    }
  };

  const disconnect = async () => {
    if (!window.confirm("Disconnect Gmail? Items already in the app stay; new polls will stop until you reconnect.")) return;
    setSubmitting(true);
    try {
      await api.googleDisconnect();
      await statusQ.refetch();
    } finally {
      setSubmitting(false);
    }
  };

  if (statusQ.isLoading) return null;
  const s = statusQ.data;

  if (!s?.connected) {
    return (
      <div className="mx-6 mt-4 p-4 rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30">
        <div className="flex items-start gap-3">
          <Mail className="text-amber-600 dark:text-amber-400 mt-0.5" size={20} />
          <div className="flex-1">
            <h3 className="font-semibold text-amber-900 dark:text-amber-100">
              Connect Gmail to start receiving alerts
            </h3>
            <p className="text-sm text-amber-800 dark:text-amber-200 mt-1">
              crbox-alerts reads your Google Alerts emails directly from Gmail
              (read-only). Click below to authorize, then create alerts with
              names matching your Google Alert queries.
            </p>
            {error && (
              <p className="text-sm text-red-600 dark:text-red-400 mt-2">{error}</p>
            )}
            <button
              onClick={connect}
              disabled={submitting}
              className="mt-3 px-3 py-1.5 rounded-md text-sm font-medium bg-amber-600 hover:bg-amber-700 text-white disabled:opacity-50 inline-flex items-center gap-2"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              Connect Gmail
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-6 mt-4 px-4 py-2 rounded-xl border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 flex items-center gap-3 text-sm">
      <Mail className="text-emerald-600 dark:text-emerald-400" size={16} />
      <span className="text-emerald-900 dark:text-emerald-100 flex-1">
        Connected as <span className="font-medium">{s.email || "Gmail"}</span>
        {s.last_polled_at && (
          <span className="text-emerald-700 dark:text-emerald-300 ml-2">
            · last poll {timeAgo(s.last_polled_at)}
          </span>
        )}
      </span>
      <button
        onClick={disconnect}
        disabled={submitting}
        className="text-xs text-emerald-700 dark:text-emerald-300 hover:underline disabled:opacity-50"
      >
        Disconnect
      </button>
    </div>
  );
}
