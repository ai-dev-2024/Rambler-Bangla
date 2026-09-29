#!/usr/bin/env python3
"""Pinned drag closure must be all-or-nothing for later source recovery."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host-skeleton'))
from clip_drag_inventory import inventory,EXPECTED_CLOSURE,V32

class DragDependencyInventory(unittest.TestCase):
    @unittest.skipUnless(V32.is_file(),'pinned v32 missing')
    def test_exact_closure(self):
        try:
            from androguard.core.dex import DEX  # noqa: F401
        except ImportError:
            self.skipTest('Androguard unavailable')
        result=inventory()
        self.assertEqual(set(result['classes']),EXPECTED_CLOSURE)
        self.assertEqual(result['class_count'],6)
        self.assertEqual(result['extension_dex_sha256'],
                         'b09d51e63daafb3de5952cb2ec2ebecf3e39dcc07ed416be4a98f8afe3df722d')
        self.assertEqual(result['status'],'DEPENDENCY_MAP_ONLY_NO_BUILD')

    def test_wrong_bytes_fail_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            altered=Path(directory)/'not-v32.apk'
            altered.write_bytes(b'not v32')
            with self.assertRaisesRegex(ValueError,'drift'):
                inventory(altered)

if __name__=='__main__':unittest.main()
