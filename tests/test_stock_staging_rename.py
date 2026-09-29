#!/usr/bin/env python3
"""Exact-input staging rename acceptance test; requires local stock artifact."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'rename'))
from rename_apk import rename_stock_staging, rewrite_stock_manifest  # noqa: E402


class StagingRenameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ.get('RAMBLER_STOCK_ASSEMBLED',
                                         '/tmp/rambler-stock-assembled-unsigned.apk'))
        if not cls.source.is_file():
            raise unittest.SkipTest('exact stock assembled APK unavailable')
        cls.hash = hashlib.sha256(cls.source.read_bytes()).hexdigest()

    def test_identity_and_scoped_diff(self):
        from loguru import logger
        logger.remove()
        from androguard.core.apk import APK
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'staging.apk'
            rename_stock_staging(str(self.source), str(dest),
                                 str(Path(temp) / 'work'),
                                 str(Path(temp) / 'report.json'),
                                 'com.aidev2024.ramblerbangla.staging',
                                 'Rambler Staging', 176004245,
                                 '18.3.1.977415014-beta-arm64-r33-staging',
                                 self.hash)
            a = APK(str(dest))
            self.assertTrue(a.is_valid_APK())
            self.assertEqual(a.get_package(), 'com.aidev2024.ramblerbangla.staging')
            self.assertEqual(a.get_androidversion_code(), '176004245')
            self.assertEqual(a.get_androidversion_name(),
                             '18.3.1.977415014-beta-arm64-r33-staging')
            self.assertEqual(a.get_app_name(), 'Rambler Staging')
            with zipfile.ZipFile(self.source) as before, zipfile.ZipFile(dest) as after:
                self.assertIsNone(after.testzip())
                self.assertEqual(set(before.namelist()), set(after.namelist()))
                changed = {x for x in before.namelist()
                           if before.read(x) != after.read(x)}
                self.assertEqual(changed,
                                 {'AndroidManifest.xml', 'resources.arsc', 'classes.dex'})
                for dex in ('classes2.dex', 'classes3.dex', 'classes4.dex', 'classes5.dex'):
                    self.assertEqual(before.read(dex), after.read(dex))
                self.assertIn(b'com.aidev2024.ramblerbangla.staging',
                              after.read('classes.dex'))

    def test_wrong_input_hash_aborts(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                rename_stock_staging(str(self.source), str(Path(temp) / 'bad.apk'),
                                     temp, str(Path(temp) / 'report.json'),
                                     'com.aidev2024.ramblerbangla.staging',
                                     'Rambler Staging', 176004245,
                                     '18.3.1.977415014-beta-arm64-r33-staging',
                                     '0' * 64)
            self.assertFalse((Path(temp) / 'bad.apk').exists())

    def test_missing_manifest_anchor_aborts(self):
        with zipfile.ZipFile(self.source) as source:
            data = source.read('AndroidManifest.xml')
        with self.assertRaisesRegex(ValueError, 'anchor|refs'):
            rewrite_stock_manifest(data, 'com.google.android.inputmethod.latin.missing',
                                   'com.aidev2024.ramblerbangla.staging',
                                   'Rambler Staging', 176004245,
                                   '18.3.1.977415014-beta-arm64-r33-staging')


if __name__ == '__main__':
    unittest.main()
