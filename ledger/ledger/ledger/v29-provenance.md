# V29 Provenance - segment-lock hardening + Bangla spelling normalization

Date: 2026-09-23 (AEST). Builder: maintainer. Repo: ai-dev-2024/Rambler-Bangla.
Authorization: owner approval 2026-09-23,
after loop review (external design review + engineering review) returned MODIFY-before-build;
all amendments incorporated in docs/V29-DESIGN.md v2 (amendment map in section 9).

## Artifacts (signed, v22 key, cert sha256 5ca0623a1f3beb027d3eb87ad0811e97db0ebb8736bd11af0831ab7d6bafbc31)
- v29-prod.apk    sha256 c277b65e928f728936c3e5722ab7b80dcb1ad67c27616c114a71be4a62085f00  https://gofile.io/d/a0gGjAcA
- v29-staging.apk sha256 6fc37a45c0ebfd8072adcb45b6aab05d56fb5e7a7a130324e7fac9a9361b03f6  https://gofile.io/d/HO0CVM4i
- classes-v29.dex sha256 94ad4f4e324cec5751d47846c41b855e654f437be2f303a07f4e3786dbf78347 (prod)
- classes-v29-stg.dex sha256 6fdcd39cb4dfa550246c32e4cac2976fff289139bf63793e8d062874d377b5b6 (staging)
- Rig jar (dex-derived, byte-fidelity gate): rambler-v29.jar from classes-v29.dex via dex2jar.
- Intermediate unsigned aligned APKs uploaded earlier (gofile.io/d/YFeb6prV, gofile.io/d/lsnWYQ3a) are BUILD INTERMEDIATES - do not distribute.
- v28d remains the last prior good: prod 5889214e492541fa6024f03e023ae471e55f7d300395d0027235d81a7ef85362. All earlier APKs (v27.x, v28, v28b, v28c) remain superseded - do not distribute.

## Patch surface (smallest possible on v28d)
- GboardRamblerSegmentLock.smali: A2 garble demotion (bounded ED1 + garble allowlist + 129-word PROTECT_BN),
  conservative morphology (doubled-consonant ed/ing), Tier-1 consult at emission (locked segments only),
  session pin machinery (AUTO/BN/EN, in-memory, 2-min inactivity reset; EN/BN unreachable from UI in this build).
- GboardRamblerTier1.smali: NEW - 2,265 canonical roman->script pairs (Avro MPL 2.0 + 19 corpus overrides).
- GboardRamblerScriptFix.smali: UNTOUCHED (no hook changes; v28d k1/k3 paths byte-identical).

## Evidence (all on the dex-derived rig jar unless noted)
- battery 85/85; adversarial 14/14; matrix pass; hardening pass; reverse 0/39; driver 19-line corpus pass; fuzz 720/720.
- v29-vs-v28d diffs: 15 battery + 3 adversarial + 3 matrix + 4 driver + 2 hardening - ALL Tier-1 spelling emission
  inside already-locked Bangla segments. ZERO segment-lock decision changes outside docs/V29-FIXTURES.md named fixtures.
- Field-incident fix: garbled repro sentences ("rigarding...", "so hwen...") stay English; "outputted" stays English.
- EN pin: 14/14 byte-exact passthrough (punctuation, apostrophes, emoji, handles, URLs, mixed script, whitespace, numbers).
- Demotion review: 108 ED1 collisions published (v29/collisions.json); zero false demotions on every protected corpus measured separately.
- Spelling corpus (docs/spelling-corpus-v1.tsv): 35/36 WRONG fixed byte-exact; zero regressions on OK/DIALECT.
- CI: android-smoke run #13 (this build) - result recorded below when green.

## Licenses
- Avro phonetic canonical autocorrect DB: MPL 2.0 (attribution; source: avrolib.js/avrodict.js in-tree reference only).
- spelling-corpus-v1.tsv overrides: MK soak 2026-09-23 (his expected spellings win conflicts: install->ইনস্টল over Avro ইন্সটল).
- cmudict (BSD, cmusphinx): analysis input for Tier-1b (not shipped in this build).
- bn_BD.dic (GPLv2): analysis only, never shipped. Enriched autodict fork: no license - excluded.

## Known limitations (reported, not hidden)
- Pin UI not in this build: pin machinery rig-tested (EN/BN lanes) but unreachable by the user; AUTO only. V29.1.
- Host "skip:has-bengali" guard (pre-existing v27/v28 behavior) also binds the BN pin lane; AUTO byte-identical to v28d.
- "but" stays Latin in Bangla context (discourse-marker isolation, pre-existing design).
- Acoustic locale routing: excluded from V29 per loop review (experiment only, zero behavior dependency).
