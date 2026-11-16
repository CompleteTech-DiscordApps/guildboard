// Independent acceptance of the documented workspace graph; no subprocesses.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { checkBoundaries } from '../engineering/boundaries.mjs';

const nodes = ['apps/activity','apps/api','apps/bot','packages/contracts','packages/canvas','packages/auth','packages/collaboration','packages/config'];
const edges = {
  'apps/activity':['contracts','canvas'], 'apps/api':['contracts','config','auth','collaboration'],
  'apps/bot':['contracts','config','auth','collaboration'], 'packages/contracts':[],
  'packages/canvas':['contracts'], 'packages/auth':['contracts'],
  'packages/collaboration':['contracts','auth'], 'packages/config':[],
};
const root = fs.mkdtempSync(path.join(process.env.ENGINEERING_ACCEPTANCE_TMP || os.tmpdir(), 'gb-acceptance-'));
let count = 0;
try {
  for (const n of nodes) {
    fs.mkdirSync(path.join(root,n,'src'), {recursive:true});
    fs.writeFileSync(path.join(root,n,'tsconfig.json'), JSON.stringify({compilerOptions:{baseUrl:'.',paths:{'@alias/*':['../../packages/auth/src/*']}}}));
    fs.writeFileSync(path.join(root,n,'src/index.ts'), 'export {};\n');
  }
  function scenario(label, project, source, expected, config) {
    const file = path.join(root,project,'src/index.ts');
    const cfg = path.join(root,project,'tsconfig.json');
    const original = fs.readFileSync(cfg);
    try {
      if (config) fs.writeFileSync(cfg, config);
      fs.writeFileSync(file, source);
      const first = checkBoundaries(root);
      const second = checkBoundaries(root);
      assert.deepEqual(second, first, `${label}: unstable errors`);
      assert.equal(first.length === 0, expected, `${label}: ${first.join('; ')}`);
      console.log(`PASS ${label}: ${expected ? 'allow' : 'deny'}${first.length ? ' (' + first.join('; ') + ')' : ''}`);
      count++;
    } finally { fs.writeFileSync(file,'export {};\n'); fs.writeFileSync(cfg,original); }
  }
  for (const from of nodes) for (const to of nodes) {
    if (from === to) continue;
    const name = to.split('/')[1];
    scenario(`${from} -> ${to}`,from,`import '@guildboard/${name}';`,edges[from].includes(name));
  }
  for (const [label, project, source, allowed] of [
    ['type import allowed','apps/activity',"import type { X } from '@guildboard/contracts';",true],
    ['re-export denied','packages/auth',"export * from '@guildboard/canvas';",false],
    ['dynamic literal denied','apps/activity',"import('@guildboard/config');",false],
    ['require denied','apps/bot',"require('@guildboard/activity');",false],
    ['alias denied','apps/activity',"import '@alias/index';",false],
    ['alias allowed','apps/api',"import '@alias/index';",true],
    ['relative denied','apps/activity',"import '../../../packages/auth/src/index';",false],
    ['server builtin allowed','apps/bot',"import 'node:fs';",true],
    ['browser builtin denied','packages/canvas',"import 'node:fs';",false],
    ['unresolved relative denied','apps/api',"import './missing';",false],
    ['unknown workspace denied','apps/api',"import '@guildboard/missing';",false],
    ['nonliteral denied','apps/api',"import(variable);",false],
    ['syntax denied','apps/api','import { from;',false],
  ]) scenario(label,project,source,allowed);
  scenario('invalid tsconfig','apps/api','export {};',false,'{');
  console.log(`PASS ${count} independent scenarios`);
} finally { fs.rmSync(root,{recursive:true,force:true}); }
