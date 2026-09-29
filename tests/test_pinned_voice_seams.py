#!/usr/bin/env python3
"""Read-only DEX guard for the *pinned* stock/v32 voice seams.

This does not prove runtime eligibility, conversion, or editor commitment.
Run directly or via unittest discovery. If the two pinned APKs are absent,
the test is SKIPPED rather than inventing a passing result.
"""
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


STOCK = Path('/tmp/rambler-bases/gboard-beta-arm64.apk')
V32 = Path('/downloads/rambler-bangla-v32.apk')
STOCK_SHA = '2672a08a0292a307b9f62cd0fa6f48f3bc2334a2f2d9daff7db9d54fc4a2a7e3'
V32_SHA = 'ce0d7e6710711f972e24ece2e838a3f51aff5184aeaeb78590dc1b14f182bd64'
EXT = 'Lcom/akshaykadam/pixelboard/extension/rambler/GboardRamblerScriptFix;'


def method(dex, descriptor, name, params):
    cls = dex.get_class(descriptor)
    if cls is None:
        raise AssertionError('missing class ' + descriptor)
    methods = [m for m in cls.get_methods()
               if m.get_name() == name and m.get_descriptor().replace(' ', '') == params]
    if len(methods) != 1:
        raise AssertionError(f'{descriptor}->{name}{params}: {len(methods)} matches')
    return [(i.get_name(), i.get_output()) for i in methods[0].get_instructions()]


def invoke_indices(instructions, suffix):
    return [i for i, (op, arg) in enumerate(instructions)
            if op.startswith('invoke-') and suffix in arg]


class PinnedVoiceSeams(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STOCK.is_file() or not V32.is_file():
            raise unittest.SkipTest('pinned stock/v32 APK input absent: NO DEX VERDICT')
        # Import only after presence check so a missing optional decoder also
        # remains a visible skip in portable CI; hash mismatch is never a skip.
        try:
            from androguard.core.dex import DEX
            from loguru import logger
            logger.remove()
        except ImportError as exc:
            raise unittest.SkipTest(f'androguard unavailable: NO DEX VERDICT ({exc})')
        from host_skeleton_inventory import sha
        if sha(STOCK) != STOCK_SHA or sha(V32) != V32_SHA:
            raise AssertionError('pinned voice input SHA-256 mismatch')
        with ZipFile(STOCK) as a, ZipFile(V32) as b:
            cls.stock = DEX(a.read('classes2.dex'))
            cls.v32 = DEX(b.read('classes3.dex'))
            cls.v32_extension = DEX(b.read('classes.dex'))

    def test_candidate_write_precedes_same_object_dispatch(self):
        signature = '(Lazdg;)V'
        a = method(self.stock, 'Lvrh;', 'h', signature)
        b = method(self.v32, 'Lvrh;', 'h', signature)
        self.assertEqual((len(a), len(b)), (49, 69))
        hook = invoke_indices(b, EXT + '->processVoice(Ljava/lang/String;)Ljava/lang/String;')
        self.assertEqual(len(hook), 1)
        self.assertFalse(invoke_indices(a, 'processVoice('))
        candidate_write = [i for i, (op, arg) in enumerate(b)
                           if op == 'iput-object' and 'Lazdo;->c Ljava/lang/String;' in arg]
        dispatch = invoke_indices(b, 'Lauhe;->execute(Ljava/lang/Runnable;)V')
        self.assertEqual(len(candidate_write), 1)
        self.assertEqual(len(dispatch), 1)
        self.assertLess(hook[0], candidate_write[0])
        self.assertLess(candidate_write[0], dispatch[0])
        self.assertEqual(len(invoke_indices(a, 'Lauhe;->execute(Ljava/lang/Runnable;)V')), 1)
        self.assertEqual(len([1 for op, arg in b if op == 'iget-boolean' and
                              'Lazdo;->d Z' in arg]), 1)
        # Stock downstream owner still schedules the very same Lazdg object;
        # neither fact proves the editor's committed text.
        for dex in (self.stock, self.v32):
            runner = method(dex, 'Lvul;', 'run', '()V')
            self.assertEqual(len(invoke_indices(runner, 'Lajrf;->dQ(Lazdg;)V')), 1)

    def test_request_locale_fallback_only_when_holder_absent(self):
        signature = '(Landroid/content/Context;Lqsh;ILqrw;Lasfj;)Lazgc;'
        a = method(self.stock, 'Lqrx;', 'a', signature)
        b = method(self.v32, 'Lqrx;', 'a', signature)
        self.assertEqual((len(a), len(b)), (277, 275))
        self.assertEqual(len(invoke_indices(a, 'Ljava/util/Locale;->getDefault()Ljava/util/Locale;')), 1)
        self.assertEqual(len(invoke_indices(b, EXT + '->voiceLanguageTagFallback()Ljava/lang/String;')), 1)
        self.assertFalse(invoke_indices(a, EXT))
        self.assertEqual(len([1 for op, arg in a if op == 'iget-object' and
                              'Lqsh;->f Lajpe;' in arg]), 1)
        self.assertEqual(len([1 for op, arg in b if op == 'iget-object' and
                              'Lqsh;->f Lajpe;' in arg]), 1)
        self.assertFalse(invoke_indices(b, 'admitExactBengaliLocales'))
        # These are separate instruction streams: one added fallback cannot
        # establish any runtime supported-locale admission behavior.
        self.assertEqual(len(invoke_indices(a, 'Ljava/util/Locale;->toLanguageTag()Ljava/lang/String;')), 1)

    def test_v32_voice_mixed_script_short_circuit_is_before_conversion(self):
        # This pins a known regression risk in shipped v32 bytes, not a fix.
        ext = self.v32_extension
        entry = method(ext, EXT, 'processVoice', '(Ljava/lang/String;)Ljava/lang/String;')
        enter = invoke_indices(entry, 'GboardRamblerLoanSpell;->enterVoice()V')
        process = invoke_indices(entry, EXT + '->process(Ljava/lang/String; Ljava/util/Locale; Z)Ljava/lang/String;')
        exit_text = invoke_indices(entry, 'GboardRamblerLoanSpell;->exitText(Ljava/lang/String; Ljava/lang/String;)Ljava/lang/String;')
        self.assertEqual((len(enter), len(process), len(exit_text)), (1, 1, 1))
        self.assertLess(enter[0], process[0])
        self.assertLess(process[0], exit_text[0])
        ins = method(ext, EXT, 'processInternal', '(Ljava/lang/String;Ljava/util/Locale;Z)Ljava/lang/String;')
        gate = invoke_indices(ins, EXT + '->gateOpen(Ljava/util/Locale;)Z')
        check = invoke_indices(ins, EXT + '->containsBengali(Ljava/lang/String;)Z')
        dictionary = invoke_indices(ins, EXT + '->ensureDictionary()I')
        join = invoke_indices(ins, EXT + '->joinSplitPhrases(Ljava/lang/String;)Ljava/lang/String;')
        segment = invoke_indices(ins, 'GboardRamblerSegmentLock;->process(Ljava/lang/String;)Ljava/lang/String;')
        self.assertEqual((len(gate), len(check), len(dictionary), len(join), len(segment)),
                         (1, 1, 1, 1, 1))
        self.assertLess(gate[0], check[0])
        self.assertLess(check[0], dictionary[0])
        self.assertLess(dictionary[0], join[0])
        self.assertLess(join[0], segment[0])
        self.assertEqual([op for op, _ in ins[check[0]+1:check[0]+6]],
                         ['move-result', 'if-eqz', 'const-string', 'invoke-static', 'return-object'])
        self.assertEqual(ins[check[0]+3], ('const-string', 'v0, "skip:has-bengali"'))
        self.assertEqual(ins[check[0]+5], ('return-object', 'v1'))
        bengali = method(ext, EXT, 'containsBengali', '(Ljava/lang/String;)Z')
        self.assertIn(('const/16', 'v3, 2432'), bengali)
        self.assertIn(('const/16', 'v3, 2559'), bengali)
        # The early return is ahead of conversion for both typing and voice.
        # Runtime behavior, backend choice and committed editor text are not shown.

    def test_old_1803_locale_targets_do_not_exist(self):
        for dex in (self.stock, self.v32):
            self.assertEqual(len(method(dex, 'Lsdc;', '<init>', '(Lbcsx;)V')), 3)
            self.assertEqual(len(method(dex, 'Lrwr;', 'apply', '(Ljava/lang/Object;)Ljava/lang/Object;')), 13)
            self.assertFalse([m for m in dex.get_class('Lsdc;').get_methods()
                              if m.get_name() == '<init>' and 'Ljava/util/Set;' in m.get_descriptor()])
            self.assertFalse([m for m in dex.get_class('Lrwr;').get_methods()
                              if m.get_name() == '<init>'])


if __name__ == '__main__':
    unittest.main()
