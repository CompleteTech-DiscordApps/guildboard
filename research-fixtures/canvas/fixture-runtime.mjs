// Loopback-only research helpers. No application server or production policy.
import http from 'node:http';
import {readFile, realpath} from 'node:fs/promises';
import path from 'node:path';

export function browserLaunchOptions(executablePath) {
  const options = {headless: true, chromiumSandbox: true};
  if (executablePath) options.executablePath = executablePath;
  return options;
}

export function isFixtureNetworkRequest(requestUrl, fixtureOrigin) {
  try {
    const url = new URL(requestUrl);
    return (url.protocol === 'http:' || url.protocol === 'https:') && url.origin === fixtureOrigin;
  } catch {
    return false;
  }
}

function isWithinRoot(root, file) {
  const relative = path.relative(root, file);
  return relative !== '..' && !relative.startsWith('..' + path.sep) && !path.isAbsolute(relative);
}

export async function startFixtureServer(directory) {
  const root = await realpath(directory);
  const server = http.createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
      const candidate = path.resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname));
      if (!isWithinRoot(root, candidate)) throw Error('outside fixture');
      const file = await realpath(candidate);
      if (!isWithinRoot(root, file)) throw Error('outside fixture');
      const data = await readFile(file);
      const extension = path.extname(file);
      const contentType = {'.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html'}[extension]
        || 'application/octet-stream';
      response.writeHead(200, {'content-type': contentType});
      response.end(data);
    } catch {
      response.writeHead(404);
      response.end();
    }
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      server.off('error', reject);
      resolve();
    });
  });
  return server;
}
