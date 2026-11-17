"""GitHub transport. Uses gh keyring authentication; never logs credentials."""
import json, subprocess, time, pathlib, datetime, re
ROOT=pathlib.Path(__file__).resolve().parents[2]
STATE=ROOT/'planning/github-state.json'
TRANSFERRED_REPOSITORY = 'CompleteDotTech/guildboard'
TRANSFERRED_REPOSITORY_LINK = re.compile(
 r'https://github\.com/' + re.escape(TRANSFERRED_REPOSITORY) + r'(?=[/?#)\s]|$)',
 re.IGNORECASE,
)
def save(path,data):
 path=pathlib.Path(path); tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');tmp.replace(path)
def api(path,method='GET',data=None,*,quiet_get=False):
 if quiet_get and (method != 'GET' or data is not None):
  raise ValueError('quiet transport only supports GET without a body')
 if method!='GET' and path.startswith('repos/Pick-Your-AI/'):
  raise RuntimeError('Reference organization is read-only in this bootstrap')
 if path=='graphql' and data and 'mutation' in data.get('query','') and 'PVT_kwDOFHg4Xc4BnUon' in json.dumps(data) and 'copyProjectV2' not in data.get('query',''):
  raise RuntimeError('Reference Project is read-only in this bootstrap')
 args=['gh','api',path,'--method',method,'--include']
 if data is not None: args+=['--input','-']
 for attempt in range(6):
  p=subprocess.run(args,input=json.dumps(data) if data is not None else None,capture_output=True,text=True)
  header,sep,payload=p.stdout.partition('\n\n')
  if not sep:payload=p.stdout;header=''
  response_headers={}
  for line in header.splitlines():
   if ':' in line:
    key,value=line.split(':',1);response_headers[key.lower()]=value.strip()
  if p.returncode==0:
   result=json.loads(payload) if payload.strip() else {}
   if not isinstance(result,dict) or not result.get('errors'): return result
  else: result={'stderr':p.stderr,'response':payload,'rate':{k:response_headers.get(k) for k in ['retry-after','x-ratelimit-remaining','x-ratelimit-reset']}}
  if quiet_get:
   # A preview must leave no local trace or reveal the failed response.
   raise RuntimeError('GitHub issue read failed')
  (ROOT/'planning/audit/failures.jsonl').open('a').write(json.dumps({'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'endpoint':path,'method':method,'error':result})+'\n')
  retryable=any(t in json.dumps(result).lower() for t in ['rate limit','secondary','502','503','timeout'])
  read_query=path=='graphql' and data and data.get('query','').lstrip().startswith('query')
  if read_query and 'something went wrong' in json.dumps(result).lower():retryable=True
  if method=='POST' and path.endswith('/issues'):retryable=False  # uncertain creates must refresh stable markers before retry
  if retryable:
   delay=max(60 if 'secondary' in json.dumps(result).lower() else 5,2**attempt*5)
   try:delay=max(delay,int(response_headers.get('retry-after','0')))
   except ValueError:pass
   if response_headers.get('x-ratelimit-remaining')=='0':
    try:delay=max(delay,int(response_headers['x-ratelimit-reset'])-time.time()+1)
    except (KeyError,ValueError):pass
   time.sleep(delay);continue
  raise RuntimeError(json.dumps(result))
 raise RuntimeError('GitHub retry budget exhausted')
def issue_url(number, repo):
 """Build the issue URL from its number and repository identity."""
 return f'https://github.com/{repo}/issues/{number}'

def canonicalize_transferred_links(text, repo):
 return TRANSFERRED_REPOSITORY_LINK.sub(f'https://github.com/{repo}', text)

def issue_mapping(issue, repo):
 return {'number': issue['number'], 'url': issue_url(issue['number'], repo), 'id': issue['node_id']}

def gql(query,**variables):return api('graphql','POST',{'query':query,'variables':variables})['data']
FIELD_FRAGMENT='... on ProjectV2Field{id name dataType} ... on ProjectV2SingleSelectField{id name dataType options{id name color description}}'
def project():
 s=json.loads(STATE.read_text());return gql('query($id:ID!){node(id:$id){... on ProjectV2{id title url number public owner{... on User{login} ... on Organization{login}} fields(first:100){nodes{'+FIELD_FRAGMENT+'}} views(first:100){nodes{id number name layout filter sortByFields(first:10){nodes{direction field{'+FIELD_FRAGMENT+'}}} groupByFields(first:10){nodes{'+FIELD_FRAGMENT+'}} verticalGroupByFields(first:10){nodes{'+FIELD_FRAGMENT+'}} configuration{visibleFields(first:100){nodes{'+FIELD_FRAGMENT+'}}}}} workflows(first:100){nodes{id name enabled}} repositories(first:50){nodes{nameWithOwner}}}}}',id=s['project']['id'])['node']

def blocker_summary(urls):
 """Project text cells are capped at 256 characters; native links retain all detail."""
 urls=sorted(set(urls));numbers=[u.rstrip('/').split('/')[-1] for u in urls]
 if not urls:return None
 prefix='Await '+str(len(urls))+' prerequisites: '+', '.join('#'+n for n in numbers)+'; first: '+urls[0]
 if len(prefix)<=256:return prefix
 return 'Await '+str(len(urls))+' native prerequisites; first: '+urls[0]+'; see native blocked-by panel for the complete list.'
