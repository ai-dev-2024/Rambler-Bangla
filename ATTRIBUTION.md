# Attribution and licensing

This work is a derivative of:

- **PixelBoard** by Akshay Kadam (@Akshayykadam) -
  https://github.com/Akshayykadam/PixelBoard - GNU GPL v3.0.
  Patch architecture, extension-carrier pattern, runtime-ABI style, and the
  Rambler selector / Advanced Voice patch conventions are followed here.
- **jasonwu1994/Gboard-patches** -
  https://github.com/jasonwu1994/Gboard-patches - GNU GPL v3.0.
  Original Advanced Voice / Rambler patches, the zh-TW locale-admission
  precedent, and the extension runtime pattern.
- **Morphe** (patch engine) and **smali/baksmali** (JesusFreke, BSD license) -
  used as tools; smali jars are fetched at build time, not vendored.

This repository is therefore licensed **GNU GPL v3.0** (see LICENSE), with
modification notices retained in each source file.

## What this repo deliberately does NOT contain

- No Google Gboard APKs, dex dumps, smali dumps of Google classes, model
  files, or signing keys. The two stock prompt-policy strings are referenced
  only by SHA-256 fingerprint plus the short quoted fragments already
  published in the accompanying static-analysis reports; the full 17.8 KB
  Google prompt is never reproduced.
- The patcher requires the user to supply a lawfully obtained Gboard APK.
  Do not redistribute patched Gboard APKs: Google's binaries, models, and
  keys are not licensed for redistribution, and the GPL covering this patch
  layer grants no rights over them.

## V29 dictionary data (Tier-1 normalization table)

- **Avro Keyboard phonetic dictionary** (OthmanAhmad/Avro Keyboard project,
  Mozilla Public License 2.0) - the romanized-Bangla to Bangla spelling pairs
  underlying the V29 Tier-1 normalization table (2,247 alphabetic pairs,
  plus 18 additions from the maintainer's field corpus; a further 19 corpus
  spellings override Avro-derived values on conflict, e.g. install -> ইনস্টল).
  Composition byte-verified against the shipped build 2026-09-23: total 2,265
  pairs. MPL 2.0 license text: https://mozilla.org/MPL/2.0/
- cmudict (BSD) is NOT shipped in V29; it is reserved for the post-test-pass
  Tier-1b derivation workstream.

## V29.3 loanword spelling data

- **CMU Pronouncing Dictionary** (Carnegie Mellon University, BSD-style
  licence) - pronunciations used by a rule mapper to generate the V29.3
  English-to-Bangla loanword table (data/loanspell/loan-table.tsv and the
  generated GboardRamblerLoanTable.java). Full notice: NOTICE-cmudict.txt.
