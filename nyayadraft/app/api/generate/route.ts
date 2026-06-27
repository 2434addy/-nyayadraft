import { NextResponse } from "next/server";
import { buildPrompt } from "@/lib/prompt-templates";

export const runtime = "nodejs";
export const maxDuration = 300;

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
    .replace(/Format ascribed below without deviation:\s*/gi, "")
    .replace(/This template[^.]*\./gi, "")
    .replace(/Sure! Below is a draft[^.]*\./gi, "")
    .replace(/Please note that[^.]*\./gi, "")
    .replace(/Note:\s*This is a template[^.]*\./gi, "")
    .replace(/\[End of document\]/gi, "")
    .replace(/\(End\)/gi, "")
    .trim();
}

interface GenerateBody {
  doc_type?: string;
  details?: Record<string, string>;
}

export async function POST(request: Request) {
  const apiUrl = process.env.RUNPOD_API_URL;
  const apiKey = process.env.RUNPOD_API_KEY;
  if (!apiUrl || !apiKey) {
    return NextResponse.json(
      { error: "Server is not configured. Set RUNPOD_API_URL and RUNPOD_API_KEY." },
      { status: 500 }
    );
  }

  let body: GenerateBody;
  try {
    body = (await request.json()) as GenerateBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON request body." }, { status: 400 });
  }

  const { doc_type, details } = body;
  if (!doc_type || !details || typeof details !== "object") {
    return NextResponse.json(
      { error: "Both 'doc_type' and 'details' are required." },
      { status: 400 }
    );
  }

  let prompt: string;
  try {
    prompt = buildPrompt(doc_type, details);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Could not build prompt." },
      { status: 400 }
    );
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
          prompt,
          sampling_params: { max_tokens: 4096, temperature: 0.7 },
        },
      }),
    });
  } catch (error) {
    return NextResponse.json(
      { error: `Could not reach RunPod: ${error instanceof Error ? error.message : "network error"}` },
      { status: 502 }
    );
  }

  if (!runResponse.ok) {
    const detail = await runResponse.text();
    return NextResponse.json(
      { error: `RunPod request failed (${runResponse.status}): ${detail}` },
      { status: 502 }
    );
  }

  const runData = (await runResponse.json()) as {
    id?: string;
    status?: string;
    output?: unknown;
  };

  if (runData.status === "COMPLETED") {
    return NextResponse.json({ text: cleanOutput(extractText(runData.output)) });
  }

  const jobId = runData.id;
  if (!jobId) {
    return NextResponse.json(
      { error: "RunPod did not return a job id." },
      { status: 502 }
    );
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
      return NextResponse.json(
        { error: `RunPod status check failed (${statusResponse.status}): ${detail}` },
        { status: 502 }
      );
    }

    const statusData = (await statusResponse.json()) as {
      status?: string;
      output?: unknown;
      error?: unknown;
    };

    switch (statusData.status) {
      case "COMPLETED":
        return NextResponse.json({ text: cleanOutput(extractText(statusData.output)) });
      case "FAILED":
      case "CANCELLED":
      case "TIMED_OUT": {
        const reason =
          typeof statusData.error === "string" ? ` ${statusData.error}` : "";
        return NextResponse.json(
          { error: `Generation ${statusData.status.toLowerCase()}.${reason}` },
          { status: 502 }
        );
      }
      default:
        break;
    }
  }

  return NextResponse.json(
    { error: "Generation timed out while waiting for RunPod." },
    { status: 504 }
  );
}