# Rambler stock-Lite staging lineage

This is a separate test app, not an update to the Rambler production app.
The owner confirmed that `com.aidev2024.ramblerbangla.staging` is the application ID for this and future test builds.
This confirms the application-ID lineage, not device behavior or a final
production release.

- Application ID: `com.aidev2024.ramblerbangla.staging`
- First versionCode: `176004245`
- First versionName: `18.3.1.977415014-beta-arm64-r33-staging`
- Launcher label: `Rambler Staging`
- Signing cert: the existing Rambler release certificate, SHA-256
  `085ecb290e3645bca6c3419faeb4f3f0d7a845fccb8621e3030cf87475990702`.
  Its private key stays in the owner's professional Drive custody and is never in this repo.
- Input: exact stock beta arm64 APK SHA-256
  `2672a08a0292a307b9f62cd0fa6f48f3bc2334a2f2d9daff7db9d54fc4a2a7e3`,
  patched for the guarded Rambler Lite script policy only. This build has no
  PixelBoard/Rambler v32 clipboard, voice-gate, layout, or settings feature parity.

Keep staging's package ID and certificate stable in future staging builds.
Never use the production application ID for this stock-only test build.
Version codes rise within each line. The production daily driver has its own
identity and release path. No stock APK or signing material is committed here.

The stock-specific rename route is guarded by its assembled input SHA and
exact manifest/DEX anchors; unlike the older PixelBoard rename route, it
changes stock `com.google.android.inputmethod.latin` identity directly. The
staging label is a literal typed AXML attribute; minSdk stays at the stock 26.

- Next host-skeleton test versionCode: `176004246`, versionName
  `18.3.1.977415014-beta-arm64-r34-staging`. This increments the existing
  staging line, retains package/cert and r33 Lite hooks, and adds an Advanced
  settings entry to an honest foundation-only screen in a separate local
  experiment. Its shell build script and Java source are not included in this
  docs-and-tests branch. It does not add voice or clipboard parity. Static
  checks cannot establish a device result.
