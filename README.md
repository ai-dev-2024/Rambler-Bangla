# Rambler Bangla

[![Static test suite](https://github.com/ai-dev-2024/Rambler-Bangla/actions/workflows/tests.yml/badge.svg)](https://github.com/ai-dev-2024/Rambler-Bangla/actions/workflows/tests.yml)

Rambler Bangla is a fail-closed, fingerprint-guarded patch that stops Gboard
18.3.1's Rambler / Jetson **Lite** cleanup stage from Romanizing Bengali,
while preserving every other cleanup behavior. Bengali stays in Bengali
Unicode for `bn-BD`, `bn-IN` and `bn-Beng`; Romanization happens only for an
explicit Latin variant (`bn-Latn`); English always stays Latin. No
transliteration is added and no cleanup stage is disabled.

## Features

### Headline features (V29.3)

- **Multilingual voice typing, one language per sentence**: on the
  multilingual layout (abc → বাংলা), each dictated sentence is written fully
  in Bangla script or fully in English. Start in either language and switch
  whenever you like; the keyboard follows you sentence by sentence.
- **Real Bangla spellings for English words**: English words spoken inside
  Bangla come out as proper transliterations (কোম্পানি, টেলিভিশন, বার্লিন)
  instead of letter-by-letter output. Transliteration only, never
  translation.
- **Clipboard drag-to-reorder**: in the clipboard panel, long-press an item,
  drag it to a new spot, and drop it to change the order.
- **Protected text**: #hashtags, @handles, links, emails and times stay in
  Latin letters on every voice path, so they keep working.

### How each layout behaves

| Layout | Voice and typing result |
| --- | --- |
| English (US) | English only. Rambler changes nothing. |
| বাংলা (native) | Bangla only. Romanized Bangla and English words become Bangla script. |
| abc → বাংলা | Multilingual. Each sentence is Bangla script or English, decided per sentence. |
| Bangla (Latin) | Treated as Bangla: output is Bangla script. |

Gboard's combined "EN · BN" keyboard reports itself as English (US), so it
behaves like the English row. For mixed Bangla and English dictation, use
the abc → বাংলা layout.

### Settings

Both switches are in the keyboard's settings, in the Rambler section.

**Bangla script correction** (on by default)
- On: Rambler converts Romanized Bangla to Bangla script, applies the
  loanword spellings, and follows the per-layout rules above. This is what
  most users want.
- Off: Rambler converts nothing, for voice or typing. You get Gboard's own
  output unchanged, so Bangla speech may appear in Latin letters.
- When to turn it off: if you prefer Romanized Bangla, or to check whether an
  odd result comes from Rambler or from Gboard itself.

**Rambler diagnostics** (off by default)
- Use it only when reporting a problem.
- Turn it on, reproduce the problem (dictate or type the same text), then
  turn it off. Turning it off saves a log to your Downloads folder as
  `RamblerBangla-diag-<date>-<time>.txt` and shows "Rambler diag saved to
  Downloads".
- The log records the active layout and how each dictation or typed text was
  converted, including the text before and after conversion. It stays on your phone
  unless you share it. Read it before you share it, and leave diagnostics off
  in normal use.

### Under the hood

- **Script gate**: two runtime hooks replace the injected "Hinglish Override"
  rule and rewrite only the Romanization bullet of the cleanup prompt's
  SCRIPT GATE, driven by the enabled-language list. Fail-closed: any
  fingerprint, signature, or dataflow miss aborts with no output.
- **Segment-locked multilingual dictation (V28)**: each dictated segment is
  classified once and rendered entirely in one language.
- **Bangla spelling normalization (V29)**: garble-resistant English
  near-match demotion plus a 2,265-pair canonical roman-to-script table.
- **Loanword spelling table (V29.3)**: built from the CMU Pronouncing
  Dictionary (BSD) plus reviewed overrides. See `data/loanspell/`.
- **Side-by-side install**: the test build ships under its own package
  identity (`com.aidev2024.ramblerbangla`) and installs alongside the upstream
  keyboard.
  The repository contains the rename tooling and audit documentation, but no
  APK, generated DEX, key, or other proprietary binary. See `rename/` and
  `docs/SIDE-BY-SIDE.md`.
- **Source only**: this repository distributes no APKs.

## Project status

- **V29.3 (2026-09-24): maintainer test build.** One language per sentence
  in multilingual dictation, plus English loanword spelling in Bangla voice
  output (CMU-derived table + checked overrides). Typing is unchanged.
  Notes: `docs/V29.3-RELEASE-NOTES.md`. Build record: `ledger/v29.3-provenance.md`.
- **V29 (2026-09-23): field iteration, in development.** Not a stable
  release: this cycle's field reports documented open bugs (residual
  spelling errors, language-switch edge cases) and iteration is continuing
  in the open. Design: `docs/V29-DESIGN.md`. Acceptance fixtures:
  `docs/V29-FIXTURES.md`. Build record: `ledger/v29-provenance.md`.
- **v28d: last stable baseline.** Evidence and status detail:
  `docs/EVIDENCE.md`, `docs/V28-SEGMENT-LOCK.md`, `ledger/v28-provenance.md`.

## Build and test

```bash
bash scripts/bootstrap_tools.sh          # fetch pinned toolchain into ./tools
pip install androguard==4.1.4
source tools/tool-env.sh
bash tests/run_tests.sh                  # full suite: expect "17 passed, 0 failed"

# Against a real, user-supplied Gboard 18.3.1 APK:
python3 standalone-patcher/dex_patch.py analyze \
  --apk /path/to/gboard-18.3.1.apk --profile fingerprints/gboard-18.3.1.json
python3 standalone-patcher/dex_patch.py patch \
  --apk /path/to/gboard-18.3.1.apk --out /path/to/out.apk \
  --profile fingerprints/gboard-18.3.1.json --extension-dex <runtime.dex>
scripts/verify_apk.sh single /path/to/out.apk --profile fingerprints/gboard-18.3.1.json
scripts/verify_apk.sh compare /path/to/stock.apk /path/to/out.apk
```

The patcher never signs; re-sign with your own key afterwards (upstream
builds additionally rename the package and bypass signature checks). Building
`runtime.dex`: `javac` the extension class, then `d8 --min-api 24`
(`fixtures/build_fixture.sh` shows both steps).

## Toolchain

Fetched at build time from public repos (none vendored): Temurin JDK 21,
smali/baksmali/dexlib2 2.5.2 + deps (Maven Central), r8/d8 8.3.37, aapt2
8.3.0, apksig 8.3.0, android.jar 4.1.1.4, androguard 4.1.4 (pip).
`scripts/bootstrap_tools.sh` downloads them into `./tools` (or `$TOOLS_DIR`),
checks each file against `tools-src/toolchain.sha256`, builds the small
fixture signer from `tools-src/MiniApkSigner.java`, and writes
`tools/tool-env.sh`. The same steps run in CI on every push and pull request
(`.github/workflows/tests.yml`).

## Repository layout

- `extension-src/.../GboardRamblerLiteScriptRuntime.java` - the policy runtime
  (pure Java, no Android deps; rides the upstream extension carrier).
- `morphe-patch/` - the Morphe bytecode patch + RuntimeAbi merge snippet for
  the upstream keyboard tree (compile-reviewed; built through the validated
  standalone route).
- `standalone-patcher/dex_patch.py` - reproducible local route
  (baksmali -> fingerprint/dataflow-anchored smali insertion -> smali).
- `fingerprints/gboard-18.3.1.json` - the fail-closed profile (documented
  hashes; no Google strings reproduced).
- `fixtures/` - self-built synthetic APK (zero Google content) that mirrors
  the anchors; proves the whole pipeline including d8, aapt2, v2 signing.
- `tests/` - `run_tests.sh`: 51 policy assertions + 17 end-to-end checks,
  including three fail-closed negative tests.
- `scripts/verify_apk.sh` - device-free verification of real outputs.
- `integration/patches-list-entry.json` - upstream patch-list entry.
- `docs/` - design, evidence, validation, licensing, and corpus documents.
- `ledger/` - per-version build provenance records.

## Credits and license

Derivative of **PixelBoard** by Akshay Kadam (GPL v3.0); built with the
Morphe patch engine and smali/baksmali (JesusFreke, BSD). V29 normalization
data derives from the Avro Keyboard phonetic dictionary (MPL 2.0). Full
notices: `ATTRIBUTION.md`. This repository is licensed GNU GPL v3.0 (see
`LICENSE`) and contains no Google binaries, keys, or model files.
