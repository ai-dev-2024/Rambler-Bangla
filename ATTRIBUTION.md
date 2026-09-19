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
