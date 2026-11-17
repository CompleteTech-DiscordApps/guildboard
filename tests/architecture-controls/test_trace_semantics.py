import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('trace_gate', ROOT / 'scripts/architecture-controls/check.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)

class TraceSemantics(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ['TMPDIR'])
        self.root = Path(self.temp.name)/'tree'
        shutil.copytree(ROOT, self.root)
        self.path = self.root/'docs/architecture-controls/traceability.json'
        self.trace = json.loads(self.path.read_text())
    def tearDown(self): self.temp.cleanup()
    def reject(self):
        self.path.write_text(json.dumps(self.trace))
        with self.assertRaises(gate.Invalid): gate.check_trace(self.root)
    def test_membership_follows_canonical_requirement_arrays(self):
        cases = json.loads((ROOT/'docs/requirements/fixtures/GB-T0-01-01-use-cases.json').read_text())['cases']
        for case in cases:
            for rid in case['requirements']:
                with self.subTest(rid=rid, case=case['id']):
                    self.trace = json.loads((ROOT/'docs/architecture-controls/traceability.json').read_text())
                    self.trace['requirements'][rid]['use_cases'].remove(case['id']); self.reject()
    def test_required_semantic_links_and_fids(self):
        for rid, key, value in [('R05','interactions','I09'),('R05','canonical_acceptance','F10'),('R05','interactions','I14'),('R05','canonical_acceptance','F07'),('R05','canonical_acceptance','F21'),('R05','canonical_acceptance','F32'),('R06','interactions','I12'),('R06','canonical_acceptance','F13'),('R06','interactions','I11'),('R06','interactions','I06')]:
            with self.subTest(rid=rid,key=key,value=value):
                self.trace = json.loads((ROOT/'docs/architecture-controls/traceability.json').read_text())
                self.trace['requirements'][rid][key].remove(value); self.reject()
    def test_valid_but_unrelated_mappings_rejected(self):
        for rid,key,value in [('R05','interactions','I10'),('R05','canonical_acceptance','F15'),('R06','interfaces','bot'),('R02','controls','release')]:
            with self.subTest(rid=rid,key=key,value=value):
                self.trace = json.loads((ROOT/'docs/architecture-controls/traceability.json').read_text())
                self.trace['requirements'][rid][key].append(value); self.reject()
    def test_unrelated_interaction_and_its_valid_fid_together_rejected(self):
        self.trace['requirements']['R05']['interactions'].append('I10')
        self.trace['requirements']['R05']['canonical_acceptance'].append('F15')
        self.reject()
