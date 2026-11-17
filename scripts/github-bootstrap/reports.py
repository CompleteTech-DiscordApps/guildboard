from api import *
import collections
m=json.loads((ROOT/'planning/guildboard-backlog.json').read_text());by={x['id']:x for x in m['items']}
def link(id):
 x=by[id];return '['+id+']('+issue_url(x['github']['number'],m['repository'])+')' if x.get('github') else '`'+id+'` (creation pending)'
rows=[]
for x in m['items']:
 if x['work_type']!='Feature':continue
 impl=[c for c in m['items'] if c['parent_id']==x['id'] and c['work_type'] in ['Task','Documentation','Operations']]
 tests=[c for c in m['items'] if c['parent_id']==x['id'] and c['work_type']=='Test']
 doc=by[x['workstream'].replace('T','GB-T')+'.D1'];gate='GB-T13.G3' if x['fields']['Release Target']=='v1.0' else 'GB-T13.G1' if x['fields']['Release Target']=='MVP' else None
 for criterion in x['requirements']:
  rows.append({'requirement':criterion,'workstream':x['workstream'],'feature':x['id'],'implementation':[v['id'] for v in impl],'tests':[v['id'] for v in tests],'documentation':doc['id'],'release_gate':gate,'release':x['fields']['Release Target']})
save(ROOT/'planning/traceability.json',rows)
md='# Requirements traceability\n\nEvery authored mandatory behavior clause maps to focused implementation, verification, documentation and release acceptance. These links track planned acceptance, not completed behavior. Post-v1.0 work is explicitly outside mandatory release scope.\n\n| Requirement | Implementation | Tests | Documentation | Release gate |\n| --- | --- | --- | --- | --- |\n'
for r in rows:md+='| '+r['requirement'].replace('|','/')+' | '+', '.join(link(i) for i in r['implementation'])+' | '+', '.join(link(i) for i in r['tests'])+' | '+link(r['documentation'])+' | '+(link(r['release_gate']) if r['release_gate'] else 'Post-v1.0')+' |\n'
(ROOT/'planning/TRACEABILITY.md').write_text(md)
local=json.loads((ROOT/'planning/audit/local-validation.json').read_text());chain=local['longest_prerequisite_chain']
remote_path=ROOT/'planning/audit/remote-audit.json'
if remote_path.exists():
 remote=json.loads(remote_path.read_text());num_to_id={x['github']['number']:x['id'] for x in m['items'] if x.get('github')}
 if remote.get('result')=='pass' and all(n in num_to_id for n in remote.get('longest_unweighted_dependency_chain',[])):chain=[num_to_id[n] for n in remote['longest_unweighted_dependency_chain']]
md='# Dependency graph and critical path\n\nOnly native blocking prerequisites impose execution order. Parent completion is aggregation, never a blanket blocker. Compatibility and information inputs can be bidirectional without becoming dependency cycles.\n\n## Longest prerequisite chain\n\nThis is an unweighted chain, not a scheduled duration estimate. No dates or staffing commitments exist. Parallel release branches also matter.\n\n'+' → '.join(link(i) for i in chain)+'\n\n## Native blocking edges\n\n| Blocked issue | Prerequisite |\n| --- | --- |\n'
for x in m['items']:
 for d in x['dependencies']:md+='| '+link(x['id'])+' | '+link(d)+' |\n'
(ROOT/'planning/DEPENDENCIES.md').write_text(md)
md='# Risk and uncertainty register\n\nEvery research conclusion is initially Unverified. These are actionable evidence gaps, not discovered production defects. No account access, client compatibility, load capacity or deployed networking is presumed.\n\n| Workstream | Evidence gap | Owner expertise | Research | Acceptance contract |\n| --- | --- | --- | --- | --- |\n'
for t,w in enumerate(json.loads((ROOT/'planning/workstreams.json').read_text())):md+=f'| T{t} | {w["research"]} | {w["role"]} | '+link(f'GB-T{t}.R1')+' | '+link(f'GB-T{t}.S1')+' |\n'
md+='\n## Operational prerequisites\n\nActual Discord application credentials, guild admin access, GoDaddy VPS account/provisioning, domain/DNS control, production secrets and real client test environments remain implementation-stage prerequisites. No VPS purchase or deployment was authorized or performed by this planning bootstrap.\n'
(ROOT/'planning/RISKS.md').write_text(md)
md='# Milestones and release gates\n\nMilestones express sequence; none has a due date. Implementation and independent verification are separate.\n\n'
for name in json.loads(STATE.read_text())['milestones']:
 xs=[x for x in m['items'] if x['milestone']==name];md+=f'- **{name}**: {len(xs)} work items.\n'
md+='\n- MVP: '+link('GB-T13.G1')+'\n- Production recovery/GoDaddy: '+link('GB-T13.G2')+'\n- Stable v1.0: '+link('GB-T13.G3')+'\n\nA merged PR is not production acceptance. Security and backup restore verification block release.\n'
(ROOT/'planning/MILESTONES.md').write_text(md)
print('Traceability clauses',len(rows))
