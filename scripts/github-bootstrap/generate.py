"""Compile authored capability definitions into stable, fully classified work units."""
from api import *
streams=json.loads((ROOT/'planning/workstreams.json').read_text());state=json.loads(STATE.read_text());ms=list(state['milestones']);items=[]
old={x['id']:x for x in json.loads((ROOT/'planning/guildboard-backlog.json').read_text()).get('items',[])} if (ROOT/'planning/guildboard-backlog.json').exists() else {}
def add(id,title,t,typ,parent=None,requirements='',deps=None,milestone=None,release=None,priority=None,ready=None):
 w=streams[t];dep=deps or [];rel=release or ('MVP' if t in [0,1,2,3,4,5,8] else 'v1.0');pri=priority or ('Critical' if t in [0,1,2,4,5,9,10,12] else 'High')
 meta={'Tier':f'T{t} '+w['name'],'Work Type':typ,'Priority':pri,'Readiness':ready or ('Not Applicable' if typ in ['Epic','Capability','Feature'] else 'Blocked' if dep else 'Ready' if typ in ['Research','Specification','Documentation'] else 'Needs Specification'),'Status':'Backlog','Dependency Status':'Blocked' if dep else 'Unblocked','Release Target':rel,'Risk':'Critical' if t in [1,2,4,5,9,10] else 'High' if typ!='Documentation' else 'Low','Effort':'XL' if typ in ['Epic','Capability'] else 'L' if typ=='Feature' else 'M','Owner Role':w['role'],'Research Confidence':'Unverified','Verification Status':'Unverified'}
 clauses=[x.strip().rstrip('.') for x in requirements.split(';') if x.strip()]
 ac=[c[0].upper()+c[1:]+'.' for c in clauses]
 tests=([f'Provide primary evidence and a reproducible experiment for: {title}; record version, date, limitations and unresolved questions.'] if typ=='Research' else [f'Positive acceptance: {c}.' for c in clauses[:2]]+[f'Negative/failure acceptance: reject unauthorized, malformed, stale and cross-guild inputs for {title.lower()} without side effects.' if t in [1,2,3,4,5,6,8,9] else f'Failure acceptance: exercise invalid configuration, unavailable prerequisites and interrupted execution for {title.lower()}.'])
 labels=['type: '+('workstream' if typ=='Epic' else typ.lower())]+['topic: '+x for x in w['topics']]+['release: '+{'MVP':'mvp','v1.0':'v1.0','Post-v1.0':'post-v1.0'}[rel]]
 x={'id':id,'title':title if typ=='Epic' else id+' — '+title,'workstream':f'T{t}','parent_id':parent,'work_type':typ,'fields':meta,'milestone':ms[milestone if milestone is not None else w['milestone']],'labels':labels,'dependencies':dep,'acceptance_criteria':ac,'expected_tests':tests,'documentation_artifacts':[f'docs/workstreams/T{t}.md'],'requirements':clauses,'assignees':[]}
 for k in ['github','project_item_id','applied_hash','body_hash','comment_id']: 
  if k in old.get(id,{}):x[k]=old[id][k]
 # Remote mappings keep number/node ID; links always derive from the pinned canonical repository.
 if 'github' in x:x['github']={**x['github'],'url':issue_url(x['github']['number'],state['repo'])}
 items.append(x);return x
for t,w in enumerate(streams):
 root=f'GB-T{t}';add(root,f'T{t}: '+w['name'],t,'Epic',requirements='Deliver all native child outcomes with accepted evidence; resolve handoffs, security findings and release acceptance; do not close while mandatory descendants remain incomplete')
 add(root+'.R1',w['research'],t,'Research',root,requirements=w['research']+'; record alternatives, primary source URLs, evaluated versions, uncertainty and recommended decision',milestone=0)
 add(root+'.S1',w['contract'],t,'Specification',root,requirements=w['contract']+'; document schemas, invariants, errors, security consequences and test fixtures; obtain consuming engineering review before implementation',deps=[root+'.R1'],milestone=0)
 for c,(cap,features) in enumerate(w['capabilities'],1):
  cid=f'{root}.{c:02}';add(cid,cap,t,'Capability',root,requirements='; '.join(title for title,_ in features)+'; accept implementation, tests and documentation together')
  for f,(title,req) in enumerate(features,1):
   fid=f'{cid}.{f:02}';post=t==13 and c==4 and f==2
   rel='Post-v1.0' if post else None;pri='Low' if post else None
   add(fid,title,t,'Feature',cid,requirements=req,release=rel,priority=pri,milestone=8 if post else None)
   kind='Documentation' if t==13 and c<4 else 'Task'
   deps=[root+'.S1']
   ready=None
   if t==0 and c==3 and f==2:deps=[];ready='Ready'
   impl=add(fid+'.T1',('Document ' if kind=='Documentation' else 'Implement ')+title,t,kind,fid,requirements=req,deps=deps,ready=ready,release=rel,priority=pri,milestone=8 if post else None)
   add(fid+'.V1','Verify '+title,t,'Test',fid,requirements='Execute acceptance scenarios for '+title+'; '+req+'; retain raw results, tested revision/environment and defects; no pass claims from mocks alone for Discord or GoDaddy integration',deps=[impl['id']],release=rel,priority=pri,milestone=8 if post else None)
 add(root+'.D1','Document '+w['name']+' integration and handoff',t,'Documentation',root,requirements='Explain accepted contracts and operator/contributor steps for '+w['name']+'; link actual implementation and test evidence; distinguish planned behavior, supported behavior and unresolved limitations',deps=[root+'.S1'])
# Small independent implementation boundaries with complete contracts.
add('GB-T0.03.02.T1.S1','Implement secret-safe configuration diagnostics',0,'Subtask','GB-T0.03.02.T1',requirements='Return structured CONFIG_INVALID with sorted missing or invalid variable names; never include environment values, database credentials or session secrets; return failure for later startup to translate to nonzero exit; do not terminate the process inside the parser; snapshot tests contain variable names only',ready='Ready',milestone=1)
add('GB-T0.03.02.T1.S2','Implement strict numeric and URL configuration parsers',0,'Subtask','GB-T0.03.02.T1',requirements='Accept PORT only as base-10 whole integer 1–65535; reject whitespace-only, fractional, exponential, negative and overflow values; accept DATABASE_URL only with mysql protocol and nonempty hostname/database; test all boundary values without logging credentials',ready='Ready',milestone=1)
by={x['id']:x for x in items}
def block(target,*sources):
 x=by[target];x['dependencies']=list(dict.fromkeys(x['dependencies']+list(sources)));x['fields']['Readiness']='Blocked';x['fields']['Dependency Status']='Blocked'
block('GB-T1.03.02.T1','GB-T1.02.01.V1','GB-T1.03.01.V1')
block('GB-T2.01.02.T1','GB-T1.03.02.V1')
block('GB-T4.01.01.T1','GB-T2.01.02.V1','GB-T1.02.02.V1')
block('GB-T4.S1','GB-T3.S1')
block('GB-T4.02.01.T1','GB-T3.01.02.V1','GB-T5.02.01.V1')
block('GB-T5.02.02.T1','GB-T5.02.01.V1')
block('GB-T5.03.01.T1','GB-T5.02.02.V1')
block('GB-T5.03.02.T1','GB-T5.03.01.V1','GB-T5.02.02.V1')
block('GB-T2.02.01.T1','GB-T2.01.02.V1')
block('GB-T2.02.02.T1','GB-T2.02.01.V1')
block('GB-T6.01.02.T1','GB-T2.02.02.V1')
block('GB-T10.02.02.T1','GB-T10.02.01.V1')
block('GB-T10.04.02.T1','GB-T10.02.01.V1','GB-T10.02.02.V1','GB-T10.03.02.V1')
block('GB-T11.03.02.T1','GB-T11.03.01.V1')
block('GB-T12.03.01.T1','GB-T4.02.02.V1','GB-T4.01.02.V1')
block('GB-T12.03.02.T1','GB-T5.03.02.V1','GB-T11.03.02.V1')
block('GB-T9.04.02.T1','GB-T9.01.01.V1','GB-T9.01.02.V1','GB-T9.02.01.V1','GB-T9.02.02.V1')
# Concrete release gates depend on accepted verification, never just merged implementation.
mvp=['GB-T8.01.01.V1','GB-T8.01.02.V1','GB-T8.02.01.V1','GB-T1.01.01.V1','GB-T1.02.01.V1','GB-T1.03.02.V1','GB-T2.01.02.V1','GB-T2.03.01.V1','GB-T3.01.01.V1','GB-T3.04.02.V1','GB-T4.01.01.V1','GB-T4.01.02.V1','GB-T4.02.02.V1','GB-T5.02.02.V1','GB-T12.02.01.V1','GB-T12.03.01.V1']
add('GB-T13.G1','MVP acceptance gate',13,'Test','GB-T13',requirements='Demonstrate Discord startup and authenticated guild context; verify moderator roles and simultaneous moderators; deny viewer writes on backend; demonstrate canvas, live synchronization, saved boards, basic lock and reconnect; attach fundamental security and acceptance evidence',deps=mvp,milestone=2,release='MVP',priority='Critical')
add('GB-T13.G2','Production recovery and GoDaddy acceptance gate',13,'Test','GB-T13',requirements='Demonstrate actual GoDaddy VPS HTTPS/WSS and Discord networking; restore database and assets in isolated environment with measured RPO/RTO; verify monitoring, rollback and production smoke tests; record deployment environment and unresolved findings',deps=['GB-T10.04.02.V1','GB-T11.03.02.V1','GB-T12.04.01.V1','GB-T12.04.02.V1'],milestone=6,priority='Critical')
alltests=[x['id'] for x in items if x['work_type']=='Test' and x['fields']['Release Target']!='Post-v1.0' and not x['id'].endswith(('.G1','.G2'))]
# Gate fan-in stays within supported issue dependency limits by using workstream acceptance gates.
for t in range(13):
 deps=[x['id'] for x in items if x['workstream']==f'T{t}' and x['work_type']=='Test']
 add(f'GB-T{t}.G1',f'T{t} accepted workstream verification gate',t,'Test',f'GB-T{t}',requirements='Confirm all mandatory verification children for '+streams[t]['name']+' have real evidence; resolve defects and security exceptions; verify handoff documentation and integration on release candidate',deps=deps,priority='Critical',milestone=6)
add('GB-T13.G3','Stable v1.0 release approval gate',13,'Test','GB-T13',requirements='All mandatory functionality, modes, moderation, import/export, accessibility and recovery accepted; independent security review findings resolved; production acceptance and full integration tests pass; reviewed versioned artifacts, release notes and support documentation exist',deps=[f'GB-T{t}.G1' for t in range(13)]+['GB-T13.G1','GB-T13.G2','GB-T13.01.01.V1','GB-T13.01.02.V1','GB-T13.02.01.V1','GB-T13.02.02.V1','GB-T13.03.01.V1','GB-T13.03.02.V1'],milestone=7,priority='Critical')
for target,source,reason in json.loads((ROOT/'planning/additional-dependencies.json').read_text()):
    block(target,source)
    by[target].setdefault('dependency_rationale',{})[source]=reason
for x in items:
    if x['id'].startswith('GB-T0.03'):x['milestone']=ms[1]
    if x['work_type']=='Subtask':x['fields']['Effort']='S'
for x in items:
    if x['id'].startswith('GB-T8.01'):x['fields']['Priority']='Critical'
# Independently owned MVP slices and post-approval publication avoid release cycles.
add('GB-T8.02.01.T2','Implement MVP board list, creation and saved-state APIs',8,'Task','GB-T8.02.01',requirements='Provide authenticated tenant-scoped list/create/select and saved-state board endpoints using accepted versioned contracts; enforce verified guild membership and board policy on every request; exclude advanced grant administration and asset import/export from this focused slice; integration tests prove foreign-guild requests and viewer mutations are denied without side effects',deps=['GB-T8.S1','GB-T8.01.02.V1','GB-T5.01.01.V1','GB-T5.02.02.V1'],milestone=2,release='MVP',priority='Critical')
add('GB-T8.02.01.V2','Verify MVP board APIs and persistence boundary',8,'Test','GB-T8.02.01',requirements='Exercise actual authenticated board list/create/select and saved-state routes; assert guild and viewer isolation and durable saved revision; reject expired credentials and malformed or foreign identifiers without side effects; retain exact revision, database fixture and raw integration results',deps=['GB-T8.02.01.T2'],milestone=2,release='MVP',priority='Critical')
add('GB-T12.MVP1','MVP integrated security and collaboration acceptance',12,'Test','GB-T12',requirements='Launch real supported Discord Activity and verify authenticated guild context; demonstrate two simultaneous moderators and backend-enforced read-only viewers; save board state, lock editing and reconnect without losing acknowledged edits; reject expired sessions, foreign guild identifiers and forged writer operations; record actual client/environment evidence and distinguish mocks from platform checks',deps=['GB-T1.01.01.V1','GB-T1.02.02.V1','GB-T2.01.02.V1','GB-T2.03.01.V1','GB-T3.04.02.V1','GB-T4.01.01.V1','GB-T4.01.02.V1','GB-T4.02.01.V1','GB-T4.02.02.V1','GB-T5.02.02.V1','GB-T8.02.01.V2'],milestone=2,release='MVP',priority='Critical')
add('GB-T13.04.01.O1','Publish MVP after accepted release gate',13,'Operations','GB-T13.04.01',requirements='Publish an actual versioned MVP tag and artifacts only after MVP acceptance and release-automation verification pass; attach release notes, checksums, known limitations and rollback/support guidance; verify published artifacts match the accepted candidate and record the actual release URL; do not claim v1.0 or production acceptance from MVP publication',deps=['GB-T13.G1','GB-T13.04.01.V1'],milestone=2,release='MVP',priority='Critical')
add('GB-T13.04.01.O2','Publish stable v1.0 after production approval',13,'Operations','GB-T13.04.01',requirements='Publish a stable versioned release only after the v1.0 approval gate passes; attach reviewed artifacts, provenance, migration notes, security disposition and operator documentation; verify published checksums and actual production smoke evidence; record actual release and deployment receipts without fabricating approvals',deps=['GB-T13.G3','GB-T13.04.01.V1'],milestone=7,release='v1.0',priority='Critical')
by={x['id']:x for x in items}
block('GB-T12.MVP1','GB-T3.02.02.V1','GB-T4.03.02.V1','GB-T1.02.01.V1')
by['GB-T12.MVP1']['requirements'].append('Exercise malicious text and URLs, malformed operations, resource flooding, OAuth replay and origin/session binding; prove rejection or safe rendering without credential exposure or persisted unauthorized side effects')
by['GB-T12.MVP1']['acceptance_criteria'].append('Malicious text/URLs, replayed authentication, malformed operations and quota violations cannot execute active content, widen permissions or corrupt saved state.')
by['GB-T12.MVP1']['expected_tests'].append('Capture negative XSS/link, OAuth replay/origin, malformed-message and message-flood scenarios against the actual integrated MVP.')
block('GB-T13.04.01.T1','GB-T0.03.01.V1')
block('GB-T13.G3','GB-T13.04.01.O1')
gate=by['GB-T13.G1'];gate['dependencies']=[d for d in gate['dependencies'] if d not in ['GB-T12.02.01.V1','GB-T12.03.01.V1','GB-T8.02.01.V1']]+['GB-T12.MVP1','GB-T8.02.01.V2']
block('GB-T8.G1','GB-T8.02.01.V2')
block('GB-T12.G1','GB-T12.MVP1')
# Milestones express executable phase order; MVP does not wait for full v1 verification.
for x in items:
    id=x['id'];t=int(x['workstream'][1:])
    if id in ['GB-T0','GB-T0.D1','GB-T0.G1']:x['milestone']=ms[1]
    if id.endswith('.G1') and t<13:x['milestone']=ms[1 if t==0 else streams[t]['milestone']]
    if t in [2,5,8]:
        rel='v1.0'
        if x['work_type'] in ['Research','Specification']:rel='MVP'
        if t==2 and (id.startswith('GB-T2.01') or id.startswith('GB-T2.03.01')):rel='MVP';x['milestone']=ms[1 if id.startswith('GB-T2.01') else 2]
        if t==5 and (id.startswith('GB-T5.01.01') or id.startswith('GB-T5.02') or id.startswith('GB-T5.03.01')):
            rel='MVP';x['milestone']=ms[1 if id.startswith('GB-T5.02.01') else 2]
        if t==8:
            if id.startswith('GB-T8.01'):rel='MVP';x['milestone']=ms[1]
            elif id in ['GB-T8.02.01.T2','GB-T8.02.01.V2']:rel='MVP';x['milestone']=ms[2]
            elif id.startswith('GB-T8.02'):x['milestone']=ms[3]
            elif x['work_type'] not in ['Research','Specification']:x['milestone']=ms[4]
        x['fields']['Release Target']=rel
        x['labels']=[v for v in x['labels'] if not v.startswith('release:')]+['release: '+('mvp' if rel=='MVP' else 'v1.0')]
    if id in ['GB-T13.04.01.T1','GB-T13.04.01.V1']:
        x['milestone']=ms[2];x['fields']['Release Target']='MVP';x['labels']=[v for v in x['labels'] if not v.startswith('release:')]+['release: mvp']
    if id.endswith(('.O1','.O2')):x['fields']['Risk']='Critical';x['fields']['Effort']='S'
# Handoff documents require the actual verified outcomes they describe.
for t in range(14):
    doc=next(x for x in items if x['id']==f'GB-T{t}.D1')
    doc['dependencies']=list(dict.fromkeys(doc['dependencies']+[x['id'] for x in items if x['workstream']==f'T{t}' and x['work_type']=='Test' and ('.V' in x['id'] or x['id'].endswith('.MVP1')) and x['fields']['Release Target']!='Post-v1.0']))
    gate=next(x for x in items if x['id']==(f'GB-T{t}.G1' if t<13 else 'GB-T13.G3'))
    gate['dependencies'].append(doc['id'])
for x in items:
    x['description']='; '.join(x['requirements'])
    if x['id'].startswith('GB-T13.G'):x['fields']['Risk']='Critical'
config=next(x for x in items if x['id']=='GB-T0.03.02.T1')
config['requirements'].append('Implement the exact parseConfig API, types, files and validation/evidence rules in planning/configuration-contract.md; no global environment reads, network IO or value logging inside the parser')
config['acceptance_criteria'].append('The documented parseConfig contract passes every listed boundary and secret-redaction scenario.')
config['description']='; '.join(config['requirements'])
# No guessed issue URLs: rendering resolves only existing GitHub mappings.
save(ROOT/'planning/guildboard-backlog.json',{'schema_version':1,'repository':state['repo'],'project':state['project'],'items':items})
print('Compiled',len(items),'items')
from collections import Counter
print(Counter(x['work_type'] for x in items))
