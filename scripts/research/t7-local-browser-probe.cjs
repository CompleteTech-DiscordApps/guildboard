// Run the shared T7 fixture assertions with an existing Playwright package
// and Chromium executable. Output is local fixture evidence.
const { createHash } = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { mkdtempSync, readFileSync } = require('node:fs');
const { resolve, join } = require('node:path');
const { runInNewContext } = require('node:vm');

const [playwrightDir, chromiumPath, outputDir] = process.argv.slice(2);
if (!playwrightDir || !chromiumPath || !outputDir) {
  console.error('Usage: node scripts/research/t7-local-browser-probe.cjs PLAYWRIGHT_DIR CHROMIUM_EXECUTABLE OUTPUT_DIR');
  process.exit(2);
}

const root = resolve(__dirname, '../..');
const hash = value => createHash('sha256').update(value).digest('hex');

async function main() {
  const { chromium } = require(resolve(playwrightDir));
  const { version: playwrightVersion } = require(resolve(playwrightDir, 'package.json'));
  const html = readFileSync(join(root, 'docs/research/t7-outline-prototype.html'), 'utf8');
  const source = readFileSync(join(root, 'tests/research/t7-browser-checks.js'), 'utf8');
  const checks = runInNewContext(source, {}, { filename: 't7-browser-checks.js' });
  const head = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
  const screenshot = join(mkdtempSync(join(resolve(outputDir), 't7-browser-')), 'fixture.png');

  const browser = await chromium.launch({
    executablePath: resolve(chromiumPath),
    chromiumSandbox: true,
    headless: true,
  });
  let result;
  try {
    const page = await browser.newPage({ serviceWorkers: 'block' });
    const attemptedRequests = [];
    await page.route('**/*', route => {
      attemptedRequests.push(route.request().resourceType());
      return route.abort();
    });
    await page.setContent(html);
    result = await checks(page, screenshot);
    if (attemptedRequests.length) {
      throw new Error('The fixture attempted to load a network resource.');
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({
    observed_at_utc: new Date().toISOString(),
    tested_head: head,
    environment: { platform: process.platform, node: process.version, playwright: playwrightVersion, chromium_sandbox: true },
    prototype_sha256: hash(html),
    checks_sha256: hash(source),
    screenshot_path: screenshot,
    screenshot_sha256: hash(readFileSync(screenshot)),
    browser_result: result,
  }, null, 2));
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
