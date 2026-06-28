// Production entry point for NyayaDraft's backend.
//
// Railway's Procfile runs `node server.js`. The TypeScript sources under `src/`
// are compiled to `dist/` by `npm run build` (the Railway build phase, see
// railway.json). This thin CommonJS shim simply boots the compiled server, so
// `node server.js` works identically in local and deployed environments.
require("./dist/server.js");
