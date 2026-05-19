import { Bookmark, BookmarkCheck, Check, ExternalLink, EyeOff } from "lucide-react";
import type { Item } from "../types";
import type { ViewMode } from "../hooks/useViewMode";
import { classNames, timeAgo } from "../lib/format";

interface Props {
  item: Item;
  mode: ViewMode;
  onToggleRead: (item: Item) => void;
  onToggleSaved: (item: Item) => void;
  onToggleHidden: (item: Item) => void;
  onOpen: (item: Item) => void;
}

export function ItemCard({ item, mode, onToggleRead, onToggleSaved, onToggleHidden, onOpen }: Props) {
  const isRead = !!item.state?.read_at;
  const isSaved = !!item.state?.saved_at;
  const isHidden = !!item.state?.hidden_at;

  if (mode === "text") {
    return (
      <a
        href={item.link}
        target="_blank"
        rel="noreferrer noopener"
        onClick={() => onOpen(item)}
        className={classNames(
          "group flex items-baseline gap-2 px-2 py-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-900 text-sm",
          isRead && "text-zinc-500",
        )}
      >
        <span className="text-xs text-zinc-500 tabular-nums shrink-0 w-12">
          {timeAgo(item.published_at).replace(" ago", "")}
        </span>
        <span className="text-xs text-zinc-500 shrink-0 truncate w-32" title={item.source_domain}>
          {item.source_domain}
        </span>
        <span className="text-xs text-zinc-600 dark:text-zinc-400 shrink-0 truncate w-32" title={item.alert_name}>
          {item.alert_icon} {item.alert_name}
        </span>
        <span className={classNames("flex-1 truncate", !isRead && "font-medium")}>
          {item.title}
        </span>
      </a>
    );
  }

  if (mode === "list") {
    return (
      <div
        className={classNames(
          "group flex items-center gap-3 px-3 py-2 rounded-lg border transition-colors",
          "border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900",
          "hover:border-zinc-300 dark:hover:border-zinc-700",
          isRead && "opacity-60",
        )}
      >
        <div className="flex-1 min-w-0 cursor-pointer" onClick={() => onOpen(item)}>
          <div className="flex items-center gap-2 text-xs text-zinc-500 mb-0.5">
            <span className="font-medium text-zinc-700 dark:text-zinc-300 truncate">
              {item.alert_icon} {item.alert_name}
            </span>
            <span>·</span>
            <span className="truncate">{item.source_domain}</span>
            <span>·</span>
            <span title={item.published_at}>{timeAgo(item.published_at)}</span>
          </div>
          <h3 className={classNames(
            "font-medium text-sm leading-snug truncate hover:text-brand-600 dark:hover:text-brand-400",
            !isRead && "text-zinc-900 dark:text-zinc-50",
          )}>
            {item.title}
          </h3>
        </div>
        <Actions
          item={item}
          isRead={isRead}
          isSaved={isSaved}
          isHidden={isHidden}
          onOpen={onOpen}
          onToggleRead={onToggleRead}
          onToggleSaved={onToggleSaved}
          onToggleHidden={onToggleHidden}
          dense
        />
      </div>
    );
  }

  // Compact: one-line snippet, smaller card
  if (mode === "compact") {
    return (
      <article
        className={classNames(
          "group p-3 rounded-lg border transition-colors",
          "border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900",
          "hover:border-zinc-300 dark:hover:border-zinc-700",
          isRead && "opacity-60",
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 text-xs text-zinc-500 mb-0.5">
              <span className="font-medium text-zinc-700 dark:text-zinc-300 truncate">
                {item.alert_icon} {item.alert_name}
              </span>
              <span>·</span>
              <span className="truncate">{item.source_domain}</span>
              <span>·</span>
              <span title={item.published_at}>{timeAgo(item.published_at)}</span>
            </div>
            <h3
              className={classNames(
                "font-semibold text-sm leading-snug line-clamp-2 cursor-pointer hover:text-brand-600 dark:hover:text-brand-400",
                !isRead && "text-zinc-900 dark:text-zinc-50",
              )}
              onClick={() => onOpen(item)}
            >
              {item.title}
            </h3>
            {item.snippet && (
              <p className="text-xs text-zinc-600 dark:text-zinc-400 line-clamp-1 mt-0.5">
                {item.snippet}
              </p>
            )}
          </div>
          <Actions
            item={item}
            isRead={isRead}
            isSaved={isSaved}
            isHidden={isHidden}
            onOpen={onOpen}
            onToggleRead={onToggleRead}
            onToggleSaved={onToggleSaved}
            onToggleHidden={onToggleHidden}
            dense
          />
        </div>
      </article>
    );
  }

  // Comfortable (default)
  return (
    <article
      className={classNames(
        "group p-4 rounded-xl border transition-colors",
        "border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900",
        "hover:border-zinc-300 dark:hover:border-zinc-700 shadow-card",
        isRead && "opacity-60",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-xs text-zinc-500 mb-1">
            <span className="font-medium text-zinc-700 dark:text-zinc-300">
              {item.alert_icon} {item.alert_name}
            </span>
            <span>·</span>
            <span className="truncate">{item.source_domain}</span>
            <span>·</span>
            <span title={item.published_at}>{timeAgo(item.published_at)}</span>
          </div>
          <h3
            className={classNames(
              "font-semibold text-base leading-snug line-clamp-2 mb-1.5 cursor-pointer hover:text-brand-600 dark:hover:text-brand-400",
              !isRead && "text-zinc-900 dark:text-zinc-50",
            )}
            onClick={() => onOpen(item)}
          >
            {item.title}
          </h3>
          {item.snippet && (
            <p className="text-sm text-zinc-600 dark:text-zinc-400 line-clamp-3">
              {item.snippet}
            </p>
          )}
        </div>
        <Actions
          item={item}
          isRead={isRead}
          isSaved={isSaved}
          isHidden={isHidden}
          onOpen={onOpen}
          onToggleRead={onToggleRead}
          onToggleSaved={onToggleSaved}
          onToggleHidden={onToggleHidden}
        />
      </div>
    </article>
  );
}

function Actions({
  item, isRead, isSaved, isHidden,
  onOpen, onToggleRead, onToggleSaved, onToggleHidden,
  dense = false,
}: {
  item: Item;
  isRead: boolean;
  isSaved: boolean;
  isHidden: boolean;
  onOpen: (i: Item) => void;
  onToggleRead: (i: Item) => void;
  onToggleSaved: (i: Item) => void;
  onToggleHidden: (i: Item) => void;
  dense?: boolean;
}) {
  const size = dense ? 14 : 16;
  const pad = dense ? "p-1" : "p-1.5";
  const Container = dense ? "div" : "div";
  return (
    <Container className={classNames("flex shrink-0 gap-0.5", dense ? "items-center" : "flex-col gap-1")}>
      <a
        href={item.link}
        target="_blank"
        rel="noreferrer noopener"
        onClick={() => onOpen(item)}
        className={classNames(pad, "rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-brand-600")}
        title="Open in new tab"
      >
        <ExternalLink size={size} />
      </a>
      <button
        onClick={() => onToggleRead(item)}
        className={classNames(
          pad, "rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800",
          isRead ? "text-brand-600 dark:text-brand-400" : "text-zinc-500",
        )}
        title={isRead ? "Mark unread" : "Mark read"}
      >
        <Check size={size} />
      </button>
      <button
        onClick={() => onToggleSaved(item)}
        className={classNames(
          pad, "rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800",
          isSaved ? "text-amber-500" : "text-zinc-500",
        )}
        title={isSaved ? "Unsave" : "Save"}
      >
        {isSaved ? <BookmarkCheck size={size} /> : <Bookmark size={size} />}
      </button>
      <button
        onClick={() => onToggleHidden(item)}
        className={classNames(
          pad, "rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800",
          isHidden ? "text-zinc-400" : "text-zinc-500",
        )}
        title={isHidden ? "Unhide" : "Hide"}
      >
        <EyeOff size={size} />
      </button>
    </Container>
  );
}
