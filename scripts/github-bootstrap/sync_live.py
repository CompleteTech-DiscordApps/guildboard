"""Stream native links/triage while issue creation proceeds; never writes the manifest.
Checkpoint is operational state only. Remote readback remains verification authority.
"""
from api import *
import hashlib, concurrent.futures, threading
lock=threading.Lock()
s=json.loads(STATE.read_text());pid=s['project']['id'];fields={f['name']:f for f in api('users/'+s['owner']+'/projectsV2/'+str(s['project']['number'])+'/fields?per_page=100')};cp=ROOT/'planning/enrollment-state.json';checkpoint=json.loads(cp.read_text()) if cp.exists() else {}
while True:
 m=json.loads((ROOT/'planning/guildboard-backlog.json').read_text());by={x['id']:x for x in m['items']};pending=[x for x in m['items'] if x.get('github') and x['id'] not in checkpoint]
 if not pending:
  if len(checkpoint)==len(m['items']):break
  time.sleep(8);continue
 for start in range(0,len(pending),25):
  batch=pending[start:start+25]
  nodes=gql('query($ids:[ID!]!){nodes(ids:$ids){... on Issue{id parent{id} blockedBy(first:100){nodes{id}} projectItems(first:20){nodes{id fullDatabaseId project{id} fieldValues(first:30){nodes{... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2SingleSelectField{name}}}}}}}}}}',ids=[x['github']['id'] for x in batch])['nodes'];live={v['id']:v for v in nodes if v}
  def process(x):
   n=live[x['github']['id']];item=next((v for v in n['projectItems']['nodes'] if v['project']['id']==pid),None)
   if not item:
    item=gql('mutation($i:AddProjectV2ItemByIdInput!){addProjectV2ItemById(input:$i){item{id fullDatabaseId}}}',i={'projectId':pid,'contentId':x['github']['id']})['addProjectV2ItemById']['item'];item['fieldValues']={'nodes':[]}
   variables={};decl=[];muts=[]
   def put(typ,method,data,result):
    key='i'+str(len(decl));decl.append('$'+key+':'+typ+'!');variables[key]=data;muts.append(key+':'+method+'(input:$'+key+'){'+result+'}')
   if x['parent_id']:
    want=by[x['parent_id']]['github']['id']
    if n['parent'] and n['parent']['id']!=want:raise RuntimeError('Conflicting parent '+x['id'])
    if not n['parent']:put('AddSubIssueInput','addSubIssue',{'issueId':want,'subIssueId':x['github']['id']},'issue{id}')
   blockers={v['id'] for v in n['blockedBy']['nodes']}
   for d in x['dependencies']:
    want=by[d]['github']['id']
    if want not in blockers:put('AddBlockedByInput','addBlockedBy',{'issueId':x['github']['id'],'blockingIssueId':want},'issue{id}')
   vals={v['field']['name']:v['name'] for v in item['fieldValues']['nodes'] if v}
   updates=[]
   for k,v in x['fields'].items():
    if vals.get(k)==v:continue
    # Bootstrap owns initial values only. Later executions fill missing metadata.
    if x.get('applied_hash') and k in vals:continue
    f=fields[k];option=next(o['id'] for o in f['options'] if (o['name']['raw'] if isinstance(o['name'],dict) else o['name'])==v)
    updates.append({'id':f['id'],'value':option})
   if x['dependencies']:
    reason=blocker_summary([issue_url(by[d]['github']['number'],s['repo']) for d in x['dependencies']])
    updates.append({'id':fields['Blocking Reason']['id'],'value':reason})
   if muts:gql('mutation('+','.join(decl)+'){'+''.join(muts)+'}',**variables)
   if updates:api('users/'+s['owner']+'/projectsV2/'+str(s['project']['number'])+'/items/'+str(item['fullDatabaseId']),'PATCH',{'fields':updates})
   with lock:
    checkpoint[x['id']]={'project_item_id':item['id'],'applied_hash':hashlib.sha256(json.dumps(x['fields'],sort_keys=True).encode()).hexdigest()};save(cp,checkpoint)
    print('native-linked and triaged',len(checkpoint),'/',len(m['items']),x['id'],flush=True)
  with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
   futures=[pool.submit(process,x) for x in batch]
   for future in concurrent.futures.as_completed(futures):
    try:future.result()
    except RuntimeError as e:print('Retry after refreshed live read:',str(e),flush=True);time.sleep(5)
print('All current manifest issues linked and triaged',flush=True)
