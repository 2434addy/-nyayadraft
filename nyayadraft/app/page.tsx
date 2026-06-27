"use client";

import { useMemo, useState } from "react";
import { Check, Copy, Download, Loader2 } from "lucide-react";

import { DOC_TYPES } from "@/lib/documents";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export default function Home() {
  const [docType, setDocType] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const selected = useMemo(
    () => DOC_TYPES.find((doc) => doc.value === docType) ?? null,
    [docType]
  );

  function handleDocTypeChange(value: string) {
    setDocType(value);
    setValues({});
    setResult("");
    setError(null);
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
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-3xl px-4 py-12">
        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight">NyayaDraft</h1>
          <p className="mt-2 text-muted-foreground">
            AI-assisted drafting for Indian legal documents. Select a document
            type, fill in the details, and generate a draft.
          </p>
        </header>

        <Card>
          <CardHeader>
            <CardTitle className="text-xl">Document details</CardTitle>
            <CardDescription>
              {selected
                ? selected.description
                : "All fields are required to generate a draft."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="doc-type">Document type</Label>
              <Select value={docType} onValueChange={handleDocTypeChange}>
                <SelectTrigger id="doc-type">
                  <SelectValue placeholder="Select a document type" />
                </SelectTrigger>
                <SelectContent>
                  {DOC_TYPES.map((doc) => (
                    <SelectItem key={doc.value} value={doc.value}>
                      {doc.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {selected && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {selected.fields.map((field) => (
                  <div
                    key={field.key}
                    className={cn(
                      "space-y-2",
                      field.type === "textarea" && "sm:col-span-2"
                    )}
                  >
                    <Label htmlFor={field.key}>{field.label}</Label>
                    {field.type === "textarea" ? (
                      <Textarea
                        id={field.key}
                        value={values[field.key] ?? ""}
                        onChange={(event) =>
                          handleFieldChange(field.key, event.target.value)
                        }
                      />
                    ) : (
                      <Input
                        id={field.key}
                        type={field.type === "number" ? "number" : "text"}
                        value={values[field.key] ?? ""}
                        onChange={(event) =>
                          handleFieldChange(field.key, event.target.value)
                        }
                      />
                    )}
                  </div>
                ))}
              </div>
            )}

            <Button
              onClick={handleGenerate}
              disabled={loading || !docType}
              className="w-full sm:w-auto"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                "Generate document"
              )}
            </Button>

            {error && (
              <p
                role="alert"
                className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {error}
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="mt-6">
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <div className="space-y-1.5">
              <CardTitle className="text-xl">Generated document</CardTitle>
              <CardDescription>Review carefully before use.</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleCopy}
                disabled={!result}
              >
                {copied ? (
                  <Check className="mr-2 h-4 w-4" />
                ) : (
                  <Copy className="mr-2 h-4 w-4" />
                )}
                {copied ? "Copied" : "Copy"}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleDownload}
                disabled={!result}
              >
                <Download className="mr-2 h-4 w-4" />
                Download
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <Textarea
              readOnly
              value={result}
              placeholder="The generated document will appear here."
              className="h-[420px] resize-none overflow-y-auto whitespace-pre-wrap font-mono text-sm"
            />
          </CardContent>
        </Card>

        <footer className="mt-8 text-center text-xs text-muted-foreground">
          NyayaDraft produces drafts for convenience only and does not
          constitute legal advice.
        </footer>
      </div>
    </main>
  );
}
