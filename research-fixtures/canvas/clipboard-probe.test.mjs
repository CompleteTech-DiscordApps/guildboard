// Offline control-flow regressions only; no browser or clipboard evidence.
import assert from 'node:assert/strict';
import test from 'node:test';
import {isDeepStrictEqual} from 'node:util';
import {assertLocalBrowserEnvironment, probeClipboard} from './clipboard-probe.mjs';
import {probeCanvas} from './probe.mjs';

const remoteNames = ['SELENIUM_REMOTE_URL', 'SELENIUM_REMOTE_HEADERS', 'SELENIUM_REMOTE_CAPABILITIES'];
const origin = 'http://127.0.0.1:32001';
const syntheticValue = 'synthetic-sensitive-sentinel';

function environment(t, values = {}) {
  const before = {...process.env};
  t.after(() => {
    for (const name of Object.keys(process.env)) if (!Object.hasOwn(before, name)) delete process.env[name];
    Object.assign(process.env, before);
  });
  for (const name of remoteNames) delete process.env[name];
  Object.assign(process.env, values);
  return {...process.env};
}

function deniedCalls() {
  const calls = {launcher: 0, network: 0, clipboard: 0};
  return {calls,
    launch: async () => {
      calls.launcher++;
      calls.network++;
      calls.clipboard++;
      throw Error('denied control must never reach launcher');
    },
    startServer: async () => { calls.network++; throw Error('denied control must never start server'); },
  };
}

for (const entry of ['initial', 'clipboard']) {
  for (const name of remoteNames) for (const value of [syntheticValue, '']) {
    test(`${entry} denies ${name} ${value ? 'configured' : 'empty'} before all side effects`, async t => {
      const before = environment(t, {[name]: value});
      const control = deniedCalls();
      const run = () => entry === 'initial' ? probeCanvas(control) : probeClipboard(origin, control);
      await assert.rejects(run, error => {
        assert.equal(error.message, `Local browser launch requires unset environment names: ${name}`);
        assert.equal(String(error).includes(syntheticValue), false);
        assert.equal(error.stack.includes(syntheticValue), false);
        return true;
      });
      assert.deepEqual(control.calls, {launcher: 0, network: 0, clipboard: 0});
      assert.ok(isDeepStrictEqual({...process.env}, before), 'the full caller environment must stay unchanged');
    });
  }
}

test('all denied configuration is reported by name without values or parent mutation', t => {
  const before = environment(t, Object.fromEntries(remoteNames.map(name => [name, syntheticValue])));
  assert.throws(assertLocalBrowserEnvironment, error => {
    assert.equal(error.message, `Local browser launch requires unset environment names: ${remoteNames.join(', ')}`);
    assert.equal(String(error).includes(syntheticValue), false);
    return true;
  });
  assert.ok(isDeepStrictEqual({...process.env}, before), 'the full caller environment must stay unchanged');
});

for (const executablePath of ['', '/synthetic/local/chromium']) {
  test(`initial permitted local launch preserves options and cleans up after a controlled failure (${executablePath ? 'explicit' : 'managed'})`, async t => {
    const before = environment(t, {CHROMIUM_PATH: executablePath});
    const marker = Error('offline page control stops before input');
    const calls = [];
    await assert.rejects(() => probeCanvas({
      startServer: async directory => {
        assert.equal(directory, process.cwd());
        calls.push('server');
        return {address: () => ({port: 32001}), close: callback => { calls.push('server-close'); callback(); }};
      },
      launch: async options => {
        calls.push('launch');
        assert.deepEqual(options, {headless: true, chromiumSandbox: true,
          ...(executablePath ? {executablePath} : {})});
        return {newPage: async options => {
          assert.deepEqual(options, {viewport: {width: 1200, height: 800}});
          throw marker;
        }, close: async () => { calls.push('browser-close'); }};
      },
    }), error => error === marker);
    assert.deepEqual(calls, ['server', 'launch', 'browser-close', 'server-close']);
    assert.ok(isDeepStrictEqual({...process.env}, before), 'the full caller environment must stay unchanged');
  });
}

test('initial entry rechecks the parent precondition immediately before launch', async t => {
  const before = environment(t);
  const control = deniedCalls();
  let closed = false;
  await assert.rejects(() => probeCanvas({...control, startServer: async () => {
    // Model a change during the asynchronous server setup; never launch a browser.
    process.env.SELENIUM_REMOTE_HEADERS = syntheticValue;
    return {address: () => ({port: 32001}), close: callback => { closed = true; callback(); }};
  }}), {message: 'Local browser launch requires unset environment names: SELENIUM_REMOTE_HEADERS'});
  assert.deepEqual(control.calls, {launcher: 0, network: 0, clipboard: 0});
  assert.equal(closed, true);
  assert.ok(isDeepStrictEqual({...process.env}, {...before, SELENIUM_REMOTE_HEADERS: syntheticValue}),
    'the guard must preserve even a concurrent caller environment change');
});

test('initial local launcher failure still closes its fixture server', async t => {
  const before = environment(t);
  const marker = Error('offline launcher failure');
  let closed = false;
  await assert.rejects(() => probeCanvas({
    startServer: async () => ({address: () => ({port: 32001}), close: callback => { closed = true; callback(); }}),
    launch: async () => { throw marker; },
  }), error => error === marker);
  assert.equal(closed, true);
  assert.ok(isDeepStrictEqual({...process.env}, before), 'the full caller environment must stay unchanged');
});

function localClipboard(t, version = '141.0.7390.37', arguments_ = ['--headless', '--ozone-platform=headless']) {
  const before = environment(t, {DISPLAY: syntheticValue, WAYLAND_DISPLAY: syntheticValue,
    XAUTHORITY: syntheticValue, CHROMIUM_PATH: '/synthetic/ignored/chromium'});
  const calls = [];
  const browser = {
    version: () => version,
    close: async () => { calls.push('browser-close'); },
    newBrowserCDPSession: async () => {
      calls.push('cdp');
      return {send: async command => {
        assert.equal(command, 'Browser.getBrowserCommandLine');
        return {arguments: arguments_};
      }, detach: async () => { calls.push('detach'); }};
    },
    newContext: async () => { throw Error('context must not be reached in this control'); },
  };
  const launch = async options => {
    calls.push('launch');
    const expectedEnv = {...before};
    for (const name of ['DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY']) delete expectedEnv[name];
    assert.ok(isDeepStrictEqual(options, {headless: true, chromiumSandbox: true, env: expectedEnv,
      args: ['--ozone-platform=headless']}), 'clipboard local launch options must remain exact');
    assert.ok(options.env !== process.env, 'display filtering must use a distinct environment object');
    return browser;
  };
  return {before, calls, browser, launch};
}

test('clipboard keeps managed launch options, version gate and cleanup before clipboard setup', async t => {
  const control = localClipboard(t, 'synthetic-uninspected-version');
  const result = await probeClipboard(origin, control);
  assert.equal(result.result, 'unavailable');
  if (process.platform === 'linux') assert.match(result.reason, /no clipboard calls made/);
  assert.deepEqual(control.calls, process.platform === 'linux' ? ['launch', 'browser-close'] : []);
  assert.ok(isDeepStrictEqual({...process.env}, control.before), 'the full caller environment must stay unchanged');
});

for (const arguments_ of [
  ['--headless'], ['--ozone-platform=headless'], ['--headless', '--ozone-platform=headless', '--no-sandbox'],
]) {
  test(`clipboard rejects unisolated effective browser flags (${arguments_.join(', ')})`, async t => {
    const control = localClipboard(t, '141.0.7390.37', arguments_);
    if (process.platform === 'linux') {
      await assert.rejects(() => probeClipboard(origin, control), {code: 'ERR_ASSERTION'});
      assert.deepEqual(control.calls, ['launch', 'cdp', 'browser-close']);
    } else {
      assert.equal((await probeClipboard(origin, control)).result, 'unavailable');
      assert.deepEqual(control.calls, []);
    }
    assert.ok(isDeepStrictEqual({...process.env}, control.before), 'the full caller environment must stay unchanged');
  });
}

test('permitted clipboard launch retains isolation, context network controls and failure cleanup', async t => {
  const control = localClipboard(t);
  const marker = Error('offline page control stops before clipboard APIs');
  const diagnostic = t.mock.method(console, 'error', () => {});
  control.browser.newContext = async options => {
    control.calls.push('context');
    assert.deepEqual(options, {viewport: {width: 1200, height: 800}, serviceWorkers: 'block'});
    return {
      setDefaultTimeout: timeout => assert.equal(timeout, 10000),
      grantPermissions: async (permissions, scope) => {
        assert.deepEqual(permissions, ['clipboard-read', 'clipboard-write']);
        assert.deepEqual(scope, {origin});
      },
      route: async (pattern, handler) => {
        assert.equal(pattern, '**/*');
        for (const [url, permitted] of [[`${origin}/app.js`, true], ['http://example.invalid/asset.js', false],
          ['http://127.0.0.1:32002/app.js', false]]) {
          let action;
          await handler({request: () => ({url: () => url}),
            continue: () => { action = 'continue'; }, abort: () => { action = 'abort'; }});
          assert.equal(action, permitted ? 'continue' : 'abort');
        }
      },
      on: event => assert.equal(event, 'page'),
      newPage: async () => { throw marker; },
      close: async () => { control.calls.push('context-close'); },
    };
  };
  if (process.platform === 'linux') {
    await assert.rejects(() => probeClipboard(origin, control), error => error === marker);
    assert.deepEqual(control.calls, ['launch', 'cdp', 'detach', 'context', 'context-close', 'browser-close']);
    assert.equal(diagnostic.mock.callCount(), 1);
    const [message] = diagnostic.mock.calls[0].arguments;
    assert.equal(message.includes(syntheticValue), false);
    assert.equal(JSON.parse(message).clipboardFailure.message, marker.message);
  } else {
    assert.equal((await probeClipboard(origin, control)).result, 'unavailable');
    assert.deepEqual(control.calls, []);
  }
  assert.ok(isDeepStrictEqual({...process.env}, control.before), 'the full caller environment must stay unchanged');
});
