import hashlib
import io
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/licenses'))
import fetch

# Optional local engineering fixture: no network is involved.
FIXTURE = os.environ.get('LICENSE16_ARTIFACT_FIXTURE')
RECEIPT = os.environ.get('LICENSE16_ARTIFACT_RECEIPT')

class Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data); self.url = url
    def geturl(self): return self.url
    def read(self, n=-1):
        if not 0 < n <= 65536: raise AssertionError('unbounded read')
        return super().read(n)

class Opener:
    def __init__(self, mapping, failure=None): self.mapping = mapping; self.failure = failure; self.calls = 0
    def open(self, url, timeout):
        assert timeout == 30
        self.calls += 1
        if self.failure == 'network' and self.calls == 2: raise OSError('interrupted')
        data = self.mapping[url].read_bytes()
        if self.failure == 'mismatch' and self.calls == 2: data += b'x'
        if self.failure == 'oversized' and self.calls == 2: data = b'x' * (fetch.MAX_FILE + 1)
        return Response(data, url + '/redirect' if self.failure == 'redirect' else url)

@unittest.skipUnless(FIXTURE and RECEIPT, 'engineering artifacts and receipt not supplied')
class FetchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        receipt = json.loads(Path(RECEIPT).read_text())
        cls.mapping = {x['url']: Path(FIXTURE) / x['artifact'] for x in receipt['verified']}
        assert len(cls.mapping) == receipt['expected'] == 100
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name); self.output = self.base / 'cache'
    def tearDown(self): self.tmp.cleanup()
    def test_actual_cache(self):
        result = fetch.fetch(ROOT, self.output, Opener(self.mapping))
        self.assertEqual(result['count'], 100)
        self.assertEqual(len(list(self.output.iterdir())), 100)
        inventory = json.loads((ROOT / 'docs/licenses/inventory.json').read_text())
        nested = 0
        for path, c in inventory['components'].items():
            a = c['artifact']; data = (self.output / a['cache_filename']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), a['archive_sha256'])
            import base64
            self.assertEqual('sha512-' + base64.b64encode(hashlib.sha512(data).digest()).decode(), a['integrity'])
            nested += path.count('node_modules/') > 1
        self.assertEqual(nested, 4)
        print('actual cache:', result['count'], 'archives,', result['bytes'], 'bytes, nested:', nested)
    def test_failures_rollback(self):
        for failure in ('network', 'mismatch', 'oversized', 'redirect'):
            with self.subTest(failure=failure):
                with self.assertRaises((fetch.Invalid, OSError)): fetch.fetch(ROOT, self.output, Opener(self.mapping, failure))
                self.assertEqual(list(self.base.iterdir()), [])
    def test_existing_and_symlink(self):
        self.output.mkdir(); marker = self.output / 'keep'; marker.write_text('keep')
        with self.assertRaises(fetch.Invalid): fetch.fetch(ROOT, self.output, Opener(self.mapping))
        self.assertEqual(marker.read_text(), 'keep')
        link = self.base / 'link'; link.symlink_to(self.output, target_is_directory=True)
        with self.assertRaises((fetch.Invalid, OSError)): fetch.fetch(ROOT, link / 'new', Opener(self.mapping))
        self.assertEqual(marker.read_text(), 'keep')
    def test_changed_inputs_rejected(self):
        original = fetch.validate_structure
        def changed(root):
            result = original(root); result['hashes']['package-lock.json'] = '0' * 64; return result
        with mock.patch.object(fetch, 'validate_structure', changed):
            with self.assertRaises(fetch.Invalid): fetch.fetch(ROOT, self.output, Opener(self.mapping))
        self.assertFalse(self.output.exists())
    def test_modified_lock_and_catalog(self):
        copy = self.base / 'root'
        shutil.copytree(ROOT, copy)
        for relative in ('package-lock.json', 'docs/licenses/inventory.json'):
            path = copy / relative
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            if relative.endswith('inventory.json'):
                inventory = json.loads(original)
                inventory['owned_decisions'] = []
                path.write_text(json.dumps(inventory))
            with self.subTest(path=relative), self.assertRaises(fetch.Invalid):
                fetch.fetch(copy, self.output, Opener(self.mapping))
            path.write_bytes(original)
        self.assertFalse(self.output.exists())
    def test_urls(self):
        good = 'https://registry.npmjs.org/@scope/name/-/name-1.tgz'
        fetch._url(good)
        for bad in ('http://registry.npmjs.org/a', 'https://registry.npmjs.org:443/a', 'https://x@registry.npmjs.org/a', 'https://registry.npmjs.org.evil/a', 'https://registry.npmjs.org/a?x', 'https://registry.npmjs.org/a#x', 'https://registry.npmjs.org/a/../b', 'https://registry.npmjs.org/%2e%2e/a'):
            with self.subTest(url=bad), self.assertRaises(fetch.Invalid): fetch._url(bad)

if __name__ == '__main__': unittest.main()
