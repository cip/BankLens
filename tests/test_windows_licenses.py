"""Synthetic checks for the Windows notice collection and provenance files."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'packaging/windows/collect_licenses.py'
spec = importlib.util.spec_from_file_location('banklens_license_collection', SCRIPT)
collection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collection)


class LicenseCollectionTests(unittest.TestCase):
    def test_collects_notices_and_rejects_unexpected_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            proxy = root / 'proxy.py'
            proxy.write_text('synthetic')
            report = root / 'report.json'
            report.write_text(json.dumps({'install': [{'metadata': {'name': 'pypdf', 'version': '6.10.0'},
                'download_info': {'archive_info': {'hashes': {'sha256': 'synthetic-hash'}}}}]}))
            original_sha = collection.sha
            def fake_sha(path):
                return ('d1539d95e1a713c068ca81d42e047b2c76568964cf277596d4e19efb22f476be'
                        if path == proxy else original_sha(path))
            fake_spec = type('Spec', (), {'origin': str(proxy)})()
            with patch.object(collection, 'PACKAGES', {'pypdf': '6.10.0'}), \
                 patch.object(collection, 'WEBVIEW_DLLS', {}), \
                 patch.object(collection.sys, 'version_info', (3, 11, 9)), \
                 patch.object(collection.util, 'find_spec', return_value=fake_spec), \
                 patch.object(collection, 'sha', side_effect=fake_sha):
                collection.collect(root / 'output', report)
                records = json.loads((root / 'output/paketversionen.json').read_text())
                self.assertEqual(records[0]['name'], 'pypdf')
                self.assertTrue(records[0]['license_files'])
                self.assertEqual(json.loads((root / 'output/paket-downloads.json').read_text())[0]['sha256'], 'synthetic-hash')
                with patch.object(collection, 'PACKAGES', {'pypdf': '0.0.0'}):
                    with self.assertRaisesRegex(RuntimeError, 'Unexpected version'):
                        collection.collect(root / 'other', report)


if __name__ == '__main__':
    unittest.main()
