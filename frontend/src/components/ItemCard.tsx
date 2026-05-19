import { Bookmark, BookmarkCheck, Check, ExternalLink, EyeOff } from "lucide-react";
import type { Item } from "../types";
import { classNames, timeAgo } from "../lib/format";

interface Props {
  item: Item;
  onToggleRead: (item: Item) => void;
  onToggleSaved: (item: Item) => void;
  onToggleHidden: (item: Item) => void;
  onOpen: (item: Item) => void;
}

export function ItemCard({ item, onToggleRead, onToggleSaved, onToggleHidden, onOpen }: Props) {
  const isRead = !!item.state?.read_at;
  const isSaved = !!item.state?.saved_at;
  const isHidden = !!item.state?.hidden_at;

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

        <div className="flex flex-col gap-1 shrink-0">
          <a
            href={item.link}
            target="_blank"
            rel="noreferrer noopener"
            onClick={() => onOpen(item)}
            className="p-1.5 rounded-md text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-brand-600"
            title="Open in new tab"
          >
            <ExternalLink size={16} />
          </a>
          <button
            onClick={() => onToggleRead(item)}
            className={classNames(
              "p-1.5 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800",
              isRead ? "text-brand-600 dark:text-brand-400" : "text-zinc-500",
            )}
            title={isRead ? "Mark unread" : "Mark read"}
          >
            <Check size={16} />
          </button>
          <button
            onClick={() => onToggleSaved(item)}
            className={classNames(
              "p-1.5 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800",
              isSaved ? "text-amber-500" : "text-zinc-500",
            )}
            title={isSaved ? "Unsave" : "Save"}
          >
            {isSaved ? <BookmarkCheck size={16} /> : <Bookmark size={16} />}
          </button>
          <button
            onClick={() => onToggleHidden(item)}
            className={classNames(
              "p-1.5 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800",
              isHidden ? "text-zinc-400" : "text-zinc-500",
            )}
            title={isHidden ? "Unhide" : "Hide"}
          >
            <EyeOff size={16} />
          </button>
        </div>
      </div>
    </article>
  );
}
