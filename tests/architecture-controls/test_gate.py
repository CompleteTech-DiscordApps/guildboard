import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('architecture_gate', ROOT / 'scripts/architecture-controls/check.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)

class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.base = Path(self.temp.name)/'base'; self.head = Path(self.temp.name)/'head'
        shutil.copytree(ROOT, self.base); shutil.copytree(ROOT, self.head)
    def tearDown(self): self.temp.cleanup()
    def save(self, root, name, value): (root/name).write_text(json.dumps(value))
    def seal(self): self.save(self.head, 'docs/architecture-controls/baseline.json', {'version':1,'boundaries':gate.inventory(self.head)})
    def record(self, path, old, new):
        p='docs/architecture-controls/decisions.json'
        self.save(self.head,p,{'version':1,'records':[{'id':'DEC-0001','revision':1,'boundary':path,'old_sha256':old,'new_sha256':new,'rationale':'Review impact','alternatives':['Keep previous interface'], 'controls':['docs/security/GB-T0-04-02-threat-model.md'],'test_evidence':['tests/architecture-controls/test_gate.py']}]})
    def digest(self, root, path):
        p=root/path
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    def test_unchanged(self): self.assertEqual(gate.check(self.base,self.head),0)
    def test_changed_requires_matching_record(self):
        p='apps/api/README.md'; old=self.digest(self.base,p); (self.head/p).write_text('changed'); self.seal(); new=self.digest(self.head,p)
        with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
        self.record(p,old,new); self.assertEqual(gate.check(self.base,self.head),1)
    def test_add_remove_and_rename(self):
        for action in ('add','remove','rename'):
            with self.subTest(action=action):
                shutil.rmtree(self.head); shutil.copytree(self.base,self.head)
                oldpath='apps/api/package.json'; newpath='apps/api/new-interface.json'
                if action == 'add': (self.head/newpath).write_text('new')
                if action == 'remove': (self.head/oldpath).unlink()
                if action == 'rename': (self.head/oldpath).rename(self.head/newpath)
                self.seal()
                with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
                if action != 'rename':
                    p=newpath if action=='add' else oldpath
                    self.record(p,self.digest(self.base,p),self.digest(self.head,p)); self.assertEqual(gate.check(self.base,self.head),1)
                else:
                    self.record(oldpath,self.digest(self.base,oldpath),None)
                    with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
                    f=self.head/'docs/architecture-controls/decisions.json'; x=json.loads(f.read_text()); rec=dict(x['records'][0],id='DEC-0002',boundary=newpath,old_sha256=None,new_sha256=self.digest(self.head,newpath)); x['records'].append(rec); f.write_text(json.dumps(x)); self.assertEqual(gate.check(self.base,self.head),2)
    def test_unrelated_or_invalid_decision(self):
        p='apps/api/README.md'; (self.head/p).write_text('changed'); self.seal()
        self.record('docs/adr/0002-server-authority-and-interactions.md',self.digest(self.base,p),self.digest(self.head,p))
        with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
        self.record(p,self.digest(self.base,p),self.digest(self.head,p)); f=self.head/'docs/architecture-controls/decisions.json'; x=json.loads(f.read_text()); x['records'][0]['alternatives']=[]; f.write_text(json.dumps(x))
        with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
    def test_trace_shape_and_missing_ids(self):
        f=self.head/'docs/architecture-controls/traceability.json'; x=json.loads(f.read_text()); del x['requirements']['R01']; f.write_text(json.dumps(x))
        with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
        x=json.loads((self.base/'docs/architecture-controls/traceability.json').read_text()); x['unknown']=True; f.write_text(json.dumps(x))
        with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
    def test_missing_prerequisite_and_baseline_tampering(self):
        (self.head/'apps/api/README.md').unlink()
        with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
        shutil.rmtree(self.head); shutil.copytree(self.base,self.head)
        (self.head/'apps/api/README.md').write_text('edited'); self.seal()
        # Head baseline cannot replace the independently supplied base baseline.
        with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
        (self.base/'docs/architecture-controls/baseline.json').unlink()
        with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
    def test_interruption_does_not_write_or_promote(self):
        p=self.head/'docs/architecture-controls/baseline.json'; before=p.read_bytes()
        with mock.patch.object(gate,'check_trace',side_effect=OSError('interrupted')):
            with self.assertRaises(OSError): gate.check(self.base,self.head)
        self.assertEqual(p.read_bytes(),before)
        self.assertFalse(list(self.head.glob('**/*.promoted')))
    def test_unavailable_evidence_and_oversize(self):
        p='apps/api/README.md'; (self.head/p).write_text('changed'); self.seal(); self.record(p,self.digest(self.base,p),self.digest(self.head,p))
        (self.head/'tests/architecture-controls/test_gate.py').unlink()
        with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
        (self.head/p).write_bytes(b'x'*(gate.MAX_FILE+1))
        with self.assertRaises(gate.Invalid): gate.check(self.base,self.head)
if __name__ == '__main__': unittest.main()
