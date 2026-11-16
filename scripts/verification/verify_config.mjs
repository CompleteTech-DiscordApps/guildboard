// Independent contract acceptance: run after the config package has been built.
import assert from 'node:assert/strict';
import { parseConfig } from '../../packages/config/dist/src/index.js';
import fs from 'node:fs';
import net from 'node:net';
import { syncBuiltinESMExports } from 'node:module';

const valid = Object.freeze({ PORT: '3000', NODE_ENV: 'test', DATABASE_URL: 'mysql://fixture:password-marker@localhost/guild', DISCORD_CLIENT_ID: '900719925474099312345', SESSION_SECRET: 'secret-marker-01234567890123456789' });
const fields = ['DATABASE_URL', 'DISCORD_CLIENT_ID', 'NODE_ENV', 'PORT', 'SESSION_SECRET'];
let assertions = 0;
let scenarios = 0;
let current = 'setup';
const check = (actual, expected) => { assertions++; assert.deepStrictEqual(actual, expected); };
const expectedSuccess = (env, port = Number(env.PORT)) => ({ ok: true, value: { port, nodeEnv: env.NODE_ENV, databaseUrl: env.DATABASE_URL, discordClientId: env.DISCORD_CLIENT_ID, sessionSecret: env.SESSION_SECRET } });
const failure = keys => ({ ok: false, error: { code: 'CONFIG_INVALID', invalidKeys: keys } });
const run = (name, env, expected) => {
  current = name; scenarios++;
  const before = { ...env };
  const result = parseConfig(env);
  check(result, expected);
  check(env, before);
};

// Trap common observable effects while exercising both success and failure paths.
const original = { log: console.log, error: console.error, warn: console.warn, exit: process.exit, write: fs.writeFileSync, read: fs.readFileSync, connect: net.connect, createConnection: net.createConnection };
let effects = 0;
const trap = () => { effects++; throw new Error('unexpected side effect'); };
const originalEnv = process.env;
const environment = { ...originalEnv };
try {
  console.log = console.error = console.warn = process.exit = trap;
  fs.writeFileSync = fs.readFileSync = net.connect = net.createConnection = trap;
  syncBuiltinESMExports();
  process.env = new Proxy(environment, { get: trap, set: trap, deleteProperty: trap, ownKeys: trap });
  run('valid-frozen', valid, expectedSuccess(valid));
  for (let n = 0; n <= 65536; n++) {
    for (const prefix of ['', '000']) {
      const env = { ...valid, PORT: prefix + n };
      run('decimal-port-sweep', env, n >= 1 && n <= 65535 ? expectedSuccess(env, n) : failure(['PORT']));
    }
  }
  for (const port of ['', '-1', '+1', ' 1', '1 ', '1.0', '1e2', '0x10', '１２', '999999999999999999999999999999999999999']) run('invalid-port', { ...valid, PORT: port }, failure(['PORT']));
  for (const key of fields) {
    const env = { ...valid }; delete env[key];
    run('missing-field', env, failure([key]));
    run('empty-field', { ...valid, [key]: '' }, failure([key]));
  }
  run('all-missing', {}, failure(fields));
  run('aggregate-and-redact', { ...valid, PORT: 'bad', NODE_ENV: 'TEST', DATABASE_URL: 'https://fixture:password-marker@host/db', DISCORD_CLIENT_ID: '1x', SESSION_SECRET: 'short-secret-marker' }, failure(fields));
  for (const value of ['development', 'test', 'production']) { const env = { ...valid, NODE_ENV: value }; run('enum-valid', env, expectedSuccess(env)); }
  for (const value of ['Production', ' test', 'testing']) run('enum-invalid', { ...valid, NODE_ENV: value }, failure(['NODE_ENV']));
  for (const value of ['mysql://host/db', 'mysql://fixture:password-marker@host/db']) { const env = { ...valid, DATABASE_URL: value }; run('url-valid', env, expectedSuccess(env)); }
  for (const value of ['not a url', 'https://host/db', 'mysql:///db', 'mysql://host/', 'mysql://host']) run('url-invalid', { ...valid, DATABASE_URL: value }, failure(['DATABASE_URL']));
  for (const value of ['0', '000123', '900719925474099312345']) { const env = { ...valid, DISCORD_CLIENT_ID: value }; run('id-valid', env, expectedSuccess(env)); }
  for (const value of ['-1', '1.0', '1e2', '１２', '1\n']) run('id-invalid', { ...valid, DISCORD_CLIENT_ID: value }, failure(['DISCORD_CLIENT_ID']));
  for (const value of ['x'.repeat(32), ' '.repeat(31) + 'x']) { const env = { ...valid, SESSION_SECRET: value }; run('secret-valid', env, expectedSuccess(env)); }
  for (const value of ['x'.repeat(31), ' '.repeat(32), '\n'.repeat(32)]) run('secret-invalid', { ...valid, SESSION_SECRET: value }, failure(['SESSION_SECRET']));
  const extra = { ...valid, UNRELATED_SECRET: 'unrelated-marker' };
  run('unrelated', extra, expectedSuccess(extra));
  run('caller-continuation', valid, expectedSuccess(valid));
  process.env = originalEnv;
  current = 'effect-check'; check(effects, 0); check({ ...process.env }, environment);
} catch {
  process.env = originalEnv;
  Object.assign(console, { log: original.log, error: original.error, warn: original.warn });
  process.exit = original.exit; fs.writeFileSync = original.write; fs.readFileSync = original.read; net.connect = original.connect; net.createConnection = original.createConnection; syncBuiltinESMExports();
  console.error(JSON.stringify({ status: 'failed', scenario: current, scenarios, assertions }));
  process.exitCode = 1;
}
if (!process.exitCode) {
  Object.assign(console, { log: original.log, error: original.error, warn: original.warn });
  process.exit = original.exit; fs.writeFileSync = original.write; fs.readFileSync = original.read; net.connect = original.connect; net.createConnection = original.createConnection; syncBuiltinESMExports();
  console.log(JSON.stringify({ status: 'passed', scenarios, assertions, effects }));
}
