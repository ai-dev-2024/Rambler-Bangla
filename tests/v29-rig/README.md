# V29 JVM rig (test-only)

`bash tests/v29-rig/run.sh` from the repo root. Needs a JDK 17+ and python3; no Android toolchain.

What it does: compiles main's V29 sources (`extension-src/.../rambler/GboardRamblerLoanSpell.java`,
`GboardRamblerSentenceLang.java`) plus `GboardRamblerLoanTable.java` generated on a scratch copy by
`data/loanspell/gen_java.py`, against test-only stubs of the classes that exist only in the shipped dex
(`GboardRamblerScriptFix`, `GboardRamblerSegmentLock`, `GboardRamblerTier1`, `GboardRamblerDiag`), then runs
every `src/**/V29*Test.java` class and prints one `V29 RIG: N passed, M failed (X xfail)` total. It also fails if the OVERRIDE block in LoanSpell no longer matches `overrides.tsv`.

The stubs answer only from `fixtures/shipped-outputs.tsv`: each row is a recorded output of a shipped class with its
source (a doc or a golden file). An unknown word gets null from the stubbed converter. The stand-in English
dictionary is the loan table's keys plus the override keys (the shipped 20,010-word set is not in main), and the
shipped PROTECT_BN / BANGLA_FUNC / GARBLE lists start empty (`list:` rows add words). So the rig proves main's own
logic, not the shipped converter; a result that depends on a stubbed class is only as good as its fixture row.

Tests may add a recorded row for one run with `RigFixtures.put(fn, key, output)`.
`RIG_TRACE='sentence one|sentence two' bash tests/v29-rig/run.sh` also prints SentenceLang decision traces.

`fixtures/native-targets.tsv` holds native-word (non-loanword) spelling targets checked by `V29NativeTest` on the voice
token path. Status `open` and `needs-source` rows are expected failures (xfail); if one starts passing the rig fails
with XPASS so the row gets promoted to `main`. `needs-source` means the defect lives in Tier1/ScriptFix, which main
does not carry.
