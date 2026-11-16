import fs from 'node:fs';
import path from 'node:path';
import { builtinModules } from 'node:module';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const graph = {
  'apps/activity': ['packages/contracts', 'packages/canvas'],
  'apps/api': ['packages/contracts', 'packages/config', 'packages/auth', 'packages/collaboration'],
  'apps/bot': ['packages/contracts', 'packages/config', 'packages/auth', 'packages/collaboration'],
  'packages/contracts': [],
  'packages/canvas': ['packages/contracts'],
  'packages/auth': ['packages/contracts'],
  'packages/collaboration': ['packages/contracts', 'packages/auth'],
  'packages/config': [],
};
const browser = new Set(['apps/activity', 'packages/canvas', 'packages/contracts']);
const builtins = new Set(builtinModules.map((name) => name.replace(/^node:/, '')));
const owner = (file) => Object.keys(graph).find((key) => file === path.join(root, key) || file.startsWith(path.join(root, key) + path.sep));
const errors = [];
function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    if (entry.name === 'node_modules' || entry.name === 'dist') return [];
    const file = path.join(dir, entry.name);
    if (entry.isSymbolicLink()) { errors.push(`symlink forbidden: ${file}`); return []; }
    return entry.isDirectory() ? walk(file) : /\.[cm]?[jt]sx?$/.test(entry.name) ? [file] : [];
  });
}
for (const group of ['apps', 'packages']) {
  for (const entry of fs.readdirSync(path.join(root, group), { withFileTypes: true })) {
    if (entry.isDirectory() && !graph[`${group}/${entry.name}`]) errors.push(`unknown workspace: ${group}/${entry.name}`);
  }
}
for (const key of Object.keys(graph)) {
  const dir = path.join(root, key);
  const configPath = ts.findConfigFile(dir, ts.sys.fileExists, 'tsconfig.json');
  if (!configPath) { errors.push(`missing tsconfig: ${key}`); continue; }
  const config = ts.readConfigFile(configPath, ts.sys.readFile);
  if (config.error) { errors.push(`invalid tsconfig: ${key}`); continue; }
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, path.dirname(configPath));
  if (parsed.errors.length) { errors.push(`invalid tsconfig: ${key}`); continue; }
  for (const file of walk(dir)) {
    const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    function check(specifier, node) {
      const loc = source.getLineAndCharacterOfPosition(node.getStart(source));
      const fail = (reason) => errors.push(`${path.relative(root, file)}:${loc.line + 1}: ${reason}`);
      if (!specifier || !ts.isStringLiteralLike(specifier)) { fail('nonliteral module specifier'); return; }
      const name = specifier.text;
      if (builtins.has(name.replace(/^node:/, '')) || name.startsWith('node:')) {
        if (browser.has(key)) fail(`server builtin ${name}`);
        return;
      }
      let target;
      if (name.startsWith('@guildboard/')) {
        const packageName = name.split('/')[1];
        target = Object.keys(graph).find((item) => item.split('/')[1] === packageName);
        if (!target) { fail(`unknown workspace ${name}`); return; }
      }
      const resolved = ts.resolveModuleName(name, file, parsed.options, ts.sys).resolvedModule?.resolvedFileName;
      if (resolved && !resolved.includes(`${path.sep}node_modules${path.sep}`)) {
        const resolvedOwner = owner(path.resolve(resolved));
        if (!resolvedOwner) { fail(`module outside known workspace: ${name}`); return; }
        if (target && target !== resolvedOwner) { fail(`workspace resolution mismatch: ${name}`); return; }
        target = resolvedOwner;
      } else if ((name.startsWith('.') || name.startsWith('/') || name.startsWith('#')) && !resolved) {
        fail(`unresolved local module: ${name}`); return;
      } else if (!target && !resolved && Object.keys(parsed.options.paths || {}).some((pattern) => name.startsWith(pattern.split('*')[0]))) {
        fail(`unresolved alias: ${name}`); return;
      }
      if (target && target !== key && !graph[key].includes(target)) fail(`forbidden dependency ${key} -> ${target} (${name})`);
    }
    function visit(node) {
      if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) { if (node.moduleSpecifier) check(node.moduleSpecifier, node); }
      if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) check(node.moduleReference.expression, node);
      if (ts.isImportTypeNode(node) && ts.isLiteralTypeNode(node.argument)) check(node.argument.literal, node);
      if (ts.isCallExpression(node) && (node.expression.kind === ts.SyntaxKind.ImportKeyword || (ts.isIdentifier(node.expression) && node.expression.text === 'require'))) check(node.arguments[0], node);
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
}
if (errors.length) { console.error(errors.join('\n')); process.exitCode = 1; }
else console.log('Workspace boundaries valid');
