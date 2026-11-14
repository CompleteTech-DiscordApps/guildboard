"""Reject deliberately invalid reproductions in normal and optimized interpreters."""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--nginx-binary',required=True);args=parser.parse_args()
script=Path.cwd()/'docs/research/evidence/t10-2026-11-13/acquisition-f0bf9c7/reproduce-before.py'
bootstrap='''import sys,runpy
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
script,binary,out,case=sys.argv[1:]
sys.argv=[script,'--nginx-binary',binary,'--output-directory',out]
original=Path.read_bytes
if case=='harness':
 def read(path):
  return b'malformed harness' if str(path).endswith('tests/research/t10-test-nginx-probe.py') else original(path)
 patch=mock.patch.object(Path,'read_bytes',read)
else:
 import unittest
 outcomes={'no-failures':(0,0,0),'errors':(3,1,0),'skips':(3,0,1),'missing-reports':(3,0,0)}
 failures,errors,skips=outcomes[case]
 result=SimpleNamespace(testsRun=3,failures=[None]*failures,errors=[None]*errors,skipped=[None]*skips)
 patch=mock.patch.object(unittest.TextTestRunner,'run',return_value=result)
with patch:runpy.run_path(script,run_name='__main__')
'''
records=[]
for optimized in (False,True):
 for case in ('harness','no-failures','errors','skips','missing-reports'):
  with tempfile.TemporaryDirectory(prefix='t10-reproducer-rejection-') as directory:
   command=[sys.executable]+(['-O'] if optimized else [])+['-c',bootstrap,str(script),args.nginx_binary,directory,case]
   result=subprocess.run(command,capture_output=True,text=True,timeout=15)
   expected='Harness differs from exact recorded revision' if case=='harness' else ('Unexpected owner report count' if case=='missing-reports' else 'Unexpected regression outcome')
   valid=result.returncode!=0 and expected in result.stderr and 'Verified exact old implementation' not in result.stdout and not (Path(directory)/'before-verified.json').exists()
   records.append({'optimized':optimized,'case':case,'returncode':result.returncode,'expected_error':expected,'explicit_rejection':valid})
   if not valid:raise RuntimeError(json.dumps(records[-1])+result.stdout+result.stderr)
print(json.dumps({'checks':records,'passed':len(records),'result':'All malformed harness/outcome cases rejected without verification output or success artifact'},indent=2))
