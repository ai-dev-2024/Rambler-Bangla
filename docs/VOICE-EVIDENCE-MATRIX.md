# Voice seam capture matrix for the exact 18.3.1 stock base

This is a capture plan, not a passing test report. Pin the APK bytes and test
setup in each run. The stock baseline is SHA-256
`2672a08a0292a307b9f62cd0fa6f48f3bc2334a2f2d9daff7db9d54fc4a2a7e3`;
the signed v32 reference is
`ce0d7e6710711f972e24ece2e838a3f51aff5184aeaeb78590dc1b14f182bd64`.
The staging r34 shell is neither v32 nor a voice fix. Alpha's reported
compat10 fingerprint failure is not a built candidate. Put any new candidate's
SHA, package, version and certificate in the run manifest, rather than calling
it v32. Emulator results are *EMULATOR*, never physical-device T1 PASS.

## Instrumentation boundaries

Record the Android API/ABI and image, IME package/version/cert, keyboard
Languages screen, active subtype tag, selected voice engine and AdvancedVoice
mode, mic UI, test editor before/after, and exact WAV file SHA + utterance ID.
Keep stock, v32, and candidate on otherwise matched language/backend/account
state; do not silently compare different backends. Do not record private
speech, account IDs, network tokens or full editor contents in shared logs.
Use innocuous fixed clips. For a release test, the owner's device evidence is a
separate, source-pinned run, not an extrapolation from this emulator plan.

Capture time-aligned markers at these boundaries, each with source and
observation status:

1. Recognition request: effective subtype, `Lqsh.f` holder present/absent,
   request locale, engine/model/eligibility decision. The v32 `Lqrx.a` fallback
   reads `InputMethodManager.getCurrentInputMethodSubtype()` only when the
   holder is null; stock uses the default locale. Do not mistake this header
   path for proof that Bengali was admitted to an engine.
2. A *real 18.3.1* supported-locale list or eligibility decision: owner
   method descriptor and DEX SHA, input/output locale Set, branch reason and
   timing. The upstream 18.0.3 `Lsdc`/`Lrwr` descriptors do not match this
   base. If this boundary cannot be found, mark `UNOBSERVED`, not "no gate".
3. Raw ASR result, `Lazdg.b` final `Lazdo.c` candidates before/after
   `Lvrh.h`, and any other candidate consumers. Record script histograms and
   a consent-safe fixture excerpt only, with candidate final flag and
   sequence number. `Lvrh.h` transforms final nonempty `Lazdo.c` in v32;
   this alone does not prove what the editor receives.
4. Last text submitted via InputConnection (composing and commit calls),
   resulting editor Unicode script histogram, and screenshot. Check the
   relationship to candidate IDs; a candidate screenshot alone is not a
   committed-text verdict. Note restarts/crashes/permission failures.

Every cell has one verdict: `PASS`, `FAIL`, `UNOBSERVED`, `BLOCKED`, or
`NOT_APPLICABLE`, with a log/screenshot reference and byte identity. A green
CI job is infrastructure evidence only. An absent field is `UNOBSERVED`.

## Runs (each on stock and v32, then any pinned candidate)

| ID | Enabled language and selected subtype | Input fixture | Boundary question / expected invariant |
|---|---|---|---|
| L01 | bn-BD alone, bn-BD | Bengali-only | Is the request locale bn-BD and where, if anywhere, is it rejected? Candidate and commit are observed separately. |
| L02 | bn-IN alone, bn-IN | Bengali-only | Same with exact bn-IN, without inferring from bn-BD. |
| L03 | bn-BD + en-US, bn-BD | English-only | English stays Latin at the *commit*, not just the candidate. |
| L04 | bn-BD + en-US, bn-BD | Mixed EN-to-BN sentence | English Latin and Bengali Bengali at the commit; check both directions of transition in a second fixture. |
| L05 | bn-IN + en-US, bn-IN | Mixed EN-to-BN sentence | Region-specific repeat of L04. |
| L06 | bn-BD + en-US, en-US | Bengali-only | Probe primary/subtype precedence without assuming enabled bn means selected bn. |
| L07 | bn-Latn + en-US, bn-Latn | Bengali-language utterance | Explicit Latin control must not be silently changed to Bengali script. |
| L08 | en-US alone, en-US | English-only | No Bengali insertion or backend behavior change. |
| L09 | bn-BD + en-US, bn-BD | Already-Bengali plus Romanized Bangla plus English in one candidate | Detect v32's whole-input `containsBengali` early return; assess mixed-span conversion at candidate and commit. |
| L10 | bn-BD + en-US, bn-BD | Innocuous loanword fixture (`boltechi`/`boltesi`/`bolteshi`) | Record whether candidate and commit converge to intended spelling, without relying on a dictionary-only unit test. |
| L11 | bn-BD + en-US, bn-BD | Silence / no speech | No fabricated text, unrequested commit, or crash. |
| L12 | bn-BD + en-US, bn-BD | Mixed fixture with emoji and non-BMP character | No UTF-16 surrogate split, crash or dropped trailing text; distinguish candidate from commit. |

Run L01-L05 against each selectable Rambler Lite/Base/S backend, and one
standard voice-typing negative control, when those modes exist. Repeat the
Bengali and mixed fixtures offline if the mode supports it, recording the
actual backend rather than assuming offline use. For each run, record observed
raw-ASR script and editor script; do not claim a locale gate caused a spelling
failure merely because the final editor text is Romanized.

## Decision after capture

- If the exact 18.3.1 runtime shows a Bengali eligibility rejection *before*
  ASR, map that owner method and build a fail-closed, exact-byte candidate
  patch. A static fingerprint or 18.0.3 analogy is insufficient.
- If ASR outputs Latin under Bengali request, trace model/backend choice;
  changing the post-ASR candidate hook alone cannot prove the engine fix.
- If ASR/candidates are Bengali but the commit is Latin, trace downstream
  formatter/diff/commit after `Lvrh.h` and patch the proven boundary.
- If candidate conversion works but mixed-script input is returned wholesale,
  fix the `containsBengali` early-return ordering with span-scoped regression
  tests and an EN pin/field-sensitivity negative control.

No patch may be called feature-complete until clipboard, settings, layout,
voice, install/signature, and real-device T1 checks in
`V32-STOCK-PORT-CHECKLIST.md` are complete. An emulator capture may authorize
an experiment; it cannot stand in for the owner's physical-phone release verdict.

## Static suite prerequisites and scope

The docs-and-tests branch has no stock or v32 APKs checked in. The full static
runner (`bash tests/run_tests.sh`) depends on local pinned inputs: exact stock
beta arm64 APK SHA-256 `2672a08a...a7e3`, signed v32 SHA-256
`ce0d7e67...d64`, assembled stock staging APK, and two unsigned host-skeleton
scratch APKs. The scripts currently look for these under `/tmp/rambler-bases/`,
`/downloads/`, and `/tmp/`; those are local test prerequisites, not public
repository files. The executable tool set is Java 17, Python 3, the Android
SDK stub, smali/baksmali, D8, apksig, zip tools, and the Androguard/loguru
Python packages, configured through `TOOLS_DIR/tool-env.sh`. Do not mistake
a green result on a prepared machine for a hermetic public build.

Some Python tests skip when their pinned APK or decoder is absent. The runner
marks selected seam groups `UNTESTED` when a unittest reports a skip, and
omits the stock staging-rename group when its assembled APK is absent. Other
fixtures and the V29 JVM rig have their own prerequisites. A `25 passed, 0
failed` result is meaningful only with the per-test logs showing the pinned
checks genuinely ran without skips; it is not a physical-device T1 verdict.
The shell-build sources and their dependent test, and the unwired standalone
host-descriptor inventory test, are not part of this branch.
