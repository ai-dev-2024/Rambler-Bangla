#!/usr/bin/env python3
"""Pinned stock/v32 clipboard adapter seam. Structural only, not retention or device proof."""
import hashlib
import unittest
from pathlib import Path
from zipfile import ZipFile

STOCK = Path('/tmp/rambler-bases/gboard-beta-arm64.apk')
V32 = Path('/downloads/rambler-bangla-v32.apk')
STOCK_SHA = '2672a08a0292a307b9f62cd0fa6f48f3bc2334a2f2d9daff7db9d54fc4a2a7e3'
V32_SHA = 'ce0d7e6710711f972e24ece2e838a3f51aff5184aeaeb78590dc1b14f182bd64'
READ = 'GboardRamblerClipRecents;->read(Landroid/content/Context;)I'


def instructions(dex, descriptor, name, signature):
    cls = dex.get_class(descriptor)
    assert cls is not None, descriptor
    found = [m for m in cls.get_methods() if m.get_name() == name and
             m.get_descriptor().replace(' ', '') == signature]
    assert len(found) == 1, (descriptor, name, signature, len(found))
    return [(i.get_name(), i.get_output()) for i in found[0].get_instructions()]


class PinnedClipboardRecents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STOCK.is_file() or not V32.is_file():
            raise unittest.SkipTest('pinned APK missing: no DEX verdict')
        try:
            from androguard.core.dex import DEX
            from loguru import logger
            logger.remove()
        except ImportError as exc:
            raise unittest.SkipTest('Androguard unavailable: no DEX verdict ' + str(exc))
        for path, expected in ((STOCK, STOCK_SHA), (V32, V32_SHA)):
            h = hashlib.sha256()
            with path.open('rb') as f:
                for block in iter(lambda: f.read(1048576), b''):
                    h.update(block)
            assert h.hexdigest() == expected, 'pinned bytes drift: ' + str(path)
        with ZipFile(STOCK) as s, ZipFile(V32) as v:
            cls.stock = DEX(s.read('classes2.dex'))
            cls.v32 = DEX(v.read('classes3.dex'))
            cls.v32_extension = DEX(v.read('classes.dex'))

    def test_recents_setting_only_replaces_adapter_section_limit(self):
        a = instructions(self.stock, 'Lkut;', 'F', '()V')
        b = instructions(self.v32, 'Lkut;', 'F', '()V')
        self.assertEqual((len(a), len(b)), (40, 42))
        self.assertFalse(any(READ in output for _, output in a))
        self.assertEqual(a[19], ('const/4', 'v4, 5'))
        self.assertEqual(b[19:22], [
            ('iget-object', 'v4, v5, Lkut;->e Landroid/content/Context;'),
            ('invoke-static', 'v4, Lcom/akshaykadam/pixelboard/extension/rambler/'+READ),
            ('move-result', 'v4')])
        # Branch offsets shift with the inserted instructions; compare the
        # remaining operation and operand stream, masking only jump targets.
        def normalized(items):
            return [(op, 'branch-target' if op.startswith('goto') else
                     output.split(', +')[0] if op.startswith('if-') else output)
                    for op, output in items]
        self.assertEqual(normalized(a[:19] + a[20:]),
                         normalized(b[:19] + b[22:]))
        # This method trims Lkut.o and notifies its adapter; it does not prove
        # persistent clipboard storage retention, pin capacity, or on-device UI.
        self.assertIn(('invoke-interface', 'v2, v1, Ljava/util/List;->remove(I)Ljava/lang/Object;'), b)
        self.assertIn(('invoke-virtual', 'v5, v1, Lpt;->n(I)V'), b)


    def test_preference_default_bounds_and_key_match_shipped_v32(self):
        cls = 'Lcom/akshaykadam/pixelboard/extension/rambler/GboardRamblerClipRecents;'
        dex = self.v32_extension
        clamp = instructions(dex, cls, 'clamp', '(I)I')
        self.assertEqual(clamp[0], ('const/16', 'v0, 10'))
        self.assertEqual(clamp[3], ('const/4', 'v0, 5'))
        self.assertTrue(any('Ljava/lang/Math;->min(I I)I' in arg for _, arg in clamp))
        self.assertTrue(any('Ljava/lang/Math;->max(I I)I' in arg for _, arg in clamp))
        read = instructions(dex, cls, 'read', '(Landroid/content/Context;)I')
        write = instructions(dex, cls, 'write', '(Landroid/content/Context;I)V')
        self.assertEqual(read[0], ('const/4', 'v0, 5'))
        for method in (read, write):
            self.assertIn(('const-string', 'v1, "pref_clipboard_recents_limit"') if method is read
                          else ('const-string', 'v0, "pref_clipboard_recents_limit"'), method)
            self.assertTrue(any('GboardPatchesSettings;->preferences(Landroid/content/Context;)' in arg
                                for _, arg in method))
        preferences = instructions(dex,
            'Lcom/akshaykadam/pixelboard/extension/settings/GboardPatchesSettings;',
            'preferences', '(Landroid/content/Context;)Landroid/content/SharedPreferences;')
        self.assertIn(('const-string', 'v0, "gboard_patches_settings"'), preferences)
        # Pure value-level match: the staging source mirrors these keys and
        # bounds, but has no installed host adapter or end-to-end UI.


if __name__ == '__main__':
    unittest.main()
