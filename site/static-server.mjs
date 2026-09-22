/**
 * Minimal static file server for the site/ folder.
 * Used by the Playwright browser tests, which need a real HTTP origin
 * because ES modules cannot be loaded from file:// URLs.
 */
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(fileURLToPath(new URL('.', import.meta.url)));
const PORT = Number(process.env.SITE_PORT || 4173);

const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
};

const server = createServer(async (req, res) => {
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(req.url, `http://127.0.0.1:${PORT}`).pathname);
  } catch {
    res.writeHead(400).end('Bad request');
    return;
  }

  const relativePath = normalize(pathname === '/' ? 'index.html' : pathname.slice(1));
  const filePath = resolve(ROOT, relativePath);

  if (filePath !== ROOT && !filePath.startsWith(`${ROOT}${sep}`)) {
    res.writeHead(403).end('Forbidden');
    return;
  }

  try {
    const body = await readFile(filePath);
    res.writeHead(200, { 'Content-Type': CONTENT_TYPES[extname(filePath)] || 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404).end('Not found');
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Serving ${ROOT} on http://127.0.0.1:${PORT}`);
});
