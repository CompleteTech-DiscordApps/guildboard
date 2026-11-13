"""Owned ephemeral Docker Playwright MCP stdio research; no HTTP service/install.

Uses the existing cached image, network=none, no host mounts or shared session.
Only the exact invocation's labeled container may be removed. No volume exists.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import platform
import subprocess
import threading
import uuid


IMAGE = 'mcp/playwright@sha256:8771dc4666e7c11440bfc6a0c6b00480e9a15b8891b45f29a52d7d995f8d1492'


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    html=(root/'docs/research/t7-outline-prototype.html').read_text(encoding='utf-8')
    tests=(root/'tests/research/t7-browser-checks.js').read_text(encoding='utf-8')
    name='guildboard-t7-'+uuid.uuid4().hex[:12]
    label='tech.complete.guildboard.t7.run'
    process=None
    docker=None
    report={'observed_at_utc':datetime.now(timezone.utc).isoformat(),'image':IMAGE,
            'tested_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'environment':{'platform':platform.platform(),'python':platform.python_version()},
            'container':name,'prototype_sha256':hashlib.sha256(html.encode()).hexdigest(),
            'checks_sha256':hashlib.sha256(tests.encode()).hexdigest(),
            'limits':{'network':'none','cpus':1,'memory_mib':768,'pids':256,'host_mounts':False},
            'browser_sandbox':'Cached image entrypoint explicitly uses --no-sandbox; not production isolation evidence.'}
    lines=queue.Queue()
    def read():
        for line in process.stdout:
            try: lines.put(json.loads(line))
            except json.JSONDecodeError: pass
        lines.put(None)
    serial=0
    def request(method,params):
        nonlocal serial
        serial+=1
        process.stdin.write(json.dumps({'jsonrpc':'2.0','id':serial,'method':method,'params':params})+'\n')
        process.stdin.flush()
        while True:
            message=lines.get(timeout=45)
            if message is None: raise RuntimeError('owned MCP process exited')
            if message.get('id')==serial:
                if 'error' in message: raise RuntimeError(str(message['error']))
                return message['result']
    failed=False
    try:
        context=subprocess.check_output(['docker','context','show'],text=True,stderr=subprocess.PIPE).strip()
        report['context']=context
        docker=['docker','--context',context]
        subprocess.run([*docker,'image','inspect',IMAGE],check=True,capture_output=True,text=True)
        process=subprocess.Popen([*docker,'run','--pull=never','--rm','--init','-i','--name',name,
                                  '--label',label+'='+name,'--network=none','--cpus=1',
                                  '--memory=768m','--pids-limit=256',IMAGE],
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                                 text=True,encoding='utf-8',bufsize=1)
        threading.Thread(target=read,daemon=True).start()
        init=request('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'guildboard-t7-research','version':'1'}})
        report['mcp_server']=init.get('serverInfo')
        process.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');process.stdin.flush()
        names=[t['name'] for t in request('tools/list',{})['tools']]
        tool=next(n for n in ('browser_run_code','browser_run_code_unsafe') if n in names)
        code='async (page) => { await page.setContent('+json.dumps(html)+'); return await ('+tests+')(page); }'
        result=request('tools/call',{'name':tool,'arguments':{'code':code}})
        text='\n'.join(c.get('text','') for c in result.get('content',[]) if c['type']=='text')
        if result.get('isError'): raise RuntimeError(text[:2000])
        marker='### Result\n'
        if marker not in text: raise RuntimeError('MCP did not return structured browser result: '+text[:1000])
        payload=text.split(marker,1)[1].split('\n### ',1)[0].strip()
        report['browser_result']=json.loads(payload)
        if report['browser_result'].get('result')!='pass': raise RuntimeError('browser result failed')
        target=root/'docs/research/t7-fixture.png'
        subprocess.run([*docker,'cp',name+':/tmp/guildboard-t7-fixture.png',str(target)],check=True,capture_output=True)
        report['screenshot_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
        report['result']='pass'
    except Exception as error:
        failed=True;report.update(result='blocked-or-failed',error_type=type(error).__name__,error=str(error))
        if isinstance(error,subprocess.CalledProcessError): report['command_stderr']=error.stderr
    finally:
        if process is None:
            report['owned_container_absent']=True
            report['cleanup_note']='No container process was started; preflight failed.'
        else:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill();process.wait(timeout=5)
            try:
                inspect=subprocess.run([*docker,'container','inspect',name],capture_output=True,text=True)
                if inspect.returncode==0:
                    owner=json.loads(inspect.stdout)[0]['Config']['Labels'].get(label)
                    if owner!=name: raise RuntimeError('refusing cleanup without exact ownership label')
                    # --rm may remove it between inspect and rm; verify absence below.
                    subprocess.run([*docker,'rm','--force',name],capture_output=True)
                remaining=subprocess.check_output([*docker,'ps','-a','--format','{{.Names}}'],text=True).splitlines()
                report['owned_container_absent']=name not in remaining
                if not report['owned_container_absent']: raise RuntimeError('owned container remains after cleanup')
            except Exception as error:
                failed=True;report.update(result='blocked-or-failed',cleanup_error=str(error))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes((json.dumps(report,indent=2,sort_keys=True)+'\n').encode())
    print(json.dumps({k:report.get(k) for k in ('result','owned_container_absent','error')}))
    return int(failed)


if __name__=='__main__':
    raise SystemExit(main())
