// Fixture dependency regressions, not editor/server or exhaustive security acceptance.
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createRequire} from 'node:module';
import test from 'node:test';
import {pathToFileURL} from 'node:url';

function consumerModule(consumer, dependency) {
  const require = createRequire(new URL(`./node_modules/${consumer}/package.json`, import.meta.url));
  return pathToFileURL(require.resolve(dependency)).href;
}

function isolated(program) {
  // A vulnerable generator must not hang the test runner; only this owned child
  // is terminated on timeout. Prototype probes also stay inside that child.
  const child = spawnSync(process.execPath, ['--input-type=module', '--eval', program], {
    encoding: 'utf8', timeout: 3000,
  });
  assert.equal(child.error, undefined, 'dependency probe must finish within 3 seconds');
  assert.equal(child.status, 0, child.stderr);
  assert.equal(child.stderr, '');
  assert.equal(child.stdout, 'DEPENDENCY_CHECK_PASSED');
}

for (const consumer of ['@excalidraw/excalidraw', '@excalidraw/mermaid-to-excalidraw']) {
  test(`${consumer} resolves a Nano ID with bounded zero/negative-size behavior`, () => {
    const main = consumerModule(consumer, 'nanoid');
    const nonSecure = consumerModule(consumer, 'nanoid/non-secure');
    isolated(`
      import assert from 'node:assert/strict';
      const {nanoid, customAlphabet} = await import(${JSON.stringify(main)});
      const nonSecure = await import(${JSON.stringify(nonSecure)});
      assert.equal(customAlphabet('abc', 0)(), '');
      assert.equal(nonSecure.nanoid(-1), '');
      assert.equal(nonSecure.customAlphabet('abc', -1)(), '');
      assert.match(customAlphabet('abc', 12)(), /^[abc]{12}$/);
      assert.equal(nanoid(21).length, 21);
      process.stdout.write('DEPENDENCY_CHECK_PASSED');
    `);
  });
}

test('lodash-es rejects template imports that are not identifiers', () => {
  const moduleUrl = consumerModule('@chevrotain/gast', 'lodash-es');
  isolated(`
    import assert from 'node:assert/strict';
    const {template} = await import(${JSON.stringify(moduleUrl)});
    assert.throws(() => template('safe', {imports: {'argument = 1': undefined}}), /Invalid.*imports/);
    assert.equal(template('hello <%= name %>')({name: 'fixture'}), 'hello fixture');
    process.stdout.write('DEPENDENCY_CHECK_PASSED');
  `);
});

test('lodash-es array-wrapped paths cannot delete a prototype property', () => {
  const moduleUrl = consumerModule('@chevrotain/gast', 'lodash-es');
  isolated(`
    import assert from 'node:assert/strict';
    const {unset} = await import(${JSON.stringify(moduleUrl)});
    Object.defineProperty(Object.prototype, 'canvasResearchSentinel', {value: 1, configurable: true});
    try {
      unset({}, [['__proto__'], ['canvasResearchSentinel']]);
      assert.equal(Object.prototype.canvasResearchSentinel, 1);
      const own = {nested: {value: 1}};
      assert.equal(unset(own, ['nested', 'value']), true);
      assert.deepEqual(own, {nested: {}});
    } finally { delete Object.prototype.canvasResearchSentinel; }
    process.stdout.write('DEPENDENCY_CHECK_PASSED');
  `);
});

test('KaTeX ignores inherited trust and keeps its renderToString API', async () => {
  const {default: katex} = await import(consumerModule('mermaid', 'katex'));
  const expression = String.raw`\href{https://example.invalid/fixture}{x}`;
  const inherited = Object.create({trust: true});
  inherited.throwOnError = false;
  assert.equal(katex.renderToString(expression, inherited).includes('<a '), false);
  assert.equal(katex.renderToString(expression, {trust: true}).includes('<a '), true);
  assert.match(katex.renderToString('x^2', {throwOnError: true}), /class="katex"/);
});
