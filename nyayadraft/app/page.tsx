"use client";

import { useMemo, useState } from "react";
import {
  ArrowUp,
  Check,
  Copy,
  Download,
  FileText,
  Loader2,
  Menu,
  Plus,
  Scale,
  X,
} from "lucide-react";

import { DOC_TYPES } from "@/lib/documents";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export default function Home() {
  const [docType, setDocType] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const selected = useMemo(
    () => DOC_TYPES.find((doc) => doc.value === docType) ?? null,
    [docType]
  );

  function selectDocType(value: string) {
    setDocType(value);
    setValues({});
    setResult("");
    setError(null);
    setSidebarOpen(false);
  }

  function newDraft() {
    setDocType("");
    setValues({});
    setResult("");
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

    setLoading(true);
    setError(null);
    setResult("");
    try {
      const response = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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

  function handleDownload() {
    if (!result) return;
    const blob = new Blob([result], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${docType || "document"}.txt`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
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

        <nav className="mt-5 flex-1 overflow-y-auto px-3 pb-4">
          <p className="px-2 pb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Document types
          </p>
          <ul className="space-y-0.5">
            {DOC_TYPES.map((doc) => {
              const active = doc.value === docType;
              return (
                <li key={doc.value}>
                  <button
                    type="button"
                    onClick={() => selectDocType(doc.value)}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
                      active
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-sidebar-foreground hover:bg-sidebar-accent/60"
                    )}
                  >
                    <FileText
                      className={cn(
                        "h-4 w-4 shrink-0",
                        active ? "text-primary" : "text-muted-foreground"
                      )}
                    />
                    <span className="truncate">{doc.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="border-t border-sidebar-border px-4 py-3">
          <p className="text-xs leading-relaxed text-muted-foreground">
            Drafts are for convenience only and do not constitute legal advice.
          </p>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
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

        {/* Scroll area */}
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl px-4 py-10 sm:py-14">
            {!selected ? (
              <EmptyState onPick={selectDocType} />
            ) : (
              <div className="space-y-8">
                <div className="space-y-2 text-center">
                  <h1 className="font-serif text-3xl font-medium tracking-tight sm:text-4xl">
                    {selected.label}
                  </h1>
                  <p className="text-sm text-muted-foreground sm:text-base">
                    {selected.description}
                  </p>
                </div>

                {/* Composer */}
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
                          onClick={handleDownload}
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
