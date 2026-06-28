"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUp,
  Check,
  Copy,
  Download,
  FileText,
  Loader2,
  LogOut,
  Menu,
  MoreVertical,
  Pencil,
  Plus,
  Scale,
  Search,
  Trash2,
  X,
} from "lucide-react";

import { DOC_TYPES } from "@/lib/documents";
import { cn } from "@/lib/utils";
import {
  createDraft,
  deleteDraft,
  listDrafts,
  renameDraft,
  type Draft,
} from "@/lib/drafts";
import {
  downloadTextFile,
  filterDrafts,
  formatDraftTitle,
} from "@/lib/draft-utils";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export default function Home() {
  const router = useRouter();
  const { session, user, loading: authLoading, signOut } = useAuth();
  const userId = user?.id;

  // Drafting state.
  const [docType, setDocType] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // History state.
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [draftsLoading, setDraftsLoading] = useState(true);
  const [draftsError, setDraftsError] = useState<string | null>(null);
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  // UI state.
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<Draft | null>(null);

  const selected = useMemo(
    () => DOC_TYPES.find((doc) => doc.value === docType) ?? null,
    [docType]
  );
  const visibleDrafts = useMemo(
    () => filterDrafts(drafts, search),
    [drafts, search]
  );

  // Redirect unauthenticated visitors to the login page.
  useEffect(() => {
    if (!authLoading && !session) router.replace("/auth/login");
  }, [authLoading, session, router]);

  // Load the signed-in user's drafts once we have a user.
  useEffect(() => {
    if (!userId) return;
    let active = true;
    setDraftsLoading(true);
    listDrafts()
      .then((rows) => {
        if (!active) return;
        setDrafts(rows);
        setDraftsError(null);
      })
      .catch((e) => {
        if (active)
          setDraftsError(
            e instanceof Error ? e.message : "Failed to load drafts."
          );
      })
      .finally(() => {
        if (active) setDraftsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [userId]);

  function selectDocType(value: string) {
    setDocType(value);
    setValues({});
    setResult("");
    setError(null);
    setActiveDraftId(null);
    setSidebarOpen(false);
  }

  function newDraft() {
    setDocType("");
    setValues({});
    setResult("");
    setError(null);
    setActiveDraftId(null);
    setSidebarOpen(false);
  }

  function loadDraft(draft: Draft) {
    setDocType(draft.doc_type);
    setValues(draft.fields ?? {});
    setResult(draft.generated_text);
    setActiveDraftId(draft.id);
    setError(null);
    setSidebarOpen(false);
  }

  function handleFieldChange(key: string, value: string) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  async function handleGenerate() {
    if (!selected) {
      setError("Please select a document type.");
      return;
    }
    const missing = selected.fields.filter((f) => !values[f.key]?.trim());
    if (missing.length > 0) {
      setError(
        `Please fill in all fields: ${missing.map((m) => m.label).join(", ")}.`
      );
      return;
    }
    if (!session || !user) {
      router.replace("/auth/login");
      return;
    }

    setLoading(true);
    setError(null);
    setResult("");
    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ doc_type: selected.value, details: values }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(
          data?.error || `Request failed with status ${response.status}.`
        );
      }
      const text = typeof data.text === "string" ? data.text : "";
      setResult(text);
      if (!text) {
        setError("The model returned an empty document. Please try again.");
        return;
      }

      // Auto-save to history. A save failure must not discard the draft text.
      try {
        const saved = await createDraft({
          user_id: user.id,
          doc_type: selected.value,
          doc_type_label: selected.label,
          fields: values,
          generated_text: text,
          title: formatDraftTitle(selected.label),
        });
        setDrafts((prev) => [saved, ...prev]);
        setActiveDraftId(saved.id);
        setDraftsError(null);
      } catch (saveError) {
        setDraftsError(
          saveError instanceof Error
            ? `Draft generated but not saved: ${saveError.message}`
            : "Draft generated but could not be saved to history."
        );
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function handleCopy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setError("Could not copy to clipboard.");
    }
  }

  function handleDownloadResult() {
    if (!result) return;
    const title =
      drafts.find((d) => d.id === activeDraftId)?.title ??
      selected?.label ??
      "document";
    downloadTextFile(title, result);
  }

  function startRename(draft: Draft) {
    setRenamingId(draft.id);
    setRenameValue(draft.title);
  }

  async function commitRename() {
    const id = renamingId;
    if (!id) return;
    const title = renameValue.trim();
    const current = drafts.find((d) => d.id === id);
    setRenamingId(null);
    if (!current || !title || title === current.title) return;

    setDrafts((prev) => prev.map((d) => (d.id === id ? { ...d, title } : d)));
    try {
      await renameDraft(id, title);
    } catch (e) {
      setDrafts((prev) =>
        prev.map((d) => (d.id === id ? { ...d, title: current.title } : d))
      );
      setDraftsError(e instanceof Error ? e.message : "Rename failed.");
    }
  }

  async function handleDeleteConfirmed() {
    const target = deleteTarget;
    if (!target) return;
    setDeleteTarget(null);
    const snapshot = drafts;
    setDrafts((prev) => prev.filter((d) => d.id !== target.id));
    if (activeDraftId === target.id) newDraft();
    try {
      await deleteDraft(target.id);
    } catch (e) {
      setDrafts(snapshot);
      setDraftsError(e instanceof Error ? e.message : "Delete failed.");
    }
  }

  async function handleSignOut() {
    await signOut();
    router.replace("/auth/login");
  }

  // Block the dashboard until auth resolves; the effect above redirects out.
  if (authLoading || !session) {
    return (
      <div className="flex h-screen items-center justify-center bg-background text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-transform duration-300 ease-out md:static md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex items-center justify-between px-4 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
              <Scale className="h-[18px] w-[18px]" />
            </span>
            <span className="text-base font-semibold tracking-tight text-foreground">
              NyayaDraft
            </span>
          </div>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground md:hidden"
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="px-3">
          <button
            type="button"
            onClick={newDraft}
            className="flex w-full items-center gap-2 rounded-lg border border-sidebar-border bg-transparent px-3 py-2.5 text-sm font-medium transition-colors hover:bg-sidebar-accent"
          >
            <Plus className="h-4 w-4 text-primary" />
            New draft
          </button>
        </div>

        <div className="px-3 pt-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search drafts"
              className="h-9 bg-sidebar-accent/40 pl-8 text-sm"
            />
          </div>
        </div>

        <nav className="mt-3 flex-1 overflow-y-auto px-3 pb-4">
          <p className="px-2 pb-2 pt-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            History
          </p>

          {draftsLoading ? (
            <p className="flex items-center gap-2 px-2 py-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading…
            </p>
          ) : draftsError ? (
            <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-2.5 py-2 text-xs text-destructive">
              {draftsError}
            </p>
          ) : drafts.length === 0 ? (
            <p className="px-2 py-2 text-sm text-muted-foreground">
              No drafts yet. Generate one to see it here.
            </p>
          ) : visibleDrafts.length === 0 ? (
            <p className="px-2 py-2 text-sm text-muted-foreground">
              No drafts match “{search}”.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {visibleDrafts.map((draft) => {
                const active = draft.id === activeDraftId;
                if (renamingId === draft.id) {
                  return (
                    <li key={draft.id}>
                      <input
                        autoFocus
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onBlur={commitRename}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") commitRename();
                          else if (e.key === "Escape") setRenamingId(null);
                        }}
                        className="w-full rounded-lg border border-input bg-background px-2.5 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                      />
                    </li>
                  );
                }
                return (
                  <li key={draft.id} className="group relative">
                    <button
                      type="button"
                      onClick={() => loadDraft(draft)}
                      className={cn(
                        "flex w-full flex-col gap-0.5 rounded-lg py-2 pl-2.5 pr-9 text-left transition-colors",
                        active
                          ? "bg-sidebar-accent text-sidebar-accent-foreground"
                          : "text-sidebar-foreground hover:bg-sidebar-accent/60"
                      )}
                    >
                      <span className="truncate text-sm">{draft.title}</span>
                      <span className="truncate text-xs text-muted-foreground">
                        {draft.doc_type_label} ·{" "}
                        {new Date(draft.created_at).toLocaleDateString(
                          undefined,
                          { day: "numeric", month: "short" }
                        )}
                      </span>
                    </button>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          type="button"
                          aria-label="Draft options"
                          className={cn(
                            "absolute right-1.5 top-2 rounded-md p-1.5 text-muted-foreground opacity-0 transition-colors hover:bg-sidebar-accent hover:text-foreground focus:opacity-100 focus:outline-none group-hover:opacity-100 data-[state=open]:opacity-100",
                            active && "opacity-100"
                          )}
                        >
                          <MoreVertical className="h-4 w-4" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => startRename(draft)}>
                          <Pencil />
                          Rename
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onSelect={() =>
                            downloadTextFile(draft.title, draft.generated_text)
                          }
                        >
                          <Download />
                          Download
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onSelect={() => setDeleteTarget(draft)}
                          className="text-destructive focus:text-destructive"
                        >
                          <Trash2 />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </li>
                );
              })}
            </ul>
          )}
        </nav>

        <div className="border-t border-sidebar-border px-3 py-3">
          <div className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5">
            <span className="min-w-0 truncate text-sm text-muted-foreground">
              {user?.email}
            </span>
            <button
              type="button"
              onClick={handleSignOut}
              aria-label="Sign out"
              className="shrink-0 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-foreground"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
          <p className="px-2 pt-1 text-xs leading-relaxed text-muted-foreground">
            Drafts are for convenience only and do not constitute legal advice.
          </p>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border/70 px-4">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground md:hidden"
            aria-label="Open sidebar"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="truncate text-sm font-medium text-muted-foreground">
            {selected ? selected.label : "NyayaDraft"}
          </span>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:py-14">
            {!selected && !result ? (
              <EmptyState onPick={selectDocType} />
            ) : (
              <div className="space-y-8">
                {selected && (
                  <>
                    <div className="space-y-2 text-center">
                      <h1 className="font-serif text-3xl font-medium tracking-tight sm:text-4xl">
                        {selected.label}
                      </h1>
                      <p className="text-sm text-muted-foreground sm:text-base">
                        {selected.description}
                      </p>
                    </div>

                    <div className="rounded-2xl border border-border bg-card shadow-sm transition-colors">
                      <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 sm:p-5">
                        {selected.fields.map((field) => (
                          <div
                            key={field.key}
                            className={cn(
                              "space-y-1.5",
                              field.type === "textarea" && "sm:col-span-2"
                            )}
                          >
                            <Label
                              htmlFor={field.key}
                              className="text-xs text-muted-foreground"
                            >
                              {field.label}
                            </Label>
                            {field.type === "textarea" ? (
                              <Textarea
                                id={field.key}
                                value={values[field.key] ?? ""}
                                onChange={(event) =>
                                  handleFieldChange(field.key, event.target.value)
                                }
                                placeholder={field.placeholder}
                                className="min-h-[88px] resize-none bg-background/60"
                              />
                            ) : (
                              <Input
                                id={field.key}
                                type={field.type === "number" ? "number" : "text"}
                                value={values[field.key] ?? ""}
                                onChange={(event) =>
                                  handleFieldChange(field.key, event.target.value)
                                }
                                placeholder={field.placeholder}
                                className="bg-background/60"
                              />
                            )}
                          </div>
                        ))}
                      </div>

                      <div className="flex items-center justify-between gap-3 border-t border-border/70 px-4 py-3 sm:px-5">
                        <p className="text-xs text-muted-foreground">
                          All fields are required.
                        </p>
                        <Button
                          onClick={handleGenerate}
                          disabled={loading}
                          className="gap-2 rounded-xl"
                        >
                          {loading ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Generating
                            </>
                          ) : (
                            <>
                              <ArrowUp className="h-4 w-4" />
                              Generate
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </>
                )}

                {error && (
                  <p
                    role="alert"
                    className="rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive duration-300 animate-in fade-in slide-in-from-bottom-2"
                  >
                    {error}
                  </p>
                )}

                {result && (
                  <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-sm duration-300 animate-in fade-in slide-in-from-bottom-2">
                    <div className="flex items-center justify-between gap-3 border-b border-border/70 px-4 py-3 sm:px-5">
                      <h2 className="text-sm font-medium">Generated draft</h2>
                      <div className="flex gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={handleCopy}
                          className="gap-1.5 text-muted-foreground hover:text-foreground"
                        >
                          {copied ? (
                            <Check className="h-4 w-4" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                          {copied ? "Copied" : "Copy"}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={handleDownloadResult}
                          className="gap-1.5 text-muted-foreground hover:text-foreground"
                        >
                          <Download className="h-4 w-4" />
                          Download
                        </Button>
                      </div>
                    </div>
                    <pre className="max-h-[560px] overflow-y-auto whitespace-pre-wrap px-4 py-4 font-mono text-sm leading-relaxed text-foreground/90 sm:px-5">
                      {result}
                    </pre>
                  </section>
                )}
              </div>
            )}
          </div>
        </main>
      </div>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete draft?</AlertDialogTitle>
            <AlertDialogDescription>
              “{deleteTarget?.title}” will be permanently deleted. This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirmed}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (value: string) => void }) {
  return (
    <div className="flex flex-col items-center pt-6 text-center sm:pt-16">
      <span className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/15 text-primary">
        <Scale className="h-7 w-7" />
      </span>
      <h1 className="font-serif text-3xl font-medium tracking-tight sm:text-4xl">
        What would you like to draft?
      </h1>
      <p className="mt-3 max-w-md text-sm text-muted-foreground sm:text-base">
        AI-assisted drafting for Indian legal documents. Choose a document type
        to begin.
      </p>

      <div className="mt-10 grid w-full grid-cols-1 gap-3 text-left sm:grid-cols-2">
        {DOC_TYPES.map((doc) => (
          <button
            key={doc.value}
            type="button"
            onClick={() => onPick(doc.value)}
            className="group flex items-start gap-3 rounded-xl border border-border bg-card/60 p-4 transition-colors hover:border-primary/40 hover:bg-accent"
          >
            <FileText className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground transition-colors group-hover:text-primary" />
            <span className="min-w-0">
              <span className="block text-sm font-medium">{doc.label}</span>
              <span className="mt-0.5 block text-xs leading-relaxed text-muted-foreground">
                {doc.description}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
