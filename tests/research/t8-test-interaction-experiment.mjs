import test from 'node:test';
import assert from 'node:assert/strict';
import { createPublicKey, generateKeyPairSync, verify } from 'node:crypto';
import { FIXTURE, keys, payload, envelope, authenticate, dispatch, state, report }
  from '../../scripts/research/t8-interaction-experiment.mjs';

const pair = keys();
const signed = (value, timestamp) => envelope(pair.privateKey, value, timestamp);
function deniedWithoutEffects(request, reason, authority = state(), options = {}) {
  const before = structuredClone({ effects: authority.effects, audit: authority.audit,
    receipts: [...authority.receipts], bindings: [...authority.invocationBindings] });
  assert.deepEqual(dispatch(request, pair.publicKey, authority, options), { ok: false, reason });
  assert.deepEqual({ effects: authority.effects, audit: authority.audit,
    receipts: [...authority.receipts], bindings: [...authority.invocationBindings] }, before);
}

// Valid readable admission may retain anti-replay intent even when no command
// commits. Authentication/provenance/read denials use the stricter helper above.
function admittedWithoutCommandEffects(request, reason, authority = state()) {
  const before = structuredClone({ effects: authority.effects, audit: authority.audit,
    receipts: [...authority.receipts] });
  const priorBindings = authority.invocationBindings.size;
  assert.deepEqual(dispatch(request, pair.publicKey, authority), { ok: false, reason });
  assert.deepEqual({ effects: authority.effects, audit: authority.audit,
    receipts: [...authority.receipts] }, before);
  assert.equal(authority.invocationBindings.size, priorBindings + 1);
  assert.ok(Object.isFrozen([...authority.invocationBindings.values()].at(-1)));
  deniedWithoutEffects(request, reason, authority);
}

test('independent RFC 8032 section 7.1 public known-answer vector and mutation', () => {
  // Published PUBLIC test vector only; no private test vector or app credential.
  const publicBytes = Buffer.from('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a', 'hex');
  const publicKey = createPublicKey({ key: { kty: 'OKP', crv: 'Ed25519',
    x: publicBytes.toString('base64url') }, format: 'jwk' });
  const signature = Buffer.from('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155'
    + '5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b', 'hex');
  assert.equal(verify(null, Buffer.alloc(0), publicKey, signature), true);
  assert.equal(verify(null, Buffer.from('x'), publicKey, signature), false);
});

test('actual Ed25519 accepts synthetic timestamp plus exact raw UTF-8 body', () => {
  const request = signed(payload({ locale: '日本語' }));
  assert.equal(authenticate(request, pair.publicKey).ok, true);
  const authority = state();
  assert.equal(dispatch(request, pair.publicKey, authority).result, 'new_receipt');
  assert.equal(authority.effects, 1);
  assert.equal(authority.audit, 1);
});

test('tamper body, timestamp and signature each deny without effects', () => {
  const request = signed();
  deniedWithoutEffects({ ...request, raw: Buffer.concat([request.raw, Buffer.from(' ')]) }, 'bad_signature');
  deniedWithoutEffects({ ...request, timestamp: String(FIXTURE.now - 1) }, 'bad_signature');
  const changed = (request.signature[0] === '0' ? '1' : '0') + request.signature.slice(1);
  deniedWithoutEffects({ ...request, signature: changed }, 'bad_signature');
});

test('parsed and reserialized semantically equal JSON is not the signed body', () => {
  const raw = Buffer.from(JSON.stringify(payload(), null, 2));
  const request = signed(raw);
  assert.equal(authenticate(request, pair.publicKey).ok, true);
  deniedWithoutEffects({ ...request, raw: Buffer.from(JSON.stringify(JSON.parse(raw))) }, 'bad_signature');
});

test('wrong key and wrong algorithm cannot authenticate', () => {
  const request = signed();
  assert.equal(authenticate(request, keys().publicKey).reason, 'bad_signature');
  assert.equal(authenticate(request, generateKeyPairSync('ec', { namedCurve: 'P-256' }).publicKey).reason,
    'invalid_configured_key');
  assert.equal(authenticate(request, {}).reason, 'invalid_configured_key');
});

test('missing, malformed, duplicate-represented and short headers deny', () => {
  for (const signature of [undefined, [], ['00', '00'], 'f'.repeat(127), 'z'.repeat(128), '']) {
    deniedWithoutEffects({ ...signed(), signature }, 'malformed_headers');
  }
  for (const timestamp of [undefined, ['1', '2'], '-1', '1e9', '1.5', '1'.repeat(13)]) {
    deniedWithoutEffects({ ...signed(), timestamp }, 'malformed_headers');
  }
});

test('body type, size, malformed JSON and invalid UTF-8 deny', () => {
  deniedWithoutEffects({ ...signed(), raw: '{}' }, 'raw_body_required');
  deniedWithoutEffects(signed(Buffer.alloc(FIXTURE.maxBodyBytes + 1)), 'body_too_large');
  deniedWithoutEffects(signed(Buffer.from('{')), 'invalid_json');
  deniedWithoutEffects(signed(Buffer.from([0xff])), 'invalid_json');
});

test('signed stale/future requests deny; synthetic exact window edges accept', () => {
  deniedWithoutEffects(signed(payload(), String(FIXTURE.now - FIXTURE.maxAgeSeconds - 1)), 'outside_fixture_window');
  deniedWithoutEffects(signed(payload(), String(FIXTURE.now + FIXTURE.futureSkewSeconds + 1)), 'outside_fixture_window');
  for (const offset of [-FIXTURE.maxAgeSeconds, FIXTURE.futureSkewSeconds]) {
    assert.equal(authenticate(signed(payload(), String(FIXTURE.now + offset)), pair.publicKey).ok, true);
  }
});

test('wrong application, numeric ID, unknown version and non-object payload deny', () => {
  for (const value of [payload({ application_id: '999' }), payload({ id: 123 }), payload({ version: 2 }),
    payload({ id: '18446744073709551616' }), [], null]) {
    deniedWithoutEffects(signed(value), 'wrong_application_or_envelope');
  }
});

test('signed PING has no board side effects', () => {
  const authority = state();
  assert.deepEqual(dispatch(signed(payload({ type: 1 })), pair.publicKey, authority), { ok: true, result: 'pong' });
  assert.equal(authority.effects, 0);
  assert.equal(authority.audit, 0);
});

test('signed user install, DM, mismatched install owner or missing member deny', () => {
  for (const override of [{ context: 1 }, { member: undefined }, { user: { id: FIXTURE.actor } },
    { authorizing_integration_owners: { '1': FIXTURE.actor } },
    { authorizing_integration_owners: { '0': '999' } }]) {
    deniedWithoutEffects(signed(payload(override)), 'unsupported_context');
  }
});

test('authentic foreign guild/channel/member and unknown command deny', () => {
  for (const override of [{ guild_id: '999', authorizing_integration_owners: { '0': '999' } },
    { channel_id: '999' }, { member: { user: { id: '999' } } }]) {
    deniedWithoutEffects(signed(payload(override)), 'foreign_scope');
  }
  deniedWithoutEffects(signed(payload({ data: { id: '999', name: 'board-lock', type: 1 } })), 'unknown_command');
});

test('Discord Administrator/app permission strings do not override application denial', () => {
  const request = signed(payload({ member: { user: { id: FIXTURE.actor }, permissions: '8' },
    app_permissions: '8' }));
  admittedWithoutCommandEffects(request, 'current_write_denied', { ...state(), write: false });
  admittedWithoutCommandEffects(request, 'policy_stale', { ...state(), currentGeneration: 2 });
});

test('identical retry returns receipt once; signed same-ID different bytes conflicts', () => {
  const authority = state();
  const request = signed();
  assert.equal(dispatch(request, pair.publicKey, authority).result, 'new_receipt');
  assert.equal(dispatch(request, pair.publicKey, authority).result, 'existing_receipt');
  deniedWithoutEffects(signed(payload({ locale: 'fr' })), 'interaction_id_conflict', authority);
  assert.equal(authority.effects, 1);
  assert.equal(authority.audit, 1);
});

test('retired-lineage readable receipt precedes current write and lineage checks', () => {
  const authority = state();
  const request = signed();
  dispatch(request, pair.publicKey, authority);
  authority.activeLineage = 'restored';
  authority.write = false;
  assert.equal(dispatch(request, pair.publicKey, authority).result, 'existing_receipt');
  admittedWithoutCommandEffects(signed(payload({ id: '600000000000000002' })), 'lineage_changed', authority);
  assert.equal(authority.effects, 1);
});

test('old invocation stays bound to its receipt after a new-lineage command commits', () => {
  const authority = state();
  const oldRequest = signed();
  const original = dispatch(oldRequest, pair.publicKey, authority);
  assert.equal(original.result, 'new_receipt');
  authority.activeLineage = 'restored';
  authority.commandLineage = 'restored';
  const fresh = signed(payload({ id: '600000000000000002' }));
  const restored = dispatch(fresh, pair.publicKey, authority);
  assert.equal(restored.result, 'new_receipt');
  assert.equal(restored.receipt.lineage, 'restored');
  const retry = dispatch(oldRequest, pair.publicKey, authority);
  assert.equal(retry.result, 'existing_receipt');
  assert.strictEqual(retry.receipt, original.receipt);
  assert.equal(retry.receipt.lineage, 'current');
  assert.equal(authority.effects, 2);
  assert.equal(authority.audit, 2);
  assert.equal(authority.receipts.size, 2);
  assert.equal(authority.invocationBindings.size, 2);
  authority.write = false;
  assert.strictEqual(dispatch(oldRequest, pair.publicKey, authority).receipt, original.receipt);
  deniedWithoutEffects(signed(payload({ locale: 'fr' })), 'interaction_id_conflict', authority);
  const tampered = { ...oldRequest, raw: Buffer.concat([oldRequest.raw, Buffer.from(' ')]) };
  deniedWithoutEffects(tampered, 'bad_signature', authority);
  authority.read = false;
  deniedWithoutEffects(oldRequest, 'current_read_denied', authority);
  deniedWithoutEffects(signed(payload({ locale: 'fr' })), 'current_read_denied', authority);
});

test('denied first invocations cannot rebase onto a restored lineage', () => {
  for (const reason of ['current_write_denied', 'policy_stale', 'lineage_changed']) {
    const authority = state();
    if (reason === 'current_write_denied') authority.write = false;
    if (reason === 'policy_stale') authority.expectedGeneration = 0;
    if (reason === 'lineage_changed') authority.activeLineage = 'restored';
    const oldRequest = signed();
    admittedWithoutCommandEffects(oldRequest, reason, authority);
    assert.equal(authority.effects, 0);
    assert.equal(authority.audit, 0);
    assert.equal(authority.receipts.size, 0);
    authority.write = true;
    authority.expectedGeneration = authority.currentGeneration;
    authority.activeLineage = authority.commandLineage = 'restored';
    const fresh = signed(payload({ id: '600000000000000002' }));
    assert.equal(dispatch(fresh, pair.publicKey, authority).result, 'new_receipt');
    deniedWithoutEffects(oldRequest, 'lineage_changed', authority);
    deniedWithoutEffects(signed(payload({ locale: 'fr' })), 'interaction_id_conflict', authority);
    assert.equal(authority.effects, 1);
    assert.equal(authority.audit, 1);
    assert.equal(authority.receipts.size, 1);
    assert.equal(authority.invocationBindings.size, 2);
    authority.read = false;
    deniedWithoutEffects(oldRequest, 'current_read_denied', authority);
    deniedWithoutEffects(signed(payload({ locale: 'fr' })), 'current_read_denied', authority);
  }
});

test('denied invocation retains digest and original policy fence within one lineage', () => {
  const authority = state();
  authority.expectedGeneration = 0;
  const request = signed();
  admittedWithoutCommandEffects(request, 'policy_stale', authority);
  authority.expectedGeneration = authority.currentGeneration;
  deniedWithoutEffects(request, 'policy_stale', authority);
  deniedWithoutEffects(signed(payload({ locale: 'fr' })), 'interaction_id_conflict', authority);
  assert.equal(authority.effects, 0);
  assert.equal(authority.audit, 0);
  assert.equal(authority.receipts.size, 0);
});

test('same-lineage retry after a transient write denial uses its original binding', () => {
  const authority = state();
  authority.write = false;
  const request = signed();
  admittedWithoutCommandEffects(request, 'current_write_denied', authority);
  const originalBinding = [...authority.invocationBindings.values()][0];
  authority.write = true;
  assert.equal(dispatch(request, pair.publicKey, authority).result, 'new_receipt');
  assert.strictEqual([...authority.invocationBindings.values()][0], originalBinding);
  assert.equal(authority.effects, 1);
  assert.equal(authority.audit, 1);
  assert.equal(authority.receipts.size, 1);
  assert.equal(dispatch(request, pair.publicKey, authority).result, 'existing_receipt');
});

test('current read denial conceals both prior receipt and digest mismatch', () => {
  const authority = state();
  dispatch(signed(), pair.publicKey, authority);
  authority.read = false;
  deniedWithoutEffects(signed(), 'current_read_denied', authority);
  deniedWithoutEffects(signed(payload({ locale: 'fr' })), 'current_read_denied', authority);
});

test('negative control without verification accepts tampered bytes; candidate denies', () => {
  const request = signed();
  const tampered = { ...request, raw: Buffer.concat([request.raw, Buffer.from(' ')]) };
  assert.equal(JSON.parse(tampered.raw).id, FIXTURE.interaction); // deliberately unsafe parse-only control
  deniedWithoutEffects(tampered, 'bad_signature');
});

test('negative control checking write before receipt loses readable historical result', () => {
  const authority = state();
  const request = signed();
  dispatch(request, pair.publicKey, authority);
  authority.write = false;
  assert.equal(authority.write ? 'would_dispatch' : 'denied', 'denied'); // unsafe order
  assert.equal(dispatch(request, pair.publicKey, authority).result, 'existing_receipt');
});

test('report is deterministic across fresh ephemeral signing keys', () => {
  assert.deepEqual(report(), report());
  assert.equal(report().realDiscordDelivery, false);
  assert.equal(report().effects, 1);
});
