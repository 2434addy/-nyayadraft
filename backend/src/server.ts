import "dotenv/config";
import express, { type Request as ExpressRequest, type Response as ExpressResponse } from "express";
import cors from "cors";

import { buildPrompt } from "./lib/prompt-templates";
import { NYAYADRAFT_SYSTEM_PROMPT } from "./lib/system-prompt";
import { requireUser } from "./lib/auth";

const PORT = Number(process.env.PORT) || 3001;
const POLL_INTERVAL_MS = 2000;
const MAX_POLLS = 150;

function sleep(ms: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
}

function extractText(output: unknown): string {
  if (output === null || output === undefined) return "";
  if (typeof output === "string") return output.trim();

  if (Array.isArray(output)) {
    // RunPod vLLM returns generations as an ordered list of chunks; the full
    // document is the concatenation of every chunk's first choice. Returning
    // early on the first chunk would truncate multi-chunk (streamed) output.
    let acc = "";
    for (const item of output) {
      if (typeof item === "string") {
        acc += item;
        continue;
      }
      if (!item || typeof item !== "object") continue;
      const obj = item as Record<string, unknown>;
      if (Array.isArray(obj.choices) && obj.choices.length > 0) {
        const choice = obj.choices[0] as Record<string, unknown>;
        if (Array.isArray(choice.tokens)) acc += (choice.tokens as string[]).join("");
        else if (typeof choice.text === "string") acc += choice.text;
      } else if (Array.isArray(obj.tokens)) {
        acc += (obj.tokens as string[]).join("");
      } else if (typeof obj.text === "string") {
        acc += obj.text;
      }
    }
    if (acc.trim()) return acc.trim();
    return output.map((i) => extractText(i)).filter(Boolean).join("\n").trim();
  }

  if (typeof output === "object") {
    const obj = output as Record<string, unknown>;
    if (Array.isArray(obj.choices)) {
      for (const choice of obj.choices as Record<string, unknown>[]) {
        if (Array.isArray(choice.tokens)) {
          return (choice.tokens as string[]).join("").trim();
        }
        if (typeof choice.text === "string") return choice.text.trim();
      }
    }
    if (Array.isArray(obj.tokens)) {
      return (obj.tokens as string[]).join("").trim();
    }
    const keys = ["text", "content", "generated_text", "output", "result"];
    for (const key of keys) {
      if (typeof obj[key] === "string" && (obj[key] as string).trim()) {
        return (obj[key] as string).trim();
      }
    }
    return JSON.stringify(output, null, 2);
  }

  return String(output);
}

function cleanOutput(text: string): string {
  return text
    // Strip leading meta-instruction preamble lines the model sometimes echoes
    // before the document proper. Anchored at the start; real documents open
    // with a title, party block, or date line — never these phrasings.
    .replace(/^(?:\s*(?:use\b|make sure\b|ensure\b|the (?:notice|document|deed|agreement|affidavit|complaint|letter|reply) should\b|the style\b|legal notice requires\b|this is a (?:general )?template\b)[^\n]*\n+)+/i, "")
    .replace(/Format ascribed below without deviation:\s*/gi, "")
    .replace(/This template[^.]*\./gi, "")
    .replace(/Sure! Below is a draft[^.]*\./gi, "")
    .replace(/Please note that[^.]*\./gi, "")
    .replace(/Note:\s*This is a template[^.]*\./gi, "")
    // Normalise residual bracketed artefacts the model emits in signature
    // blocks, while preserving intentional [VERIFY: ...] legal placeholders.
    .replace(/\[(?!\s*VERIFY)[^\]]*authoris[a-z]*\s+signatory[^\]]*\]/gi, "Authorised Signatory")
    .replace(/\[(?!\s*VERIFY)([^\]]*(?:seal|attestation)[^\]]*)\]/gi, "($1)")
    // Remove every remaining non-[VERIFY:] bracketed token: in a NyayaDraft
    // document the only legitimate brackets are [VERIFY: ...] legal flags;
    // anything else is a model placeholder artefact (signature labels,
    // instruction echoes, stray field labels) and must not reach the user.
    // (handles one level of nesting, e.g. "[STAMP PAPER OF ₹ [VALUE] …]", so no
    // dangling fragment is left behind)
    .replace(/\[(?!\s*VERIFY)[^[\]]*(?:\[[^[\]]*\][^[\]]*)*\]/g, "")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/^[ \t]+$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/\(End\)/gi, "")
    .trim();
}

interface GenerateBody {
  doc_type?: string;
  details?: Record<string, string>;
}

const app = express();

// CORS for the Vercel frontend. Set FRONTEND_ORIGIN to your deployed frontend
// URL (comma-separated to allow several, e.g. production + preview). When unset
// the request origin is reflected, which keeps local development frictionless.
const allowedOrigins = process.env.FRONTEND_ORIGIN
  ? process.env.FRONTEND_ORIGIN.split(",").map((origin) => origin.trim()).filter(Boolean)
  : null;
app.use(cors({ origin: allowedOrigins ?? true }));

app.use(express.json({ limit: "1mb" }));

app.get("/health", (_req: ExpressRequest, res: ExpressResponse) => {
  res.json({ status: "ok" });
});

app.post("/api/generate", requireUser, async (req: ExpressRequest, res: ExpressResponse) => {
  try {
    const apiUrl = process.env.RUNPOD_API_URL;
    const apiKey = process.env.RUNPOD_API_KEY;
    if (!apiUrl || !apiKey) {
      return res.status(500).json({
        error: "Server is not configured. Set RUNPOD_API_URL and RUNPOD_API_KEY.",
      });
    }

    const body = (req.body ?? {}) as GenerateBody;
    const { doc_type, details } = body;
    if (!doc_type || !details || typeof details !== "object") {
      return res.status(400).json({ error: "Both 'doc_type' and 'details' are required." });
    }

    let prompt: string;
    try {
      prompt = buildPrompt(doc_type, details);
    } catch (error) {
      return res.status(400).json({
        error: error instanceof Error ? error.message : "Could not build prompt.",
      });
    }

    const headers = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    };

    let runResponse: Response;
    try {
      runResponse = await fetch(apiUrl, {
        method: "POST",
        headers,
        body: JSON.stringify({
          input: {
            messages: [
              { role: "system", content: NYAYADRAFT_SYSTEM_PROMPT },
              { role: "user", content: prompt },
            ],
            sampling_params: { max_tokens: 4096, temperature: 0.3 },
          },
        }),
      });
    } catch (error) {
      return res.status(502).json({
        error: `Could not reach RunPod: ${error instanceof Error ? error.message : "network error"}`,
      });
    }

    if (!runResponse.ok) {
      const detail = await runResponse.text();
      return res.status(502).json({
        error: `RunPod request failed (${runResponse.status}): ${detail}`,
      });
    }

    const runData = (await runResponse.json()) as {
      id?: string;
      status?: string;
      output?: unknown;
    };

    if (runData.status === "COMPLETED") {
      return res.json({ text: cleanOutput(extractText(runData.output)) });
    }

    const jobId = runData.id;
    if (!jobId) {
      return res.status(502).json({ error: "RunPod did not return a job id." });
    }

    const statusUrl = `${apiUrl.replace(/\/run(sync)?\/?$/, "")}/status/${jobId}`;

    for (let attempt = 0; attempt < MAX_POLLS; attempt++) {
      await sleep(POLL_INTERVAL_MS);

      let statusResponse: Response;
      try {
        statusResponse = await fetch(statusUrl, { method: "GET", headers });
      } catch {
        continue;
      }

      if (!statusResponse.ok) {
        const detail = await statusResponse.text();
        return res.status(502).json({
          error: `RunPod status check failed (${statusResponse.status}): ${detail}`,
        });
      }

      const statusData = (await statusResponse.json()) as {
        status?: string;
        output?: unknown;
        error?: unknown;
      };

      switch (statusData.status) {
        case "COMPLETED":
          return res.json({ text: cleanOutput(extractText(statusData.output)) });
        case "FAILED":
        case "CANCELLED":
        case "TIMED_OUT": {
          const reason =
            typeof statusData.error === "string" ? ` ${statusData.error}` : "";
          return res.status(502).json({
            error: `Generation ${statusData.status.toLowerCase()}.${reason}`,
          });
        }
        default:
          break;
      }
    }

    return res.status(504).json({ error: "Generation timed out while waiting for RunPod." });
  } catch (error) {
    // Express 4 has no automatic error boundary for rejected async handlers
    // (unlike the Next.js route this was extracted from), so guard the whole
    // handler to guarantee the client always receives a JSON response.
    return res.status(500).json({
      error: `Unexpected server error: ${error instanceof Error ? error.message : "unknown error"}`,
    });
  }
});

app.listen(PORT, () => {
  console.log(`NyayaDraft backend listening on port ${PORT}`);
});

export default app;
