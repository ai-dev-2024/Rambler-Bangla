#!/usr/bin/env python3
"""Fail-closed Lkut.F staging hook tests, not a device verdict."""
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host-skeleton'))
from patch_clip_recents import patch, EXPECTED_DEX_SHA

BASE = Path('/tmp/rambler-host-skeleton-unsigned.apk')
OUT = Path('/tmp/rambler-host-picker-recents-unsigned.apk')

class RecentsHookTest(unittest.TestCase):
    def test_fail_closed_text_mutations(self):
        text = '''.class public final Lkut;\n.method public final F()V\n    .registers 6
    iget-object v2, p0, Lkut;->o:Ljava/util/List;
    const/4 v4, 0x5
    invoke-interface {v2, v1}, Ljava/util/List;->remove(I)Ljava/lang/Object;
    invoke-virtual {p0, v1}, Lpt;->n(I)V
.end method'''
        once = patch(text)
        self.assertEqual(once.count('GboardRamblerClipRecents;->read'), 1)
        with self.assertRaisesRegex(ValueError, 'existing hook'):
            patch(once)
        for bad in (text.replace('const/4 v4, 0x5','const/4 v4, 0x6'),
                    text.replace('const/4 v4, 0x5','const/4 v4, 0x5\n    const/4 v4, 0x5'),
                    text.replace('Lpt;->n(I)V','Lpt;->q(I)V'),
                    text.replace('.registers 6','.registers 7')):
            with self.assertRaises(ValueError):
                patch(bad)

    def test_input_hash_and_output_reentry_fail_closed(self):
        import subprocess
        import tempfile
        if not BASE.is_file():
            self.skipTest('local staging input absent')
        with tempfile.TemporaryDirectory() as temp:
            for source in (BASE, OUT if OUT.is_file() else BASE):
                destination = Path(temp) / 'probe-unsigned.apk'
                if source == BASE:
                    destination.write_bytes(b'occupied')
                process = subprocess.run([sys.executable, str(ROOT / 'host-skeleton/patch_clip_recents.py'),
                    '--in-apk', str(source), '--out-apk', str(destination), '--work', str(Path(temp) / 'work')],
                    capture_output=True, text=True)
                self.assertNotEqual(process.returncode, 0)
                if source == BASE:
                    self.assertIn('refusing to overwrite', process.stderr)
                    destination.unlink()
                else:
                    self.assertIn('input APK SHA drift', process.stderr)
                    self.assertFalse(destination.exists())

    @unittest.skipUnless(BASE.is_file() and OUT.is_file(), 'local staging scratch absent')
    def test_only_expected_dex_and_method_change(self):
        try:
            from androguard.core.dex import DEX
            from loguru import logger
            logger.remove()
        except ImportError:
            self.skipTest('Androguard unavailable')
        import hashlib
        with ZipFile(BASE) as old, ZipFile(OUT) as new:
            self.assertIsNone(new.testzip())
            self.assertEqual(set(old.namelist()), set(new.namelist()))
            self.assertEqual([n for n in old.namelist() if old.read(n) != new.read(n)], ['classes2.dex'])
            self.assertEqual(hashlib.sha256(old.read('classes2.dex')).hexdigest(), EXPECTED_DEX_SHA)
            a, b = DEX(old.read('classes2.dex')), DEX(new.read('classes2.dex'))
            self.assertEqual({c.get_name() for c in a.get_classes()},
                             {c.get_name() for c in b.get_classes()})
            oldcls, newcls = a.get_class('Lkut;'), b.get_class('Lkut;')
            def operations(cls):
                return {(m.get_name(),m.get_descriptor()):
                        [(i.get_name(),i.get_output()) for i in m.get_instructions()]
                        for m in cls.get_methods()}
            oldm,newm=operations(oldcls),operations(newcls)
            self.assertEqual(oldm.keys(),newm.keys())
            altered=[k for k in oldm if oldm[k] != newm[k]]
            self.assertEqual(altered,[('F','()V')])
            self.assertEqual((len(oldm[altered[0]]),len(newm[altered[0]])),(40,42))
            self.assertEqual(newm[altered[0]][19:22],[
                ('iget-object','v4, v5, Lkut;->e Landroid/content/Context;'),
                ('invoke-static','v4, Lcom/akshaykadam/pixelboard/extension/rambler/GboardRamblerClipRecents;->read(Landroid/content/Context;)I'),
                ('move-result','v4')])
            # The whole DEX is reassembled; all other class code should be
            # semantically the same, not merely have unchanged class names.
            changed=[]
            for oc in a.get_classes():
                if oc.get_name()=='Lkut;':continue
                nc=b.get_class(oc.get_name())
                if operations(oc)!=operations(nc):changed.append(oc.get_name())
            self.assertEqual(changed,[])

if __name__=='__main__':unittest.main()
