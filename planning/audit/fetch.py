import json,subprocess,sys
q='''query($c:String){repository(owner:"CompleteTech-DiscordApps",name:"guildboard"){issues(first:100,after:$c,states:[OPEN,CLOSED]){pageInfo{hasNextPage endCursor} nodes{number title state stateReason body labels(first:20){nodes{name}} milestone{title} blockedBy(first:50){nodes{number state}} parent{number} subIssues(first:50){nodes{number state}}}}}}'''
out=[];c=None
while True:
  args=['gh','api','graphql','-f','query='+q]+(['-f','c='+c] if c else [])
  d=json.loads(subprocess.check_output(args))['data']['repository']['issues']
  out+=d['nodes']
  if not d['pageInfo']['hasNextPage']:break
  c=d['pageInfo']['endCursor']
import re
for i in out:
  m=re.search(r'guildboard-id:\s*([^\s>]+)',i['body'] or '');i['gb']=m.group(1) if m else None
  i['bodylen']=len(i['body'] or '')
json.dump(out,open('issues.json','w'))
print(len(out),sum(i['state']=='OPEN' for i in out))
