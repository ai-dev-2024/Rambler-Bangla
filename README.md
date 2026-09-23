# Rambler Bangla

Rambler Bangla is a fail-closed, fingerprint-guarded patch that stops Gboard
18.3.1's Rambler / Jetson **Lite** cleanup stage from Romanizing Bengali,
while preserving every other cleanup behavior. Bengali stays in Bengali
Unicode for `bn-BD`, `bn-IN` and `bn-Beng`; Romanization happens only for an
explicit Latin variant (`bn-Latn`); English always stays Latin. No
transliteration is added and no cleanup stage is disabled.

## Features

- **Script gate**: two runtime hooks replace the injected "Hinglish Override"
  rule and rewrite only the Romanization bullet of the cleanup prompt's
  SCRIPT GATE, driven by the enabled-language list. Fail-closed: any
  fingerprint, signature, or dataflow miss aborts with no output.
- **Segment-locked multilingual dictation (V28)**: each dictated segment is
  classified once (Bangla vs English) and rendered entirely in that language,
  replacing the per-word convert/keep that scrambled mixed dictation.
- **Bangla spelling normalization (V29, in development)**: garble-resistant
  English near-match demotion plus a 2,265-pair canonical roman-to-script
  table, applied only inside locked Bangla segments.
- **Side-by-side install**: the test build ships under its own package
  identity (`com.aidev2024.ramblerbangla`) and installs alongside the upstream
  keyboard.
  The repository contains the rename tooling and audit documentation, but no
  APK, generated DEX, key, or other proprietary binary. See `rename/` and
  `docs/SIDE-BY-SIDE.md`.
- **Source only**: this repository distributes no APKs.

## Project status

- **V29 (2026-09-23): field iteration, in development.** Not a stable
  release: this cycle's field reports documented open bugs (residual
  spelling errors, language-switch edge cases) and iteration is continuing
  in the open. Design: `docs/V29-DESIGN.md`. Acceptance fixtures:
  `docs/V29-FIXTURES.md`. Build record: `ledger/v29-provenance.md`.
- **v28d: last stable baseline.** Evidence and status detail:
  `docs/EVIDENCE.md`, `docs/V28-SEGMENT-LOCK.md`, `ledger/v28-provenance.md`.

## Build and test

```bash
export TOOLS_DIR=/path/to/tools          # JDK 21 + smali classpath (see Toolchain)
source "$TOOLS_DIR/tool-env.sh"
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
`$TOOLS_DIR/tool-env.sh` wires them up.

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
