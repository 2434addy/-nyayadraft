# NyayaDraft

AI-assisted drafting for Indian legal documents. NyayaDraft is a single-page
Next.js app that collects the details for a chosen document type and asks a
fine-tuned LLM (served on [RunPod](https://www.runpod.io/) serverless) to draft
it. The generated text can be copied or downloaded as a `.txt` file.

> **Disclaimer:** Generated documents are drafts for convenience only and do
> not constitute legal advice. Always have output reviewed by a qualified
> advocate before use.

## Tech stack

- **Next.js 14** (App Router) + **TypeScript**
- **Tailwind CSS** + **shadcn/ui** (Radix primitives)
- Server-side RunPod integration via an internal API route

## Getting started

### 1. Install dependencies

```bash
npm install
```

### 2. Configure environment

Copy the example file and fill in your RunPod details:

```bash
cp .env.example .env.local
```

| Variable          | Description                                                                 |
| ----------------- | --------------------------------------------------------------------------- |
| `RUNPOD_API_URL`  | The `/run` endpoint of your RunPod serverless deployment.                   |
| `RUNPOD_API_KEY`  | Your RunPod API key. Sent as `Authorization: Bearer <key>`.                 |

These variables are read **only on the server** (inside the API route), so the
key is never exposed to the browser.

### 3. Run

```bash
npm run dev      # http://localhost:3000
npm run build    # production build
npm start        # serve the production build
```

## How it works

```
Browser (app/page.tsx)
  │  POST /api/generate  { doc_type, details }
  ▼
API route (app/api/generate/route.ts)
  │  1. buildPrompt(doc_type, details)        ← lib/prompt-templates.ts
  │  2. POST RUNPOD_API_URL { input: { prompt, sampling_params: { max_tokens: 4096, temperature: 0.7 } } }
  │  3. poll  .../status/<id>  every 2s until COMPLETED
  ▼
Returns { text } → rendered in a readonly textarea
```

- **`lib/documents.ts`** — the single source of truth for the 11 document
  types and their form fields (shared shape with the prompt templates).
- **`lib/prompt-templates.ts`** — one instruction template per document type,
  used server-side to build the model prompt.

## Supported document types

1. General Affidavit
2. Cheque Bounce Notice (S.138 NI Act)
3. Memorandum of Understanding
4. Leave & License Agreement (Maharashtra)
5. Consumer Complaint (CPA 2019)
6. Partnership Deed (1932 Act)
7. Reply to a Legal Notice
8. Legal Notice — Landlord to Tenant
9. Employment Termination Letter
10. Legal Notice — Money Recovery
11. Legal Notice — General

## Notes

- The API route polls RunPod for up to 5 minutes (`MAX_POLLS × POLL_INTERVAL_MS`
  in `app/api/generate/route.ts`). When deploying to a serverless host, ensure
  the function timeout (`maxDuration`) accommodates long generations.
- `extractText()` normalises several common RunPod worker output shapes
  (`string`, `{ text }`, vLLM `choices`, token lists) into a single string.
