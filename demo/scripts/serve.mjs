import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize, resolve, sep } from "node:path";

const root = resolve(process.cwd(), "out");
const port = Number(process.env.PORT || 4173);
const host = process.env.HOST || "127.0.0.1";

const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".woff": "font/woff",
  ".txt": "text/plain; charset=utf-8",
};

async function resolveFile(urlPath) {
  let clean = normalize(decodeURIComponent(urlPath.split("?")[0]));
  while (clean.startsWith("/") || clean.startsWith(sep)) clean = clean.slice(1);
  const candidate = resolve(root, clean);
  if (candidate !== root && !candidate.startsWith(root + sep)) return null;
  for (const option of [candidate, join(candidate, "index.html"), candidate + ".html"]) {
    try {
      const info = await stat(option);
      if (info.isFile()) return option;
    } catch {
      continue;
    }
  }
  return null;
}

try {
  await stat(join(root, "index.html"));
} catch {
  console.error("No built bundle at demo/out. Run: npm run demo");
  process.exit(1);
}

createServer(async (request, response) => {
  const file = await resolveFile(request.url || "/");
  if (!file) {
    response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    response.end("Not found");
    return;
  }
  const body = await readFile(file);
  response.writeHead(200, {
    "content-type": types[extname(file)] || "application/octet-stream",
    "cache-control": "no-store",
  });
  response.end(body);
}).listen(port, host, () => {
  console.log("");
  console.log(`  Enigma audit demo, offline, no API key`);
  console.log(`  Open http://${host}:${port}`);
  console.log(`  Keys: arrows move, 0 to 6 jump, F fullscreen, P presenter notes`);
  console.log(`  Stop with Ctrl+C`);
  console.log("");
});
