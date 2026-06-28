/**
 * Pure draft helpers — no imports, no side effects — so they can be unit-tested
 * in isolation (e.g. under Bun) without a running Supabase backend.
 */

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/**
 * Default title for an auto-saved draft: document label + date and time, so
 * repeated drafts of the same type stay distinguishable in the history list.
 * e.g. "General Affidavit · 28 Jun 2026, 14:30".
 */
export function formatDraftTitle(label: string, date: Date = new Date()): string {
  const day = date.getDate();
  const month = MONTHS[date.getMonth()];
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${label} · ${day} ${month} ${year}, ${hours}:${minutes}`;
}

export interface DraftLike {
  title: string;
  doc_type_label: string;
}

/**
 * Case-insensitive filter over a draft's title or document-type label. An empty
 * (or whitespace-only) query returns the list unchanged.
 */
export function filterDrafts<T extends DraftLike>(drafts: T[], query: string): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return drafts;
  return drafts.filter(
    (d) =>
      d.title.toLowerCase().includes(q) ||
      d.doc_type_label.toLowerCase().includes(q)
  );
}

/** Trigger a browser download of `text` as a `.txt` file named from `title`. */
export function downloadTextFile(title: string, text: string): void {
  const safeName =
    title
      .trim()
      .replace(/[^a-z0-9]+/gi, "_")
      .replace(/^_+|_+$/g, "")
      .toLowerCase() || "document";
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${safeName}.txt`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
