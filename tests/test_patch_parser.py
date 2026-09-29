#!/usr/bin/env python3
"""Small smali fixtures for the invoke-result adjacency guard."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dex_patch', ROOT / 'standalone-patcher/dex_patch.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


class EnabledLanguagesSiteTest(unittest.TestCase):
    prefix = [
        '.method static d()V',
        '    const-string v7, "{ENABLED_LANGUAGES}"',
        '    invoke-virtual {v0, v7, v8}, Ljava/lang/String;->replace(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Ljava/lang/String;',
    ]

    def locate(self, middle):
        lines = self.prefix + middle + ['    move-result-object v0', '    return-void', '.end method']
        return patcher.find_enabled_languages_site(lines, 0, len(lines)-1, '{ENABLED_LANGUAGES}')

    def test_three_stock_debug_directives(self):
        self.assertEqual(('v8', 'v0', 6), self.locate(['    .line 274', '    .line 275', '    .line 276']))

    def test_non_executable_directives(self):
        self.assertEqual(('v8', 'v0', 8), self.locate(['', '    # note', '    .local v8, "langs":Ljava/lang/String;', '    .end local v8', '    .line 276']))

    def test_executable_intervening_opcode_aborts(self):
        with self.assertRaisesRegex(patcher.PatchError, 'no move-result-object'):
            self.locate(['    .line 274', '    const/4 v9, 0x0', '    .line 275'])

    def test_wrong_result_opcode_aborts(self):
        with self.assertRaisesRegex(patcher.PatchError, 'no move-result-object'):
            self.locate(['    move-result v0'])


if __name__ == '__main__':
    unittest.main()

class StockEarlyRuleTest(unittest.TestCase):
    """Synthetic stock order, including its two-arm language join."""
    def setUp(self):
        self.profile = type('ProfileStub', (), {
            'method': lambda self, key: ('Lkfd;', 'd', '()V'),
            'anchors': {'enabled_languages_placeholder': '{ENABLED_LANGUAGES}'},
            'fingerprints': {'hinglish_override_rule': {'sha256': patcher.sha256_text('Stock rule')}},
            'ext_class': patcher.EXT_DEFAULT,
        })()
        self.lines = [
            '.method public static d()V', '    .locals 15',
            '    if-eqz v9, :cond_alt',
            '    move-object v8, v7',
            '    goto :goto_a6',
            '    :cond_alt',
            '    invoke-static {v10, v8}, Lqpx;->a(Ljava/lang/CharSequence;Ljava/lang/Iterable;)Ljava/lang/String;',
            '    move-result-object v8',
            '    :goto_a6',
            '    const-string v12, "{HINGLISH_OVERRIDE_RULE}"',
            '    const-string v14, "Stock rule"',
            '    invoke-virtual {v7, v12, v14}, Ljava/lang/String;->replace(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Ljava/lang/String;',
            '    move-result-object v7',
            '    const-string v7, "{ENABLED_LANGUAGES}"',
            '    invoke-virtual {v0, v7, v8}, Ljava/lang/String;->replace(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Ljava/lang/String;',
            '    .line 274', '    .line 275', '    .line 276',
            '    move-result-object v0',
            '    invoke-virtual {v2, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;',
            '    invoke-virtual {p0, v0}, Lhpb;->b(Ljava/lang/Object;)Lauha;',
            '    move-object v4, p0',
            '    iget-object p0, p0, Laazs;->c:Lauhe;',
            '    invoke-static {v9, v0, p0}, Laugj;->t(Lauha;Laugd;Ljava/util/concurrent/Executor;)V',
            '    return-void', '.end method',
        ]

    def test_stock_early_rule_positive(self):
        original = list(self.lines)
        result = patcher.patch_method(self.lines, self.profile, True)
        text = '\n'.join(result)
        self.assertIn('selectHinglishOverrideRule', text)
        self.assertIn('rewriteCleanupPromptScriptGate', text)
        self.assertLess(text.index('selectHinglishOverrideRule'), text.index('rewriteCleanupPromptScriptGate'))
        self.assertEqual('    .locals 18', result[1])
        # Account for the exact ten hook instructions; everything else must
        # match the original except register metadata and five repairs.
        stripped = list(result)
        for hook in ('selectHinglishOverrideRule', 'rewriteCleanupPromptScriptGate'):
            at = next(i for i, line in enumerate(stripped) if hook in line)
            del stripped[at-2:at+3]
        expected = list(original)
        expected[1] = '    .locals 18'
        repairs = {
            original[19]: ['    move-object/from16 v15, p0', original[19].replace('p0}', 'v15}')],
            original[20]: ['    move-object/from16 v15, p0', original[20].replace('{p0,', '{v15,')],
            original[21]: ['    move-object/from16 v4, p0'],
            original[22]: ['    move-object/from16 v15, p0',
                           '    iget-object v15, v15, Laazs;->c:Lauhe;',
                           '    move-object/from16 p0, v15'],
            original[23]: ['    move-object/from16 v15, p0', original[23].replace('p0}', 'v15}')],
        }
        expanded = []
        for line in expected:
            expanded.extend(repairs.get(line, [line]))
        self.assertEqual(expanded, stripped)
        # Drop injected instructions and compare untouched smali verbatim;
        # only register-window metadata and the five exact p0 sites differ.
        self.assertEqual(5, sum(1 for line in original if line.strip() in {
            'invoke-virtual {v2, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;',
            'invoke-virtual {p0, v0}, Lhpb;->b(Ljava/lang/Object;)Lauha;',
            'move-object v4, p0', 'iget-object p0, p0, Laazs;->c:Lauhe;',
            'invoke-static {v9, v0, p0}, Laugj;->t(Lauha;Laugd;Ljava/util/concurrent/Executor;)V',
        }))
        for expected in ('move-object/from16 v4, p0',
                         'invoke-virtual {v2, v15}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;',
                         'invoke-virtual {v15, v0}, Lhpb;->b(Ljava/lang/Object;)Lauha;',
                         'iget-object v15, v15, Laazs;->c:Lauhe;',
                         'invoke-static {v9, v0, v15}, Laugj;->t(Lauha;Laugd;Ljava/util/concurrent/Executor;)V'):
            self.assertIn(expected, text)

    def test_language_register_clobbered(self):
        self.lines.insert(13, '    const-string v8, "oops"')
        with self.assertRaisesRegex(patcher.PatchError, 'join/lifetime'):
            patcher.patch_method(self.lines, self.profile, True)

    def test_rule_not_consumed(self):
        self.lines[11] = '    invoke-virtual {v7, v12, v13}, Ljava/lang/String;->replace(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Ljava/lang/String;'
        with self.assertRaisesRegex(patcher.PatchError, 'not consumed'):
            patcher.patch_method(self.lines, self.profile, True)

    def test_unexpected_stock_instruction_aborts(self):
        self.lines[19] = '    invoke-virtual {v3, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;'
        with self.assertRaisesRegex(patcher.PatchError, 'five exact instructions'):
            patcher.patch_method(self.lines, self.profile, True)


if __name__ == '__main__':
    unittest.main()
