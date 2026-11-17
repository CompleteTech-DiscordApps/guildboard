"""Idempotent bootstrap; refreshes remote state before repairing. No credential storage.
Usage: python3 scripts/github-bootstrap/reconcile.py [--verify-only] [--phase issues|links|fields|comments|all]
       python3 scripts/github-bootstrap/reconcile.py --phase comments --dry-run
--dry-run reads live issues and reports bootstrap-owned body rewrites without writing local files or updating GitHub.
"""
import argparse,hashlib,re,collections,sys
parser=argparse.ArgumentParser();parser.add_argument('--verify-only',action='store_true');parser.add_argument('--phase',default='all',choices=['issues','links','fields','comments','all']);parser.add_argument('--dry-run',action='store_true',help='comments phase only: report body rewrites, write nothing');args=parser.parse_args()
if args.dry_run and (args.phase != 'comments' or args.verify_only):
 parser.error('--dry-run requires --phase comments and cannot be combined with --verify-only')
if args.dry_run:
 sys.dont_write_bytecode=True
from api import *
if args.verify_only:
 print('Read-only remote audit requested.');subprocess.run(['python3',str(ROOT/'scripts/github-bootstrap/audit.py')],check=True);raise SystemExit()
manifest=ROOT/'planning/guildboard-backlog.json';m=json.loads(manifest.read_text());s=json.loads(STATE.read_text());repo=s['repo'];pid=s['project']['id'];by={x['id']:x for x in m['items']}
def persist():
 if args.dry_run:return
 for x in m['items']:x.setdefault('description','; '.join(x['requirements']))
 save(manifest,m)
def all_issues():
 out=[];page=1
 while True:
  endpoint=f'repos/{repo}/issues?state=all&per_page=100&page={page}'
  rows=api(endpoint,quiet_get=True) if args.dry_run else api(endpoint)
  if args.dry_run and (not isinstance(rows,list) or any(
   not isinstance(row,dict) or type(row.get('number')) is not int
   or ('body' in row and row['body'] is not None and not isinstance(row['body'],str))
   or ('pull_request' not in row and not isinstance(row.get('node_id'),str))
   for row in rows
  )):
   raise ValueError('Invalid GitHub issue list')
  out += [x for x in rows if 'pull_request' not in x]
  if len(rows)<100:return out
  page+=1
try:
 remote=all_issues()
except (RuntimeError,OSError,ValueError):
 if not args.dry_run:raise
 raise SystemExit('Dry run stopped: GitHub issues could not be read.') from None
remote_by={}
preview_edited=set()
if args.dry_run:
 def identity_mismatch():
  raise SystemExit('Dry run stopped: issue identity mismatch.')

 expected={}
 if len(by)!=len(m['items']):identity_mismatch()
 for stable,item in by.items():
  if 'github' not in item:continue
  mapping=item['github']
  if not isinstance(mapping,dict):identity_mismatch()
  number=mapping.get('number')
  node_id=mapping.get('id')
  if (type(number) is not int or number <= 0 or number in expected
      or not isinstance(node_id,str) or not node_id):identity_mismatch()
  expected[number]=(stable,node_id)
 expected_nodes={node_id for _,node_id in expected.values()}
 if len(expected_nodes)!=len(expected):identity_mismatch()

 seen=set()
 for issue in remote:
  number=issue['number']
  if number in seen:identity_mismatch()
  seen.add(number)
  markers=re.findall(r'<!-- guildboard-id:([^\s]+) -->',issue.get('body') or '')
  if number not in expected:
   if issue['node_id'] in expected_nodes or any(marker in by for marker in markers):identity_mismatch()
   continue
  stable,node_id=expected[number]
  if issue['node_id']!=node_id or (markers and markers!=[stable]):identity_mismatch()
  if markers:
   remote_by[stable]=issue
  else:
   preview_edited.add(stable)
else:
 for issue in remote:
  marker=re.search(r'<!-- guildboard-id:([^ ]+) -->',issue.get('body') or '')
  if marker:
   stable=marker[1]
   if stable in remote_by:raise RuntimeError('Duplicate stable ID '+stable)
   remote_by[stable]=issue
   if stable in by:by[stable]['github']=issue_mapping(issue,repo)
 persist()
def link(id):
 x=by[id];return f"[{id}]({issue_url(x['github']['number'],repo)})" if x.get('github') else f'`{id}` (not yet created; see manifest)'
def body(x):
 f=x['fields'];typ=x['work_type'];scope='\n'.join('- '+v for v in x['requirements']);ac='\n'.join('- [ ] '+v for v in x['acceptance_criteria']);tests='\n'.join('- '+v for v in x['expected_tests']);deps='\n'.join('- Blocked by (native): '+link(d)+(' — '+x.get('dependency_rationale',{}).get(d,'') if d in x.get('dependency_rationale',{}) else '') for d in x['dependencies']) or '- No execution blockers recorded. Information inputs do not imply sequencing.'
 parent='- Parent: '+link(x['parent_id']) if x['parent_id'] else '- Top-level workstream; no parent.'
 children=[v for v in m['items'] if v['parent_id']==x['id']]
 childlinks='\n'.join('- '+link(c['id'])+' — '+c['title'].split(' — ',1)[-1] for c in children) if children and all(c.get('github') for c in children) else 'Use the native Sub-issues panel for the authoritative child list. Every child is enrolled in the Project.'
 deliver='A reviewed, source-cited decision record with alternatives and unresolved uncertainty.' if typ=='Research' else 'A reviewed versioned contract with schemas, invariants and consumer handoffs.' if typ=='Specification' else 'Executable scenarios and raw evidence tied to an exact revision/environment; record failures and defects.' if typ=='Test' else 'Reviewed documentation with reproducible steps and honest implementation status.' if typ=='Documentation' else 'Focused implementation with automated regression coverage and updated integration documentation.'
 triage='\n'.join('- **'+k+'**: '+v for k,v in f.items())+'\n- **Milestone**: '+x['milestone']+'\n- **Assignee**: intentionally unassigned; claim through maintainer workflow.'
 common=f'''<!-- guildboard-id:{x['id']} -->
Stable ID: `{x['id']}`. Scope source: [canonical planning manifest](https://github.com/{repo}/blob/main/planning/guildboard-backlog.json).
'''
 if typ=='Epic':
  capabilities=[c for c in children if c['work_type']=='Capability']
  scope+='\n'+'\n'.join('- **'+c['title'].split(' — ',1)[-1]+'**: '+', '.join(v['title'].split(' — ',1)[-1] for v in m['items'] if v['parent_id']==c['id'] and v['work_type']=='Feature')+'.' for c in capabilities)
  boundaries={
   'T0':'Own product, system boundaries, developer foundation and decisions. Identity belongs to T1, policy T2, canvas T3, collaboration T4, data T5 and release/operations to T9–T13.',
   'T1':'Own Discord lifecycle, verified identity/context and token handling. Authorization policy belongs to T2; authoritative editing and room sequencing belong to T4.',
   'T2':'Own permission evaluation, grants, restrictions and moderation authority. T1 supplies verified Discord identity; T3 supplies editor UI; T4 enforces the policy on mutation processing.',
   'T3':'Own editor tools, adapter, canonical element serialization and rendering. T4 owns authoritative collaboration/conflicts; T5 owns durable storage and board recovery.',
   'T4':'Own transport, rooms, operation processing and presence. Consume current policy from T2 and durable transactions from T5; do not duplicate editor rendering from T3.',
   'T5':'Own tenant data, board lifecycle, assets, snapshots and restore lineage. VPS provisioning belongs to T10; infrastructure backups/disaster recovery to T11; canvas undo semantics to T3/T4.',
   'T6':'Own mode state transitions, presenter authority and follow behavior. Consume writing-grant policy from T2, transport from T4 and accessible shell controls from T7.',
   'T7':'Own responsive interaction, controls, feedback and accessibility. Backend policy is T2, editor primitives T3, protocol T4 and API routes T8; UI visibility never substitutes for enforcement.',
   'T8':'Own Fastify route/bot composition, validation and published API contracts. Delegate policy to T2, concurrency to T4 and persistence invariants to T5.',
   'T9':'Own threat analysis, security/privacy requirements and independent assurance. Feature owners implement controls at their boundaries; security review is not implied by passing generic tests.',
   'T10':'Own mandatory GoDaddy VPS topology, networking, service delivery and rollback. Application routes belong to T8; operational alerts/backups/incident response to T11.',
   'T11':'Own monitoring, service resilience, backups, disaster recovery and operational response. Board history/restore logic belongs to T5; functional acceptance harnesses to T12.',
   'T12':'Own test strategy, cross-system fixtures, acceptance and evidence quality. Feature implementation remains with T0–T11; independent security review remains T9.',
   'T13':'Own documentation, community governance and release orchestration. Runtime implementation stays with engineering workstreams; production/security acceptance requires real T9–T12 evidence.'}
  boundary=boundaries[x['workstream']]
  return common+f'''
## Product or Engineering Question
How will Guildboard deliver {x['title'].split(': ',1)[-1]} with testable security, Discord compatibility and production evidence?

## Scope
{scope}

## Boundaries
{boundary} Planning completion does not certify application behavior or deployment.

## Native Sub-Issues
{childlinks}

## Deliverables
Accepted capability implementations, focused tests, documented contracts and operating/developer handoffs. Every mandatory descendant must meet its Definition of Done.

## Dependencies and Handoffs
{deps}
Native blockers apply to specific executable children, not automatically to their parent. Cross-workstream interfaces are coordinated through specification and release-gate issues.

## Acceptance Criteria
{ac}

## Review and Verification
Review child evidence, integration tests, negative authorization tests and relevant real Discord/GoDaddy compatibility checks. No parent closure while required children remain open or rejected.

## Owner
Functional role: **{f['Owner Role']}**. No individual assigned yet.

## Project Triage
{triage}
'''
 return common+f'''
## Objective
{x['title'].split(' — ',1)[-1]}. Deliver the scope below with observable acceptance evidence.

## Context
This work belongs to **{f['Tier']}**. Consumers must use accepted contracts and server-authoritative tenant/permission boundaries. Product functionality remains unimplemented until evidence proves otherwise.

## In Scope
{scope}

## Out of Scope
Unrelated Tier capabilities, production credential provisioning and undocumented platform assumptions. Do not widen permissions or replace mandatory GoDaddy Linux VPS hosting with an unevaluated alternative.

## Technical Requirements
{scope}
Preserve versioned interfaces, bounded inputs, explicit error outcomes and reproducible setup. Follow the accepted Tier specification before implementing unresolved design choices.

## Implementation Subtasks
- [ ] Inspect parent scope, current contracts and linked blockers.
- [ ] Produce the focused {typ.lower()} deliverable covering each in-scope requirement.
- [ ] Add the acceptance scenarios below, including error and abuse paths.
- [ ] Update integration documentation and attach reviewable evidence.

## Deliverables
{deliver}
Documentation: `{x['documentation_artifacts'][0]}`. Include exact commands, results and limitations where applicable.

## Acceptance Criteria
{ac}
- [ ] Each scope clause has an observable test or documented review result; unresolved requirements remain open.

## Validation and Evidence
{tests}
Use deterministic fixtures where possible. Real platform/VPS claims require dated real-environment evidence; mocked SDK or local proxy tests alone are insufficient.

## Dependencies and Relationships
{parent}
{deps}
- Information input: [workstream contracts and traceability](https://github.com/{repo}/tree/main/docs/workstreams).
- Handoff: provide accepted artifacts to the parent capability and consuming verification/release gate. Compatibility coordination alone does not create a blocker.

## Security and Privacy
Enforce least privilege and tenant isolation; do not log credentials or unnecessary board content. For authorization changes include explicit allow/deny tests, stale-session checks and no-side-effect assertions. Report security defects through the repository security policy.

## Discord/GoDaddy Compatibility
Validate applicable Discord Activity iframe/proxy and client constraints. Runtime deployment targets GoDaddy Linux VPS with HTTPS/WSS, private database and persistent assets. Record not-applicable constraints with rationale; never claim external verification from local tests.

## Review Requirements
Functional review by **{f['Owner Role']}** expertise; security review for identity/permission/data boundary changes; integration review from consumers of changed contracts. No review has been performed by creating this issue.

## Definition of Done
- [ ] Deliverable exists and applicable PR is merged after required actual review.
- [ ] Acceptance criteria and security requirements pass with linked evidence.
- [ ] Documentation, integration, native dependencies and parent progress reflect actual results.
- [ ] Post-merge and real-environment verification is recorded where relevant.

## Initial Project Triage
{triage}
'''
def order():
 done=set();result=[]
 def visit(id,stack):
  if id in done:return
  if id in stack:raise RuntimeError('Cycle '+str(stack+[id]))
  x=by[id]
  for d in ([x['parent_id']] if x['parent_id'] else [])+x['dependencies']:visit(d,stack+[id])
  done.add(id);result.append(x)
 for id in by:visit(id,[])
 return result
ordered=order()
if args.phase in ['issues','all']:
 for i,x in enumerate(ordered):
  if x.get('github'):continue
  content=body(x)
  r=api('repos/'+repo+'/issues','POST',{'title':x['title'],'body':content,'labels':x['labels'],'milestone':s['milestones'][x['milestone']]})
  x['github']=issue_mapping(r,repo);x['body_hash']=hashlib.sha256(content.encode()).hexdigest();persist()
  print(f"created {i+1}/{len(ordered)} {x['id']} #{r['number']}",flush=True)
  # Conservative writes stay under 80/min; retries never duplicate a known stable ID.
  time.sleep(1.2)
if args.phase in ['links','fields','all']:
 # Refresh IDs before every repair pass; never trust a manifest cache as proof.
 live={}
 after=None
 while True:
  r=gql('query($id:ID!,$after:String){node(id:$id){... on ProjectV2{items(first:100,after:$after){nodes{id content{... on Issue{id number}} fieldValues(first:30){nodes{... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2SingleSelectField{name}}}}}} pageInfo{hasNextPage endCursor}}}}}',id=pid,after=after)['node']['items']
  for v in r['nodes']:
   if v.get('content'):live[v['content']['id']]=v
  if not r['pageInfo']['hasNextPage']:break
  after=r['pageInfo']['endCursor']
 for x in ordered:
  if not x.get('github'):continue
  if x['github']['id'] not in live:
   r=gql('mutation($i:AddProjectV2ItemByIdInput!){addProjectV2ItemById(input:$i){item{id}}}',i={'projectId':pid,'contentId':x['github']['id']})['addProjectV2ItemById']['item'];live[x['github']['id']]={'id':r['id'],'fieldValues':{'nodes':[]}}
  x['project_item_id']=live[x['github']['id']]['id'];persist()
 if args.phase in ['links','all']:
  for x in ordered:
   if not x.get('github'):continue
   n=x['github']['number'];parent=api(f'repos/{repo}/issues/{n}/parent') if x.get('native_parent_verified') else None
   # REST parent returns 404 for roots or missing links; GraphQL is nullable and authoritative.
   current=gql('query($id:ID!){node(id:$id){... on Issue{parent{id} blockedBy(first:100){nodes{id}}}}}',id=x['github']['id'])['node']
   if x['parent_id']:
    want=by[x['parent_id']]['github']['id']
    if current['parent'] and current['parent']['id']!=want:raise RuntimeError('Existing parent differs for '+x['id'])
    if not current['parent']:gql('mutation($i:AddSubIssueInput!){addSubIssue(input:$i){issue{id}}}',i={'issueId':want,'subIssueId':x['github']['id']})
   blocked={d['id'] for d in current['blockedBy']['nodes']}
   for dep in x['dependencies']:
    want=by[dep]['github']['id']
    if want not in blocked:gql('mutation($i:AddBlockedByInput!){addBlockedBy(input:$i){issue{id}}}',i={'issueId':x['github']['id'],'blockingIssueId':want})
   print('linked',x['id'],flush=True)
 if args.phase in ['fields','all']:
  fields={f['name']:f for f in project()['fields']['nodes']}
  for x in ordered:
   if not x.get('project_item_id'):continue
   vals={v['field']['name']:v['name'] for v in live[x['github']['id']]['fieldValues']['nodes'] if v}
   changes={k:v for k,v in x['fields'].items() if k not in vals} # preserve existing deliberate changes
   # Initial bootstrap can replace copied defaults only when no applied_hash was recorded.
   if not x.get('applied_hash'):changes={k:v for k,v in x['fields'].items() if vals.get(k)!=v}
   mutations=[];variables={};decl=[]
   for j,(k,v) in enumerate(changes.items()):
    field=fields[k];option=next(z['id'] for z in field['options'] if z['name']==v)
    variables['i'+str(j)]={'projectId':pid,'itemId':x['project_item_id'],'fieldId':field['id'],'value':{'singleSelectOptionId':option}};decl.append('$i'+str(j)+':UpdateProjectV2ItemFieldValueInput!');mutations.append('f'+str(j)+':updateProjectV2ItemFieldValue(input:$i'+str(j)+'){projectV2Item{id}}')
   if mutations:gql('mutation('+','.join(decl)+'){'+''.join(mutations)+'}',**variables)
   x['applied_hash']=hashlib.sha256(json.dumps(x['fields'],sort_keys=True).encode()).hexdigest();persist();print('triaged',x['id'],flush=True)
if args.dry_run:
 counts = collections.Counter()
 beyond = []
 for x in ordered:
  issue = remote_by.get(x['id'])
  if issue is None:
   counts['edited' if x['id'] in preview_edited else 'missing'] += 1
   continue
  old_body = issue.get('body') or ''
  rendered = body(x)
  if rendered == old_body:
   counts['current'] += 1
  elif hashlib.sha256(old_body.encode()).hexdigest() != x.get('body_hash'):
   counts['edited'] += 1
  else:
   counts['rewrite'] += 1
   if canonicalize_transferred_links(old_body, repo) != rendered:
    beyond.append(x['id'])
 print(json.dumps({
  'mode': 'dry-run',
  'repository': repo,
  'would_rewrite': counts['rewrite'],
  'rewrites_beyond_repository_identity': beyond,
  'already_current': counts['current'],
  'skipped_maintainer_edited': counts['edited'],
  'skipped_missing': counts['missing'],
 }, indent=2))
 raise SystemExit()
if args.phase in ['comments','all']:
 for x in ordered:
  if not x.get('github'):continue
  if hashlib.sha256(body(x).encode()).hexdigest()!=x.get('body_hash'):
   content=body(x);r=api(f"repos/{repo}/issues/{x['github']['number']}");oldbody=r.get('body') or ''
   # Only update bootstrap-owned body when it has not been edited by a maintainer.
   if hashlib.sha256(oldbody.encode()).hexdigest()==x.get('body_hash') and content!=oldbody:
    api(f"repos/{repo}/issues/{x['github']['number']}",'PATCH',{'body':content});x['body_hash']=hashlib.sha256(content.encode()).hexdigest();persist()
  if x['work_type']!='Specification' and not x['id'].endswith(('.G2','.G3')) and x['id']!='GB-T0.03.02.T1':continue
  marker='<!-- guildboard-handoff:'+x['id']+' -->';comments=api(f"repos/{repo}/issues/{x['github']['number']}/comments?per_page=100")
  if any(marker in c.get('body','') for c in comments):continue
  deps=', '.join(link(d) for d in x['dependencies']) or 'none'
  text=marker+'\nNext action: review the prerequisite evidence from '+deps+'. Produce the exact schemas/invariants and consuming test fixtures listed above before implementation.\n\nIntegration strategy: separate server authority from client rendering; treat Discord guild/role context and GoDaddy networking as independently verified boundaries. Record rejected alternatives and unresolved platform assumptions in the ADR. Security review must cover stale permissions and cross-tenant requests; validation must identify mocked versus real-environment evidence.\n\nNo architecture approval, implementation result or maintainer agreement is implied by this triage comment.'
  if x['id']=='GB-T0.03.02.T1':text=marker+'\nImplementation handoff: follow [the explicit configuration contract](https://github.com/'+repo+'/blob/main/planning/configuration-contract.md). Create packages/config with pure parseConfig, the exact success/failure union, strict boundary validation and secret-safe errors. Keep service startup/Discord/database integration out of this focused change. Run table-driven parser tests and prove sentinel secrets never appear in diagnostics; the sibling verification issue accepts the evidence separately.'
  c=api(f"repos/{repo}/issues/{x['github']['number']}/comments",'POST',{'body':text});x['comment_id']=c['id'];persist();time.sleep(1.2)
print('Requested reconciliation phase complete',flush=True)
