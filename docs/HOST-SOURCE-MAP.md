# Pinned host source and binary correspondence

Upstream: https://github.com/Akshayykadam/PixelBoard at commit
`06228a0003a416f04b6a35c3d31530d04032fd6a` (GPL-3.0, see its `LICENSE`).
Checked-in extension Java source: 37 top-level classes, including Activity,
Provider and `GboardSettingsText`. The settings catalog source is generated
from `extensions/extension/src/main/settings-text/gboard_settings_text.xml`
by `extensions/extension/build.gradle.kts`; do not misclassify it as DEX-only.
The upstream settings Activity does not contain the v32 Rambler features.

The pinned upstream output APK (`output/PixelBoard-18.3.1.apk`, SHA-256
`195bc6bdf622725441c477097c232ef53690be03ce12bd7f27bc2a84260fd58b`)
contains 232 extension descriptors. All 232 occur among the 270 v32 extension
descriptors. V32 has 38 extension descriptors absent in the upstream output:
36 Rambler, two ClipMask settings classes. These counts were taken from the pinned upstream output and v32 APKs. The
underlying exact descriptor lists are not part of this docs-and-tests branch.
This is a descriptor correspondence, not proof that methods or resources match.
The 38 need source recovery or scoped reverse engineering when ported.

V32's manifest has a nonexported `GboardPatchesSettingsActivity` with stock
SettingsActivity theme resource `0x7f15042f`, and a nonexported
`GboardPatchesSettingsProvider` with authority
`com.aidev2024.ramblerbangla.gboard_patches`; no duplicate authority. The
signed stock staging baseline has neither component. An added staging provider
must use `com.aidev2024.ramblerbangla.staging.gboard_patches`, not v32's
production authority. Stock SettingsActivity theme is `0x7f15042f`.
Upstream patch logic inserts a settings XML entry as well, but compiled stock
resource paths differ; a manifest-only shell does not establish menu navigation.

Do not copy v32's full settings Activity as the shell: it calls unavailable
feature UI classes. The proposed staging shell can display a plain, truthful
foundation screen with no feature controls. Reachability and visual layout
remain device-gated; static AXML/DEX checks cannot establish UI behavior.

Release note: upstream is GPLv3, and redistribution must respect source and
notice obligations. Review exact final distribution form separately before
public final APK or production GitHub update.

## Local unsigned shell evidence, not a build in this branch

A separate local r34 experiment compiled a foundation-only Activity/provider
with Android SDK stubs and D8, added two nonexported manifest components and
`classes6.dex`, and ported the "Advanced settings" entry into `res/B_o.xml`
and `res/IeH.xml`. The local static checks observed 31 activities and 11
providers against the signed staging baseline's 30 and 10, no duplicate
authorities, and only the manifest and two settings XML files changed among
pre-existing ZIP entries. These checks do not establish device reachability,
visual quality, feature controls, or a distributable build.

**The unsigned-shell build script, manifest/settings patchers, and four shell
Java files are not included in this docs-and-tests branch.** The shell-specific test also is not included: it imports the omitted manifest
patcher and would fail test discovery. A separate host-descriptor inventory
test is omitted because it is not wired into the aggregate runner; the
`host_skeleton_inventory.py` helper remains for the pinned voice test. Separately produced local scratch APKs
were checked, but those checks cannot be rerun from this branch. This branch
cannot rebuild the r34 shell from source. The missing source and build path must be
reviewed separately before any shell build or release claim.
