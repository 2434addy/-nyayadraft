// Production entry point for NyayaDraft's backend.
//
// The Procfile runs `node server.js`. The TypeScript sources under `src/`
// are compiled to `dist/` by `npm run build` (the build phase on Render).
// This thin CommonJS shim simply boots the compiled server, so
// `node server.js` works identically in local and deployed environments.
require("./dist/server.js");
