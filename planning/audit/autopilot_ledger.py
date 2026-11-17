#!/usr/bin/env python3
"""Generate planning/audit/autopilot-ledger.md from live GitHub state. Usage: ledger.py <repo_dir> [notes_file]"""
import json,subprocess,sys,re,collections,datetime,pathlib
repo_dir=pathlib.Path(sys.argv[1]); notes=pathlib.Path(sys.argv[2]).read_text() if len(sys.argv)>2 else ''
here=pathlib.Path(__file__).parent
subprocess.check_call([sys.executable,str(here/'fetch.py')],cwd=here,stdout=subprocess.DEVNULL)
I={i['number']:i for i in json.load(open(here/'issues.json'))}
def lab(i,p):
  return ','.join(l['name'][len(p):] for l in i['labels']['nodes'] if l['name'].startswith(p))
depth={}
def d(n):
  if n in depth: return depth[n]
  depth[n]=-1
  bl=[b['number'] for b in I[n]['blockedBy']['nodes'] if b['state']=='OPEN' and b['number'] in I]
  depth[n]=0 if not bl else 1+max(d(b) for b in bl)
  return depth[n]
op=[n for n in I if I[n]['state']=='OPEN']
for n in op: d(n)
prs=json.loads(subprocess.check_output(['gh','pr','list','-R','CompleteTech-DiscordApps/guildboard','--state','open','--limit','100','--json','number,title,isDraft,additions,deletions,mergeable,headRefName,statusCheckRollup']))
L=[f"# Autopilot ledger\n\nGenerated {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')} from live GitHub state by the delegated-maintainer autopilot (Claude). Regenerate; do not hand-edit tables.\n",
f"Open issues: {len(op)} / {len(I)}. Blocked-external: {sum('blocked: external' in lab(I[n],'') for n in op)}.\n",
notes,"\n## Open PRs\n\n| PR | Draft | Mergeable | Checks | Diff | Branch | Title |\n|---|---|---|---|---|---|---|"]
for p in prs:
  ch=collections.Counter((c.get('conclusion') or c.get('state') or '?') for c in p['statusCheckRollup'])
  L.append(f"| #{p['number']} | {p['isDraft']} | {p['mergeable']} | {dict(ch)} | +{p['additions']}/-{p['deletions']} | `{p['headRefName']}` | {p['title']} |")
L.append("\n## Open issues by wave (wave = longest chain of open native blockers)\n\n| Wave | # | GB ID | Type | Release | Open blockers | Labels |\n|---|---|---|---|---|---|---|")
rel={'mvp':0,'v1.0':1,'post-v1.0':2}
for n in sorted(op,key=lambda n:(depth[n],rel.get(lab(I[n],'release: ').split(',')[0],3),I[n]['gb'] or '')):
  i=I[n]; bl=' '.join(f"#{b['number']}" for b in i['blockedBy']['nodes'] if b['state']=='OPEN')
  extra=','.join(l['name'] for l in i['labels']['nodes'] if l['name'].startswith('blocked'))
  L.append(f"| {depth[n]} | #{n} | {i['gb']} | {lab(i,'type: ')} | {lab(i,'release: ')} | {bl} | {extra} |")
L.append("\n## Closed issues\n\n"+', '.join(f"#{n} {I[n]['gb']}" for n in sorted(I) if I[n]['state']=='CLOSED'))
out=repo_dir/'planning/audit/autopilot-ledger.md'; out.write_text('\n'.join(L)+'\n'); print(out, len(op))
