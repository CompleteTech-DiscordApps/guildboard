"""In-process counterexamples using actual fetched sources; no network or child process."""
import importlib.util, json, os, pathlib, shutil, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('verify14',ROOT/'scripts/verification/verify_editor_feasibility.py'); v=importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
REV='eeda9759b9f6a2e9dd9eeede4b66be55a270af66'
class Checks(unittest.TestCase):
 def setUp(self):
  if 'EDITOR14_INPUTS' not in os.environ: raise unittest.SkipTest('EDITOR14_INPUTS is not set; actual source fixtures are unavailable')
  if not os.environ['EDITOR14_INPUTS']: raise ValueError('EDITOR14_INPUTS must be a nonempty path')
  self.source_inputs=pathlib.Path(os.environ['EDITOR14_INPUTS'])
  self.t=tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup); self.d=pathlib.Path(self.t.name); self.root=self.d/'root'; self.inputs=self.d/'inputs'; shutil.copytree(self.source_inputs,self.inputs)
  for name in ['docs/research/editor14/source-ledger.json','docs/research/feasibility-pins.json','docs/research/editor13/evaluated-matrix.json']:
   p=self.root/name; p.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(ROOT/name,p)
 def runcheck(self): return v.verify(self.root,self.inputs,REV)
 def test_positive(self): self.assertEqual(len(self.runcheck()['source_hashes']),14)
 def test_corruption(self):
  p=self.inputs/'public/react_19.1.0.json'; p.write_bytes(p.read_bytes()+b'x')
  with self.assertRaises(ValueError): self.runcheck()
 def test_peer_with_ledger_update(self):
  p=self.inputs/'public/excalidraw-0.18.1-declarations/package.json'; data=json.loads(p.read_bytes()); data['peerDependencies']['react']='^16.0.0'; p.write_text(json.dumps(data)); ledger=self.root/'docs/research/editor14/source-ledger.json'; d=json.loads(ledger.read_text()); d['sources']['public/excalidraw-0.18.1-declarations/package.json']['sha256']=v.digest(p.read_bytes()); ledger.write_text(json.dumps(d))
  with self.assertRaises(ValueError): self.runcheck()
 def test_missing_fifo_symlink(self):
  p=self.inputs/'public/fastify_5.6.1.json'; p.unlink()
  with self.assertRaises(OSError): self.runcheck()
  os.mkfifo(p)
  with self.assertRaises(ValueError): self.runcheck()
  p.unlink(); p.symlink_to(self.source_inputs/'public/fastify_5.6.1.json')
  with self.assertRaises(OSError): self.runcheck()
 def test_parent_symlink(self):
  p=self.inputs/'public/excalidraw-0.18.1-declarations'; shutil.rmtree(p); p.symlink_to(self.source_inputs/'public/excalidraw-0.18.1-declarations',target_is_directory=True)
  with self.assertRaises(OSError): self.runcheck()
 def test_pin_and_runtime_claim(self):
  p=self.root/'docs/research/editor13/evaluated-matrix.json'; original=json.loads(p.read_text()); d=json.loads(json.dumps(original)); d['clauses'][0]['evaluated_versions']='Excalidraw 999'; p.write_text(json.dumps(d))
  with self.assertRaises(ValueError): self.runcheck()
  original['clauses'][0]['result_and_limit']='runtime fully proven'; p.write_text(json.dumps(original))
  with self.assertRaises(ValueError): self.runcheck()
 def test_revision_and_path(self):
  with self.assertRaises(ValueError): v.verify(self.root,self.inputs,'not-a-sha')
  p=self.root/'docs/research/editor14/source-ledger.json'; d=json.loads(p.read_text()); d['sources']['../escape']=d['sources'].pop(next(iter(d['sources']))); p.write_text(json.dumps(d))
  with self.assertRaises(ValueError): self.runcheck()
 def test_interrupted_output(self):
  p=self.d/'result'; p.write_text('prior\n')
  with self.assertRaises(InterruptedError): v.publish(p,{'new':True},True)
  self.assertEqual(p.read_text(),'prior\n')
if __name__=='__main__': unittest.main()
