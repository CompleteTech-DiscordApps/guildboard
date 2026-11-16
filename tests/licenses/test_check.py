import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).absolute().parents[2]
SPEC = importlib.util.spec_from_file_location('license_check', ROOT / 'scripts/licenses/check.py')
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)

class Contract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'checkout'
        shutil.copytree(ROOT, self.root)
        self.inventory = self.root / 'docs/licenses/inventory.json'
        self.inv = json.loads(self.inventory.read_bytes())
    def tearDown(self): self.temp.cleanup()
    def save(self): self.inventory.write_text(json.dumps(self.inv))
    def invalid(self):
        self.save()
        with self.assertRaises(check.Invalid): check.validate_structure(self.root)
    def anchor(self, path):
        self.inv['input_sha256'][path] = hashlib.sha256((self.root / path).read_bytes()).hexdigest()
    def test_actual_assessment(self):
        result = check.assess(self.root)
        self.assertTrue(result['structure_valid'])
        self.assertEqual(result['counts'], {'components':100, 'sections':246, 'notices':62})
        self.assertEqual(len(result['diagnostics']), 13)
        self.assertEqual(sum(d['kind']=='section' for d in result['diagnostics']),9)
        self.assertEqual(sum(d['kind']=='classification' for d in result['diagnostics']),1)
        self.assertEqual(sum(d['kind']=='notice_coverage' for d in result['diagnostics']),2)
        self.assertEqual(sum(d['kind']=='distribution_scope' for d in result['diagnostics']),1)
        with patch('sys.argv', ['check', '--root', str(self.root)]), patch('sys.stdout'):
            self.assertEqual(check.main(), 1)
    def test_notice_missing_or_corrupt(self):
        p = self.root / self.inv['retained_notices'][0]['path']; original = p.read_bytes()
        for value in (None, b'altered'):
            if value is None: p.unlink()
            else: p.write_bytes(value)
            with self.assertRaises(check.Invalid): check.validate_structure(self.root)
            p.write_bytes(original)
    def test_lock_bijection_with_updated_anchor(self):
        path='package-lock.json'; lock=json.loads((self.root/path).read_bytes()); packages=lock['packages']
        key=next(k for k in self.inv['components'] if k.count('node_modules/')>1)
        for change in ('remove','add','nested'):
            altered=copy.deepcopy(lock)
            if change=='remove': del altered['packages'][key]
            elif change=='add': altered['packages']['node_modules/new-package']=copy.deepcopy(packages[key])
            else: altered['packages']['node_modules/new-parent/node_modules/new-package']=altered['packages'].pop(key)
            (self.root/path).write_text(json.dumps(altered)); self.anchor(path); self.invalid()
    def test_classification_missing_unknown_and_mismatch(self):
        key=next(iter(self.inv['components'])); original=copy.deepcopy(self.inv['components'][key])
        for kind in ('missing','unknown','mismatch','obligations'):
            c=self.inv['components'][key]=copy.deepcopy(original)
            if kind=='missing': del c['classification']
            elif kind=='unknown': c['classification']['status']='unknown'
            elif kind=='mismatch': c['effective_classification']['rationale']='changed'
            else: c['classification']['obligations']=[None]
            self.invalid()
    def test_supplement_duplicate_and_missing(self):
        sections=self.inv['prettier_supplemental']['sections']; original=copy.deepcopy(sections)
        sections.append(copy.deepcopy(sections[0])); self.invalid()
        sections[:]=original[1:]; self.invalid()
    def test_duplicate_and_missing_ordinal(self):
        self.inv['prettier_original_sections'][1]['ordinal']=1; self.invalid()
        del self.inv['prettier_original_sections'][1]; self.invalid()
    def test_forged_section_and_matching_hash(self):
        o=self.inv['prettier_original_sections'][0]; o['full_notice_text']+='forged'; o['notice_byte_length']=len(o['full_notice_text'].encode()); o['section_sha256']=hashlib.sha256(o['full_notice_text'].encode()).hexdigest()
        self.inv['effective_prettier_sections'][0]['original_decision']=copy.deepcopy(o)
        for s in self.inv['prettier_supplemental']['sections']:
            if s['ordinal']==1: s['original_decision']=copy.deepcopy(o)
        self.invalid()
    def test_duplicate_json_keys(self):
        self.inventory.write_text('{"schema_version":3,"schema_version":3}')
        with self.assertRaises(check.Invalid): check.validate_structure(self.root)
    def test_path_traversal(self):
        r=check.Reader(self.root)
        try:
            for p in ('../package.json','/package.json','docs/../package.json'):
                with self.assertRaises(check.Invalid): r.read(p)
        finally: r.close()
    def test_root_ancestor_and_leaf_symlinks(self):
        link=Path(self.temp.name)/'link'; link.symlink_to(self.root, target_is_directory=True)
        for p in (link, link/'docs'):
            with self.assertRaises((check.Invalid,OSError)): check.Reader(p)
        leaf=self.root/'package.json'; leaf.unlink(); leaf.symlink_to(self.root/'package-lock.json')
        with self.assertRaises(check.Invalid): check.validate_structure(self.root)
    def test_fifo_and_oversize(self):
        p=self.root/'package.json'; p.unlink(); os.mkfifo(p)
        with self.assertRaises(check.Invalid): check.validate_structure(self.root)
        p.unlink(); p.write_bytes(b'x'*(check.MAX_FILE+1))
        with self.assertRaises(check.Invalid): check.validate_structure(self.root)
    def test_interrupted_read(self):
        with patch.object(check.os,'read',side_effect=OSError('interrupted')):
            with self.assertRaises(check.Invalid): check.validate_structure(self.root)
    def test_file_membership_replacement(self):
        r=check.Reader(self.root); p=self.root/'package.json'; original=check.os.read; done=False
        def replacement(fd, size):
            nonlocal done
            if not done:
                done=True; p.rename(p.with_suffix('.old')); p.write_bytes(b'{}')
            return original(fd,size)
        try:
            with patch.object(check.os,'read',side_effect=replacement):
                with self.assertRaises(check.Invalid): r.read('package.json')
        finally: r.close()
    def test_directory_membership_replacement(self):
        r=check.Reader(self.root); p=self.root/'docs/licenses'; original=check.os.read; done=False
        def replacement(fd, size):
            nonlocal done
            if not done:
                done=True; p.rename(p.with_name('old-licenses')); p.mkdir()
            return original(fd,size)
        try:
            with patch.object(check.os,'read',side_effect=replacement):
                with self.assertRaises(check.Invalid): r.read('docs/licenses/inventory.json',2*1024*1024)
        finally: r.close()

if __name__ == '__main__': unittest.main()
