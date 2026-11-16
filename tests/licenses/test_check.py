import hashlib
import base64
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('license_check', Path(__file__).resolve().parents[2] / 'scripts/licenses/check.py')
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

def digest(b): return hashlib.sha256(b).hexdigest()
class PolicyCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name); self.modules = self.root/'modules'; self.modules.mkdir(); self.artifacts = self.root/'artifacts'; self.artifacts.mkdir()
        for d in ('apps', 'packages', 'docs/licenses'): (self.root/d).mkdir(parents=True)
        self.write('package.json', {'devDependencies': {'a': '1'}})
        self.write('package-lock.json', {'lockfileVersion':3,'packages':{'node_modules/a':{'version':'1','resolved':'https://example/a','integrity':'sha512-'+base64.b64encode(hashlib.sha512(b'a').digest()).decode(),'license':'MIT'},'node_modules/b':{'version':'2','resolved':'https://example/b','integrity':'sha512-'+base64.b64encode(hashlib.sha512(b'b').digest()).decode(),'license':'MIT'}}})
        components=[]
        for name,version,rel,integrity in [('a','1','direct','sha512-'+base64.b64encode(hashlib.sha512(b'a').digest()).decode()),('b','2','transitive','sha512-'+base64.b64encode(hashlib.sha512(b'b').digest()).decode())]:
            (self.artifacts/(name+'.tgz')).write_bytes(name.encode()); (self.modules/name).mkdir(); (self.modules/name/'LICENSE').write_bytes(b'notice')
            components.append({'name':name,'artifact':name+'.tgz','version':version,'source':'https://example/'+name,'integrity':integrity,'spdx':'MIT','relationship':rel,'use':'build','runtime':'not established','notices':[{'path':name+'/LICENSE','sha256':digest(b'notice')}]})
        self.inv={'schema':1,'inputs':{p:digest((self.root/p).read_bytes()) for p in ('package.json','package-lock.json')},'components':components,'unresolved':['distribution']}
        self.save()
        self.marker=self.root/'accepted.json'; self.marker.write_text('previous')
    def tearDown(self): self.tmp.cleanup()
    def write(self,path,value): (self.root/path).write_text(json.dumps(value))
    def save(self): self.write('docs/licenses/inventory.json', self.inv)
    def runcheck(self): return check.check(self.root,self.modules,self.artifacts)
    def blocked(self):
        with self.assertRaises((check.Invalid, OSError, ValueError)): self.runcheck()
        self.assertEqual(self.marker.read_text(),'previous')
    def test_positive(self): self.assertEqual(self.runcheck(),2)
    def test_omitted_transitive_and_direct(self):
        for index in (0,1):
            old=self.inv['components'].pop(index); self.save(); self.blocked(); self.inv['components'].insert(index,old)
    def test_changed_lock_and_manifest(self):
        for path in ('package-lock.json','package.json'):
            old=(self.root/path).read_bytes(); (self.root/path).write_bytes(old+b' '); self.blocked(); (self.root/path).write_bytes(old)
    def test_changed_notice_and_unavailable(self):
        p=self.modules/'b/LICENSE'; p.write_text('changed'); self.blocked(); p.unlink(); self.blocked()
    def test_changed_and_unavailable_artifact(self):
        p=self.artifacts/'a.tgz'; p.write_bytes(b'changed'); self.blocked(); p.unlink(); self.blocked()
    def test_unknown_and_conflicting_license(self):
        for value in ('UNKNOWN','Apache-2.0',None):
            self.inv['components'][0]['spdx']=value; self.save(); self.blocked()
    def test_upgrade_and_missing_notice(self):
        self.inv['components'][0]['version']='2'; self.save(); self.blocked()
        self.inv['components'][0]['version']='1'; self.inv['components'][0]['notices']=[]; self.save(); self.blocked()
    def test_invalid_json_duplicate_and_oversize(self):
        p=self.root/'docs/licenses/inventory.json'
        for raw in (b'{', b'{"schema":1,"schema":1}', b' '*(check.LIMIT+1)):
            p.write_bytes(raw); self.blocked()
    def test_symlink_and_nonregular(self):
        p=self.modules/'a/LICENSE'; p.unlink(); p.symlink_to(self.modules/'b/LICENSE'); self.blocked(); p.unlink(); p.mkdir(); self.blocked()
    def test_interrupted_run_preserves_record(self):
        with patch.object(check, 'read', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt): self.runcheck()
        self.assertEqual(self.marker.read_text(),'previous')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['accepted.json','apps','artifacts','docs','modules','package-lock.json','package.json','packages'])
    def test_new_workspace(self):
        p=self.root/'apps/new'; p.mkdir(); (p/'package.json').write_text('{}'); self.blocked()
if __name__ == '__main__': unittest.main()
