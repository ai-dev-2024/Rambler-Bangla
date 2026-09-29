#!/usr/bin/env python3
"""Pin v32 C-1 voice-only layout seam, not a runtime or patch verdict."""
import hashlib
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile

V32 = Path('/downloads/rambler-bangla-v32.apk')
V32_SHA = 'ce0d7e6710711f972e24ece2e838a3f51aff5184aeaeb78590dc1b14f182bd64'
PREFIX = 'Lcom/akshaykadam/pixelboard/extension/rambler/'


def instructions(dex, cls, name, signature):
    c = dex.get_class(cls)
    if c is None:
        raise AssertionError(f'missing class {cls}')
    matches = [m for m in c.get_methods() if m.get_name() == name
               and m.get_descriptor().replace(' ', '') == signature]
    if len(matches) != 1:
        raise AssertionError(f'{cls}->{name}{signature}: {len(matches)} matches')
    return [(x.get_name(), x.get_output()) for x in matches[0].get_instructions()]


class LayoutPairVoiceSeam(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not V32.is_file():
            raise unittest.SkipTest('v32 input absent: no C-1 DEX verdict')
        try:
            from androguard.core.dex import DEX
            from loguru import logger
            logger.remove()
        except ImportError as exc:
            raise unittest.SkipTest(f'DEX decoder unavailable: {exc}')
        if hashlib.sha256(V32.read_bytes()).hexdigest() != V32_SHA:
            raise AssertionError('v32 APK hash drift')
        with ZipFile(V32) as apk:
            cls.dex = DEX(apk.read('classes.dex'))

    def test_adjust_is_called_in_voice_layout_classifier_only(self):
        pair = PREFIX + 'GboardRamblerLayoutPair;'
        fix = PREFIX + 'GboardRamblerScriptFix;'
        current = instructions(self.dex, fix, 'currentLayout3', '()I')
        self.assertEqual(sum(pair + '->adjust(I Ljava/lang/String; Ljava/lang/String;)I' in arg
                             for _, arg in current), 1)
        adjustment = instructions(self.dex, pair, 'adjust', '(ILjava/lang/String;Ljava/lang/String;)I')
        self.assertEqual(len(adjustment), 18)
        for name in ('isEnglish', 'toggleOn', 'bnLatnEnabled'):
            self.assertEqual(sum('->' + name + '(' in arg for op, arg in adjustment
                                 if op.startswith('invoke-')), 1)
        self.assertEqual(adjustment[13:15], [('const/4', 'v1, 2'), ('return', 'v1')])

    def test_enabled_subtype_is_not_active_subtype(self):
        pair = PREFIX + 'GboardRamblerLayoutPair;'
        enabled = instructions(self.dex, pair, 'bnLatnEnabled', '(Ljava/lang/String;)Z')
        self.assertEqual(sum('->getEnabledInputMethodList()Ljava/util/List;' in arg
                             for _, arg in enabled), 1)
        self.assertEqual(sum('->getEnabledInputMethodSubtypeList(' in arg
                             for _, arg in enabled), 2)
        self.assertEqual(sum('->getCurrentInputMethodSubtype()' in arg
                             for _, arg in enabled), 0)
        self.assertEqual(sum(pair + '->isBnLatn(Ljava/lang/String; Ljava/lang/String;)Z' in arg
                             for _, arg in enabled), 1)
        english = instructions(self.dex, pair, 'isEnglish', '(Ljava/lang/String;Ljava/lang/String;)Z')
        self.assertEqual(sum('->startsWith(Ljava/lang/String;)Z' in arg for _, arg in english), 2)
        self.assertEqual(sum(arg == 'v0, "en"' for op, arg in english if op == 'const-string'), 1)
        # Static helper cannot distinguish English(US) from EN-BN when both surface en_US.
        # This is a negative gate, not permission to promote the layout automatically.


if __name__ == '__main__':
    unittest.main()
