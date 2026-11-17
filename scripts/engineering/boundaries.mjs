import fs from "node:fs";
import path from "node:path";
import { builtinModules } from "node:module";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const graph = {
  "apps/activity": ["packages/contracts", "packages/canvas"],
  "apps/api": ["packages/contracts", "packages/config", "packages/auth", "packages/collaboration"],
  "apps/bot": ["packages/contracts", "packages/config", "packages/auth", "packages/collaboration"],
  "packages/contracts": [],
  "packages/canvas": ["packages/contracts"],
  "packages/auth": ["packages/contracts"],
  "packages/collaboration": ["packages/contracts", "packages/auth"],
  "packages/config": [],
};
const browser = new Set(["apps/activity", "packages/canvas", "packages/contracts"]);
const builtins = new Set(builtinModules.map((n) => n.replace(/^node:/, "")));
const keys = Object.keys(graph);
export function checkBoundaries(root) {
  root = path.resolve(root);
  const errors = [];
  const owner = (file) =>
    keys.find(
      (key) => file === path.join(root, key) || file.startsWith(path.join(root, key) + path.sep),
    );
  function walk(dir) {
    return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const file = path.join(dir, entry.name);
      if (entry.isSymbolicLink()) {
        errors.push(`symlink forbidden: ${file}`);
        return [];
      }
      if (entry.isDirectory())
        return ["node_modules", "dist"].includes(entry.name) ? [] : walk(file);
      return /\.[cm]?[jt]sx?$/.test(entry.name) ? [file] : [];
    });
  }
  try {
    for (const group of ["apps", "packages"]) {
      for (const entry of fs.readdirSync(path.join(root, group), { withFileTypes: true })) {
        if (entry.isSymbolicLink() || (entry.isDirectory() && !graph[`${group}/${entry.name}`]))
          errors.push(`unknown workspace or symlink: ${group}/${entry.name}`);
      }
    }
    for (const key of keys) {
      const dir = path.join(root, key);
      const configPath = path.join(dir, "tsconfig.json");
      const config = ts.readConfigFile(configPath, ts.sys.readFile);
      if (config.error) {
        errors.push(
          `invalid tsconfig: ${key}: ${ts.flattenDiagnosticMessageText(config.error.messageText, "\n")}`,
        );
        continue;
      }
      const parsed = ts.parseJsonConfigFileContent(
        config.config,
        ts.sys,
        dir,
        undefined,
        configPath,
      );
      if (parsed.errors.length) {
        errors.push(
          `invalid tsconfig: ${key}: ${parsed.errors.map((e) => ts.flattenDiagnosticMessageText(e.messageText, "\n")).join("; ")}`,
        );
        continue;
      }
      for (const file of walk(dir)) {
        const kind = /\.tsx$/.test(file)
          ? ts.ScriptKind.TSX
          : /\.[cm]?jsx?$/.test(file)
            ? ts.ScriptKind.JS
            : ts.ScriptKind.TS;
        const source = ts.createSourceFile(
          file,
          fs.readFileSync(file, "utf8"),
          ts.ScriptTarget.Latest,
          true,
          kind,
        );
        for (const diagnostic of source.parseDiagnostics)
          errors.push(
            `${path.relative(root, file)}: syntax error: ${ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n")}`,
          );
        function fail(node, reason) {
          const loc = source.getLineAndCharacterOfPosition(node.getStart(source));
          errors.push(`${path.relative(root, file)}:${loc.line + 1}: ${reason}`);
        }
        function check(specifier, node) {
          if (!specifier || !ts.isStringLiteralLike(specifier)) {
            fail(node, "nonliteral module specifier");
            return;
          }
          const name = specifier.text;
          const builtin = builtins.has(name.replace(/^node:/, "")) || name.startsWith("node:");
          const matchingPath = Object.keys(parsed.options.paths || {}).some((pattern) => {
            const star = pattern.indexOf("*");
            return star < 0
              ? name === pattern
              : name.startsWith(pattern.slice(0, star)) &&
                  name.endsWith(pattern.slice(star + 1)) &&
                  name.length >= pattern.length - 1;
          });
          if (builtin && browser.has(key)) {
            fail(node, `server builtin ${name}`);
            return;
          }
          if (builtin && !matchingPath) return;
          let target;
          if (name.startsWith("@guildboard/")) {
            target = keys.find((item) => item.split("/")[1] === name.split("/")[1]);
            if (!target) {
              fail(node, `unknown workspace ${name}`);
              return;
            }
          }
          const resolved = ts.resolveModuleName(name, file, parsed.options, ts.sys).resolvedModule
            ?.resolvedFileName;
          if (resolved) {
            const real = fs.realpathSync(resolved);
            const resolvedOwner = owner(real);
            if (resolvedOwner) {
              if (target && target !== resolvedOwner) {
                fail(node, `workspace resolution mismatch: ${name}`);
                return;
              }
              target = resolvedOwner;
            } else if (builtin || !real.includes(`${path.sep}node_modules${path.sep}`)) {
              fail(node, `module outside known workspace: ${name}`);
              return;
            }
          } else if (
            (builtin && matchingPath) ||
            name.startsWith(".") ||
            name.startsWith("/") ||
            name.startsWith("#") ||
            Object.keys(parsed.options.paths || {}).some((p) => name.startsWith(p.split("*")[0]))
          ) {
            fail(node, `unresolved local module: ${name}`);
            return;
          }
          if (target && target !== key && !graph[key].includes(target))
            fail(node, `forbidden dependency ${key} -> ${target} (${name})`);
        }
        function visit(node) {
          if (
            (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
            node.moduleSpecifier
          )
            check(node.moduleSpecifier, node);
          if (
            ts.isImportEqualsDeclaration(node) &&
            ts.isExternalModuleReference(node.moduleReference)
          )
            check(node.moduleReference.expression, node);
          if (ts.isImportTypeNode(node))
            check(ts.isLiteralTypeNode(node.argument) ? node.argument.literal : undefined, node);
          if (
            ts.isCallExpression(node) &&
            (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
              (ts.isIdentifier(node.expression) && node.expression.text === "require"))
          )
            check(node.arguments[0], node);
          // Taking a reference to require or using module.require/createRequire can evade direct-call analysis.
          if (
            ts.isIdentifier(node) &&
            node.text === "require" &&
            !(ts.isCallExpression(node.parent) && node.parent.expression === node)
          )
            fail(node, "indirect require forbidden");
          if (
            ts.isIdentifier(node) &&
            ["module", "eval", "Function", "globalThis"].includes(node.text)
          )
            fail(node, "indirect module access forbidden");
          if (browser.has(key) && ts.isIdentifier(node) && node.text === "process")
            fail(node, "process access forbidden in browser code");
          if (ts.isIdentifier(node) && node.text === "createRequire")
            fail(node, "createRequire forbidden");
          ts.forEachChild(node, visit);
        }
        visit(source);
      }
    }
  } catch (error) {
    errors.push(`boundary configuration error: ${error.message}`);
  }
  return errors;
}
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const errors = checkBoundaries(root);
  if (errors.length) {
    console.error(errors.join("\n"));
    process.exitCode = 1;
  } else console.log("Workspace boundaries valid");
}
