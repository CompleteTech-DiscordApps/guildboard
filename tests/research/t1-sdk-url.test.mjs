// Local execution of the actual pinned SDK helper; no browser/proxy/OAuth mock.
import assert from 'node:assert/strict';
import test from 'node:test';
import { pathToFileURL } from 'node:url';

const { matchAndRewriteURL, absoluteURL } = await import(pathToFileURL(process.env.T1_SDK_URL_MODULE));
const proxyHost = '123456789.discordsays.com';
const rewrite = (url, extra = {}) => matchAndRewriteURL({
  originalURL: new URL(url), prefix: '/api', prefixHost: proxyHost,
  target: 'backend.example.test', ...extra,
}).toString();

test('maps configured HTTPS target and preserves query and fragment', () => {
  assert.equal(rewrite('https://backend.example.test/boards?q=1#view'),
    `https://${proxyHost}/api/boards?q=1#view`);
});

test('preserves WSS protocol while rewriting a configured target', () => {
  assert.equal(rewrite('wss://backend.example.test/socket'), `wss://${proxyHost}/api/socket`);
});

test('this unrelated URL remains unchanged rather than being denied by helper', () => {
  assert.equal(rewrite('https://unrelated.invalid/path'), 'https://unrelated.invalid/path');
});

// Characterize the pinned helper's regex matching, not browser or proxy behavior.
test('rewrites a lookalike hostname matched by unescaped target dots', () => {
  assert.equal(rewrite('https://backend-example-test/boards'), `https://${proxyHost}/api/boards`);
});

test('rewrites a subdomain containing the configured hostname', () => {
  assert.equal(rewrite('https://sub.backend.example.test/boards'), `https://${proxyHost}/api/boards`);
});

test('rewrites an unrelated host when its path contains the target', () => {
  assert.equal(rewrite('https://unrelated.invalid/backend.example.test/boards'),
    `https://${proxyHost}/api/backend.example.test/boards`);
});

test('rewrites an unrelated host when its query contains the target', () => {
  assert.equal(rewrite('https://unrelated.invalid/path?next=https://backend.example.test/boards'),
    `https://${proxyHost}/api/path?next=https://backend.example.test/boards`);
});

test('resolves explicit relative URL against supplied proxy origin', () => {
  assert.equal(absoluteURL('/.proxy/api/token', 'https:', proxyHost).toString(),
    `https://${proxyHost}/.proxy/api/token`);
});

test('substitutes configured target parameter into prefix', () => {
  assert.equal(rewrite('https://assets-blue.example.test/image.png', {
    target: 'assets-{tenant}.example.test', prefix: '/assets/{tenant}',
  }), `https://${proxyHost}/assets/blue/image.png`);
});

test('incomplete parameter mapping throws rather than yielding a usable route', () => {
  assert.throws(() => rewrite('https://backend.example.test/image.png', {
    prefix: '/assets/{missing}',
  }), /Misconfigured route/);
});

test('malformed input URL is rejected by URL parsing', () => {
  assert.throws(() => rewrite('https://[invalid'), TypeError);
});

test('malformed configured target is rejected by URL parsing', () => {
  assert.throws(() => rewrite('https://backend.example.test/path', {
    target: 'not a valid host',
  }), TypeError);
});
