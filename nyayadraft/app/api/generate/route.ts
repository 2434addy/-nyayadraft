import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const maxDuration = 300;

interface GenerateBody {
  doc_type?: string;
  details?: Record<string, string>;
}

/**
 * Thin proxy to the standalone NyayaDraft generation backend.
 *
 * All RunPod interaction (prompt building, the run/poll loop, output cleaning)
 * now lives in the Express service at `backend/`. This route forwards the
 * request body untouched and relays the backend's JSON response and status, so
 * the `{ text }` / `{ error }` contract the client expects is preserved.
 */
export async function POST(request: Request) {
  const apiBase = process.env.NEXT_PUBLIC_API_URL;
  if (!apiBase) {
    return NextResponse.json(
      { error: "Server is not configured. Set NEXT_PUBLIC_API_URL." },
      { status: 500 }
    );
  }

  let body: GenerateBody;
  try {
    body = (await request.json()) as GenerateBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON request body." }, { status: 400 });
  }

  const target = `${apiBase.replace(/\/+$/, "")}/api/generate`;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: `Could not reach the generation backend: ${
          error instanceof Error ? error.message : "network error"
        }`,
      },
      { status: 502 }
    );
  }

  let data: unknown;
  try {
    data = await upstream.json();
  } catch {
    return NextResponse.json(
      { error: "The generation backend returned an invalid response." },
      { status: 502 }
    );
  }

  return NextResponse.json(data, { status: upstream.status });
}
