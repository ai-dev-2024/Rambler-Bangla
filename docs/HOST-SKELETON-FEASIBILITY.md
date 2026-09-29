# Exact-stock host skeleton feasibility (research, not a build)

Pinned inputs: stock APK SHA-256
`2672a08a0292a307b9f62cd0fa6f48f3bc2334a2f2d9daff7db9d54fc4a2a7e3`,
v32 signed APK SHA-256
`ce0d7e6710711f972e24ece2e838a3f51aff5184aeaeb78590dc1b14f182bd64`.
Run `scripts/host_skeleton_inventory.py --stock ... --v32 ... --out ...`
with Androguard to reproduce the descriptor counts. This is a read-only
feasibility gate. No host code or APK has been ported.

## Class partition and missing source

Stock: 40,644 distinct class descriptors across four DEX files. V32: all
40,644 stock descriptors plus 1,356 new descriptors, five DEX files.
All 1,356 new descriptors reside in v32 `classes.dex`: 270
`com.akshaykadam.pixelboard.extension` classes and 1,086 Kotlin/annotation
support classes. V32 repartitions the stock classes: 12,922 stock classes
from stock `classes.dex` into v32 `classes2.dex`; 13,647 from stock
`classes2.dex` into v32 `classes3.dex`; all 13,435 from stock
`classes3.dex` into v32 `classes4.dex`; all 629 from stock
`classes4.dex` into v32 `classes5.dex`. Eleven stock classes moved from
stock classes.dex/classes2.dex into v32 classes.dex. There are zero duplicate
descriptors inside either input. Copying or appending whole v32 classes.dex
to stock would create duplicate host definitions; it is not a supported route.

The repo holds only four Java sources, not the 270 v32 extension classes or
1,086 support classes. The v32 DEX containers for classes.dex/classes2.dex/
classes3.dex are version 040, whereas the local baksmali 2.5.2 handles only
035; Androguard can inspect them, but a class extraction/reassembly route
for 040 must be selected and verified independently. The stock base's four
DEXes are 035. No historical rc2 DEX may be blindly overlaid onto this base.

## Settings dependency and resource gate

The v32 manifest adds `GboardPatchesSettingsActivity` and
`GboardPatchesSettingsProvider` (`.gboard_patches` authority under Rambler
package). `GboardPatchesSettingsActivity.buildRootScreen` calls feature
settings, animation, ScriptFix UI, ClipMask, ClipRecents UI, and the
`GboardSettingsText` catalog; registering the full v32 Activity as a bare
skeleton would implicitly pull in these feature dependencies. A minimal host
skeleton must either implement an audited minimal Activity/provider and
feature registry from verified source/DEX, or import the complete compatible
closure with all dependencies. It must not expose dead toggles.

V32's `R$string` fields (99), `R$color` (12) and `R$drawable` (2) have IDs that
would resolve to other resource types or nothing when interpreted directly
against v32 resources. The settings text path first calls
`GboardSettingsTextCatalog.template()`, whose `createEnglish()` maps those
IDs to literal text; fallback `Context.getString(id)` only occurs after a
catalog miss. A port must carry that catalog or replace it with explicit
stable text, and test the fallback. Drawable/color use needs separate trace.
Do not infer a working UI from class existence or ARSC parse alone.

## Proposed first reversible unit

1. Keep the staging package and pinned APK unchanged while extracting a
   verified dependency graph for the Activity/provider, catalog and manifest.
   Compare each class descriptor against stock and reject duplicates.
2. Build a minimal source-backed shell for a staging-only settings entry,
   without voice/clipboard toggles, and test resource IDs and authority
   uniqueness against the signed staging baseline. This is a **proposal**,
   not an approved implementation or a claim that it has been built.
3. Only then add one feature at a time with a pinned-byte diff and device
   matrix; the full v32 Activity is not a minimal shell.

The biggest unanswered decision is whether to recover exact extension source
from a verified archive or reverse only the minimal shell from v32 DEX.
Any host implementation needs review before signing and never updates the
production package until the complete v32 parity gate is satisfied.
