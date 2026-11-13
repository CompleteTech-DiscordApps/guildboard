/** Research fixture only. No HTTP listener, Discord client, database or runtime import. */
import { createHash, generateKeyPairSync, sign, verify } from 'node:crypto';
import { pathToFileURL } from 'node:url';

export const FIXTURE = Object.freeze({
  now: 1803516000, maxAgeSeconds: 300, futureSkewSeconds: 30, maxBodyBytes: 4096,
  app: '100000000000000001', guild: '200000000000000001',
  channel: '300000000000000001', actor: '400000000000000001',
  command: '500000000000000001', interaction: '600000000000000001',
});
const denied = reason => ({ ok: false, reason });
const hash = data => createHash('sha256').update(data).digest('hex');
const decimal = value => typeof value === 'string' && /^[1-9][0-9]{0,19}$/.test(value)
  && BigInt(value) <= 18446744073709551615n;

export function keys() {
  // Fresh, in-memory synthetic keys; private material is never exported or logged.
  return generateKeyPairSync('ed25519');
}

export function payload(overrides = {}) {
  return { id: FIXTURE.interaction, application_id: FIXTURE.app, type: 2, version: 1,
    context: 0, guild_id: FIXTURE.guild, channel_id: FIXTURE.channel,
    authorizing_integration_owners: { '0': FIXTURE.guild },
    member: { user: { id: FIXTURE.actor }, roles: [], permissions: '32' },
    app_permissions: '0', data: { id: FIXTURE.command, name: 'board-lock', type: 1 },
    ...overrides };
}

export function envelope(privateKey, value = payload(), timestamp = String(FIXTURE.now)) {
  const raw = Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value));
  const bytes = Buffer.concat([Buffer.from(timestamp, 'ascii'), raw]);
  return { raw, timestamp, signature: sign(null, bytes, privateKey).toString('hex') };
}

export function authenticate(request, publicKey, now = FIXTURE.now) {
  // A real server must enforce the byte bound while streaming, preserve raw bytes,
  // reject duplicate headers before normalization and disable unreviewed transforms.
  if (!Buffer.isBuffer(request.raw)) return denied('raw_body_required');
  if (request.raw.length > FIXTURE.maxBodyBytes) return denied('body_too_large');
  if (typeof request.signature !== 'string' || !/^[0-9a-fA-F]{128}$/.test(request.signature)
      || typeof request.timestamp !== 'string' || !/^[0-9]{1,12}$/.test(request.timestamp)) {
    return denied('malformed_headers');
  }
  try {
    if (publicKey.type !== 'public' || publicKey.asymmetricKeyType !== 'ed25519') {
      return denied('invalid_configured_key');
    }
    if (!verify(null, Buffer.concat([Buffer.from(request.timestamp, 'ascii'), request.raw]),
      publicKey, Buffer.from(request.signature, 'hex'))) return denied('bad_signature');
  } catch {
    return denied('invalid_configured_key');
  }
  const timestamp = Number(request.timestamp);
  if (!Number.isSafeInteger(now) || now - timestamp > FIXTURE.maxAgeSeconds
      || timestamp - now > FIXTURE.futureSkewSeconds) return denied('outside_fixture_window');
  let value;
  try {
    // Fatal UTF-8 decoding avoids lossy replacement before parsing. The candidate
    // production codec must additionally reject duplicate JSON keys (not modeled).
    value = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(request.raw));
  } catch {
    return denied('invalid_json');
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || value.application_id !== FIXTURE.app || value.version !== 1
      || !decimal(value.id)) return denied('wrong_application_or_envelope');
  return { ok: true, value, rawDigest: hash(request.raw) };
}

export function provenance(value) {
  if (value.type === 1) return 'ping';
  if (value.type !== 2 || value.context !== 0 || !decimal(value.guild_id)
      || !decimal(value.channel_id) || !decimal(value.member?.user?.id)
      || value.user !== undefined
      || value.authorizing_integration_owners?.['0'] !== value.guild_id) return 'unsupported_context';
  if (value.guild_id !== FIXTURE.guild || value.channel_id !== FIXTURE.channel
      || value.member.user.id !== FIXTURE.actor) return 'foreign_scope';
  if (value.data?.id !== FIXTURE.command || value.data?.type !== 1
      || value.data?.name !== 'board-lock') return 'unknown_command';
  return 'guild_command';
}

export function state() {
  return { read: true, write: true, currentGeneration: 1, expectedGeneration: 1,
    activeLineage: 'current', commandLineage: 'current', effects: 0, audit: 0,
    receipts: new Map(), invocationBindings: new Map() };
}

export function dispatch(request, publicKey, authority, options = {}) {
  const authenticated = authenticate(request, publicKey, options.now ?? FIXTURE.now);
  if (!authenticated.ok) return authenticated;
  const { value, rawDigest } = authenticated;
  const scope = provenance(value);
  if (scope === 'ping') return { ok: true, result: 'pong' };
  if (scope !== 'guild_command') return denied(scope);
  // Current identity/read gate precedes revealing receipt or digest existence.
  if (!authority.read) return denied('current_read_denied');
  const transportKey = `${value.application_id}/${value.id}`;
  let binding = authority.invocationBindings.get(transportKey);
  if (binding && binding.rawDigest !== rawDigest) return denied('interaction_id_conflict');
  // Capture intent at first authenticated, provenance-valid, readable admission,
  // including a later write denial. This is anti-replay metadata, not a receipt
  // or product effect. Never derive a retry's lineage/fence from mutable state.
  // Production still needs accepted durable admission and operation contracts.
  if (!binding) {
    binding = Object.freeze({ rawDigest, lineage: authority.commandLineage,
      expectedGeneration: authority.expectedGeneration,
      operationKey: `${value.guild_id}/fixture-board/${authority.commandLineage}/${value.member.user.id}/${value.id}` });
    authority.invocationBindings.set(transportKey, binding);
  }
  const receipt = authority.receipts.get(binding.operationKey);
  if (receipt) return { ok: true, result: 'existing_receipt', receipt };
  if (binding.lineage !== authority.activeLineage) return denied('lineage_changed');
  if (!authority.write) return denied('current_write_denied');
  if (binding.expectedGeneration !== authority.currentGeneration) return denied('policy_stale');
  // Only a hypothetical synchronous critical section. This is NOT a DB transaction
  // or multi-worker fence, and these receipts are NOT durable.
  const accepted = { revision: authority.effects + 1, lineage: binding.lineage };
  authority.effects += 1;
  authority.audit += 1;
  authority.receipts.set(binding.operationKey, accepted);
  return { ok: true, result: 'new_receipt', receipt: accepted };
}

export function report() {
  const pair = keys();
  const request = envelope(pair.privateKey);
  const authority = state();
  const first = dispatch(request, pair.publicKey, authority);
  const duplicate = dispatch(request, pair.publicKey, authority);
  authority.write = false;
  const readableReceiptAfterWriteLoss = dispatch(request, pair.publicKey, authority);
  authority.read = false;
  const unreadableReceipt = dispatch(request, pair.publicKey, authority);
  const tampered = { ...request, raw: Buffer.concat([request.raw, Buffer.from(' ')]) };
  return { schema: 't8-interaction-experiment-v1', node: process.version,
    openssl: process.versions.openssl, platform: process.platform, arch: process.arch,
    classification: 'real local crypto; hypothetical in-memory authorization and receipts',
    fixture: { maxAgeSeconds: FIXTURE.maxAgeSeconds, futureSkewSeconds: FIXTURE.futureSkewSeconds,
      maxBodyBytes: FIXTURE.maxBodyBytes, windowsAreProposedSynthetic: true },
    first: first.result, duplicate: duplicate.result,
    readableReceiptAfterWriteLoss: readableReceiptAfterWriteLoss.result,
    unreadableReceipt: unreadableReceipt.reason,
    tamper: authenticate(tampered, pair.publicKey).reason,
    effects: authority.effects, audit: authority.audit,
    realDiscordDelivery: false, registeredAppConfiguration: false, databaseVerification: false };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.stdout.write(`${JSON.stringify(report(), null, 2)}\n`);
}
