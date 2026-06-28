# NyayaDraft Backend

Standalone Express API that drafts Indian legal documents by proxying to the
fine-tuned NyayaDraft model on a RunPod serverless (vLLM) endpoint. This service
was extracted from the Next.js app's `app/api/generate/route.ts` so the heavy
run/poll loop runs on a platform without serverless function time limits.

## Endpoints

| Method | Path            | Description                                         |
| ------ | --------------- | --------------------------------------------------- |
| `POST` | `/api/generate` | Generate a document. Body: `{ doc_type, details }`. |
| `GET`  | `/health`       | Liveness probe. Returns `{ "status": "ok" }`.       |

`POST /api/generate` returns `{ "text": "<document>" }` on success, or
`{ "error": "<message>" }` with a non-200 status on failure — identical to the
contract the Next.js frontend expects.

## Environment variables

Copy `.env.example` to `.env` and fill in your values:

| Variable          | Required | Description                                                                                  |
| ----------------- | -------- | -------------------------------------------------------------------------------------------- |
| `RUNPOD_API_URL`  | yes      | The `/run` endpoint of your RunPod serverless deployment.                                     |
| `RUNPOD_API_KEY`  | yes      | RunPod API key (sent as `Authorization: Bearer <key>`).                                       |
| `PORT`            | no       | Port to listen on. Defaults to `3001`. Railway injects this automatically.                    |
| `FRONTEND_ORIGIN` | no       | Comma-separated allowed CORS origins (your Vercel URL). Unset reflects the request origin.    |

## Run locally

```bash
cd backend
npm install
npm run build      # compiles src/*.ts -> dist/
node server.js     # starts on http://localhost:3001
```

`npm run dev` runs the TypeScript source directly with hot reload (via `tsx`).

Smoke test:

```bash
curl -X POST http://localhost:3001/api/generate \
  -H "Content-Type: application/json" \
  -d '{"doc_type":"affidavit_general","details":{"name":"Test","city":"Mumbai"}}'
```

## Deploy to Railway

The repo ships with `railway.json` (build + start config) and a `Procfile`
(`web: node server.js`), so deployment is mostly automatic.

1. **Create the service.** In the [Railway](https://railway.app) dashboard:
   _New Project → Deploy from GitHub repo_, then set the service **Root
   Directory** to `backend` (this folder). Railway's Nixpacks builder reads
   `package.json` and runs `npm install && npm run build` (per `railway.json`),
   then starts the app with `node server.js`.

2. **Set environment variables** (service → _Variables_):
   - `RUNPOD_API_URL`
   - `RUNPOD_API_KEY`
   - `FRONTEND_ORIGIN` = your Vercel URL, e.g. `https://nyayadraft.vercel.app`
   - Leave `PORT` unset — Railway provides it and the server reads `process.env.PORT`.

3. **Deploy.** Railway builds and starts the service, exposing it at a generated
   domain (e.g. `https://nyayadraft-backend.up.railway.app`). The health check at
   `/health` must return `200` for the deploy to go live.

4. **Point the frontend at it.** In the Vercel project for `nyayadraft/`, set
   `NEXT_PUBLIC_API_URL` to the Railway URL (no trailing slash). The Next.js
   route at `app/api/generate/route.ts` proxies to `${NEXT_PUBLIC_API_URL}/api/generate`.

> The Node version is pinned to `>=22` (`package.json` `engines`) because the
> poll loop uses `Promise.withResolvers`. Nixpacks honours this when selecting
> the runtime.

## Project layout

```
backend/
  server.js            # entry point (Procfile target); boots dist/server.js
  src/
    server.ts          # Express app: /api/generate run+poll loop, output cleaning
    lib/
      prompt-templates.ts   # buildPrompt(doc_type, details) -> instruction prompt
      system-prompt.ts      # frozen NyayaDraft system prompt (training-distribution)
      documents.ts          # the 11 doc-type field catalogue (shared schema)
  railway.json         # Railway build/start/healthcheck config
  Procfile             # web: node server.js
  tsconfig.json        # compiles src/ -> dist/ (CommonJS)
```
