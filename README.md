# Rambler Bangla


## Rambler Bangla side-by-side build

The experimental test APK is rebuilt under its own package identity:
**Rambler Bangla** (`com.aidev2024.ramblerbangla`). It can install alongside
PixelBoard instead of being treated as an update signed by a different key.

The packaging step rewrites the manifest package, all 11 provider authorities,
declared permissions, phenotype and deep-link references, referenced binary
XML resources, the `resources.arsc` package field, and exact identity strings
in `classes.dex`. It then repacks with the alignment Android requires and is
signed with a dedicated experimental key. The repository contains the rename
tooling and audit documentation, but no APK, generated DEX, key, or other
proprietary binary. See `rename/` and `docs/SIDE-BY-SIDE.md`.


Rambler Bangla is a fail-closed, fingerprint-guarded patch that stops Gboard 18.3.1's Rambler /
Jetson **Lite** cleanup stage from Romanizing Bengali, while preserving every
other cleanup behavior. Bengali stays in Bengali Unicode for `bn-BD`, `bn-IN`
and `bn-Beng`; Romanization happens only for an explicit Latin variant
(`bn-Latn`); English always stays Latin. No transliteration is added and no
cleanup stage is disabled.

Public source: https://github.com/ai-dev-2024/Rambler-Bangla

The Android test build uses the display name **Rambler Bangla** and a distinct
application ID so it can be installed alongside PixelBoard. The application-ID
rewrite is part of the packaging step; the `com.akshaykadam.pixelboard` names
under `morphe-patch/` and `extension-src/` are upstream integration namespaces
and remain unchanged for source compatibility and clear attribution.

## Evidence basis (static, verified)

From the analysis of the PixelBoard 18.3.1 artifact (APK SHA-256
`e229d982ff65b24d71aeee804dcce6863e902ec409a0379ca3deaef17e30f6bd`):

| Anchor | Where | Fingerprint (SHA-256) |
|---|---|---|
| 289-byte "Hinglish Override" rule, unconditionally injected for any Indian-language+English mix, naming Bengali/Banglish | `classes3.dex`, `Lkfd;->d(Lhrl;Ljava/lang/String;ILqqi;Laebb;Ljava/lang/String;Laugd;Ljava/util/concurrent/atomic/AtomicBoolean;)V` | `a024513458b73f915c78438cea2a9457b9c5aed28da3644030c3dc76cd0ac6e9` |
| 17,802-byte Lite cleanup prompt, "SCRIPT GATE" Branch A mandates Indic->ASCII Romanization on a Latin keyboard | `classes3.dex`, `Lkew;->b(Ljava/lang/Object;)V` | `347a9484392763d5fb16660bc3ca9bbceb1851c96f2024f96c1e9327f504696e` |

The same 289-byte rule exists unchanged in the stock input APK: the behavior
is inherited from Gboard, not introduced by PixelBoard. This evidence covers
the **Lite (local cleanup) path only**; remote Rambler Base/S policy cannot be
established statically (see docs/VALIDATION.md).

## Design

Two runtime hooks in `kfd.d`, driven by the enabled-language data that already
flows through the method (`{ENABLED_LANGUAGES}`, joined from the
enabled-language collection):

1. `selectHinglishOverrideRule(stockRule, enabledLanguages)` replaces the
   `{HINGLISH_OVERRIDE_RULE}` substitution value:
   native Indic tag present -> native-script preservation rule;
   only explicit `-Latn` Indic tags -> stock rule;
   no Indic tags -> rule dropped (it is a no-op anyway);
   unknown/blank -> stock rule (fail-safe).
2. `rewriteCleanupPromptScriptGate(prompt, enabledLanguages)` rewrites only
   the Branch A Romanization bullet of the SCRIPT GATE, only under a native
   Indic policy, and only when the expected stock block is present verbatim;
   everything else in the prompt stays byte-identical.

Fail-closed gates: exact method signatures, both string fingerprints
(whole-APK sweep), resolvable `{ENABLED_LANGUAGES}` replace-site dataflow,
anchor-order check, already-patched check. Any miss aborts with no output.

## Layout

- `extension-src/.../GboardRamblerLiteScriptRuntime.java` - the policy runtime
  (pure Java, no Android deps; rides PixelBoard's extension carrier).
- `morphe-patch/` - the Morphe bytecode patch + RuntimeAbi merge snippet for
  the real PixelBoard tree. NOTE: the credentialed Morphe Gradle plugin could
  not be resolved in the offline environment, so this source is delivered
  compile-reviewed but built through the validated standalone route below.
- `standalone-patcher/dex_patch.py` - reproducible local route
  (baksmali -> fingerprint/dataflow-anchored smali insertion -> smali).
  `analyze` prints every anchor/register it resolves; `patch` is fail-closed.
- `fingerprints/gboard-18.3.1.json` - the fail-closed profile (documented
  hashes; no Google strings reproduced).
- `fixtures/` - self-built synthetic APK (zero Google content) that mirrors
  the anchors; proves the whole pipeline including d8, aapt2, v2 signing.
- `tests/` - `run_tests.sh`: 51 policy assertions + 17 end-to-end checks,
  including three fail-closed negative tests.
- `scripts/verify_apk.sh` - device-free verification of real outputs
  (package/version/signature/decode + fingerprint anchors).
- `integration/patches-list-entry.json` - PixelBoard patch-list entry.

## Quickstart

```bash
source $HOME/tools/tool-env.sh     # JDK 21 + smali classpath (see below)
bash tests/run_tests.sh                    # full suite: expect "17 passed, 0 failed"

# Against a real, user-supplied Gboard 18.3.1 APK:
python3 standalone-patcher/dex_patch.py analyze \
  --apk /path/to/gboard-18.3.1.apk --profile fingerprints/gboard-18.3.1.json
python3 standalone-patcher/dex_patch.py patch \
  --apk /path/to/gboard-18.3.1.apk --out /path/to/out.apk \
  --profile fingerprints/gboard-18.3.1.json --extension-dex <runtime.dex>
scripts/verify_apk.sh single /path/to/out.apk --profile fingerprints/gboard-18.3.1.json
scripts/verify_apk.sh compare /path/to/stock.apk /path/to/out.apk
```

The patcher never signs; re-sign with your own key afterwards (PixelBoard
builds additionally rename the package and bypass signature checks). Building
`runtime.dex`: `javac` the extension class, then `d8 --min-api 24`
(`fixtures/build_fixture.sh` shows both steps).

## Toolchain

Fetched at build time from public repos (none vendored): Temurin JDK 21,
smali/baksmali/dexlib2 2.5.2 + deps (Maven Central), r8/d8 8.3.37, aapt2
8.3.0, apksig 8.3.0, android.jar 4.1.1.4, androguard 4.1.4 (pip).
`$HOME/tools/tool-env.sh` wires them up.

## Limits

- The one thing static work cannot finish is on-device confirmation for the
  real kfd.d register map and for Base/S. `analyze` resolves the register map
  on the real APK at patch time; the S23 Ultra behavior matrix is in
  docs/VALIDATION.md.
- The zh-TW-analog locale-admission hook (`admitExactBengaliLocales`) is
  hypothesis-stage and OFF by default; Bengali is absent from Google's
  official Rambler tuned-language list, so remote Base/S may Romanize
  regardless of any client patch.
