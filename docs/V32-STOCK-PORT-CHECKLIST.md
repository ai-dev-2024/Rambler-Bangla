# V32 -> exact-stock port checklist (research, no port started)

Evidence: signed local v32 APK SHA-256
`ce0d7e6710711f972e24ece2e838a3f51aff5184aeaeb78590dc1b14f182bd64`,
package `com.aidev2024.ramblerbangla`, versionCode `176004244`, versionName
`18.3.1.977415014-beta-arm64-r32`, certificate SHA-256
`085ecb290e3645bca6c3419faeb4f3f0d7a845fccb8621e3030cf87475990702`.
The exact-stock base is SHA-256
`2672a08a0292a307b9f62cd0fa6f48f3bc2334a2f2d9daff7db9d54fc4a2a7e3`.
The staging-only Lite hook build does **not** ship v32 feature parity.
All class/method anchors below were inspected from v32 DEX bytes with
Androguard. They are not proof that stock 18.3.1 has equivalent method
structure, nor device behavior. Do not copy DEXes blindly.

## Dependency and staging sequence

P0-1 (extension host, settings skeleton and manifest/resources) gates every
other component: P0-2 voice and P0-3 clipboard depend on host classes,
preference storage and UI registration. Do not port their DEXes into a hostless
stock app. After a verified skeleton, prioritize the fastest device-testable
value for the owner: first the voice language-gate / committed-text path, then the
layout-pair and sentence/loanword behavior, then clipboard recents/order/drag,
then AdvancedVoice and animation. Split each into its own staging build,
byte pin and focused device matrix; do not wait for one big production port.
For each drop compare against both stock and v32, run safety regression
matrices, and keep the production update blocked until all required parts are
present and the exact full candidate passes device evidence. Some voice
subcomponents may need to land together if they share a single host hook.

## Source availability (current local repo)

The repo is not a complete v32 source tree. It has Java source for
`GboardRamblerLoanSpell`, `GboardRamblerSentenceLang`,
`GboardRamblerNativeSpell` and `GboardRamblerLiteScriptRuntime`, plus loan
source tables/generator, V29.3 smali-hook diff and a test-only V29 rig. The
rig's `ScriptFix`, `SegmentLock`, `Tier1`, and `Diag` are stubs with recorded
outputs, **not** the shipped source. The r34 unsigned staging-shell build script and Activity/provider source are
also absent from this docs-and-tests branch. No rc8 InputMethodManager voice-gate
source or full v32 clipboard/settings/layout/AdvancedVoice/animation source
is in this local checkout. For those, v32 signed DEX is the available
reference and the code must be reversed or recovered from a verified source
archive before estimating implementation time. The old-line v29 Java source
covers only part of mixed-language logic; `SegmentLock` and the host hook
still require DEX recovery. Risk grades below reflect that source gap.

## Lite-hook reconciliation

The stock staging line already has `selectHinglishOverrideRule` at the
`kfd.d` rule literal and `rewriteCleanupPromptScriptGate` after the
`{ENABLED_LANGUAGES}` substitution. They amend the *Rambler Lite cleanup
prompt*, whereas v32 `ScriptFix`/AdvancedVoice operate on voice candidates,
committed text and backend/flag routing. Coexistence is possible only if a
call-graph and device test show one pass at each boundary without duplicate
script conversion or contradictory prompt constraints. Do not assume pure
coexistence. For production, choose one explicit policy after that trace:
absorb the Lite rule into the full voice policy if needed, or retain the Lite
hooks only as an independently guarded Lite-specific path. Never carry two
unexamined cleanup paths into a production APK. Negative controls must cover
Latin-only and mixed-script input, already-Bengali text, and no-op fallback
when Lite fingerprints drift.

## P0: daily-driver behavior required before any production update

1. **Host and settings integration, high effort/high risk.** V32 `classes.dex`
   has 1,367 classes including 270 `com.akshaykadam.pixelboard.extension`
   classes; the stock host `classes.dex` lacks them. V32 manifest has 31
   activities and 11 providers vs stock's 30 and 10. The extras are
   `GboardPatchesSettingsActivity` and `GboardPatchesSettingsProvider`
   (authority `com.aidev2024.ramblerbangla.gboard_patches`). The extension
   registry, settings contract/orchestrator, AdvancedVoice settings, ScriptFix
   UI, clipboard UI, and animation settings all depend on this host. V32
   resources and `classes.dex` identity strings have to be mapped together.
   Rebuild/install must verify every activity/provider, permission, authority,
   and resource ID, not merely copied classes.
2. **Voice text conversion and language routing, high effort/high risk.** V32
   `classes.dex` contains `GboardRamblerScriptFix`, `SegmentLock`,
   `SentenceLang`, `Tier1`, `LoanSpell`, `LoanTable`, `EnglishWords`,
   `LayoutPair`, and `VoiceDiag`. Direct host call sites found in v32:
   `classes2.dex` `Lvtg;->t` calls
   `GboardRamblerScriptFix.lockVoiceCandidates(List,Object)`;
   `Lvri;->a` calls `recordEngine(Object)`.
   `classes3.dex` `Lqrx;->a` calls `voiceLanguageTagFallback()`;
   `Lvrh;->h` calls `processVoice(String)`. These are the exact v32 DEX
   anchors. Exact-stock `Lvrh;->h` and `Lqrx;->a` share the same descriptors;
   `h` has 49 instructions in stock versus 69 in v32, which first rewrites
   only final, nonempty `Lazdo;->c` candidates before scheduling `Lvul`.
   `Lvul.run` passes that same `Lazdg` to `Lajrf.dQ`, which delegates to
   `Lajrf.i`/`j`; this traces object identity but does not prove the final
   editor commit or every voice consumer. `qrx.a` has 277 instructions in
   stock versus 275 in v32: when `Lqsh.f` is absent, v32 substitutes the
   current InputMethodManager subtype locale for stock `Locale.getDefault`,
   falling back to default if the subtype cannot be read. That is a
   recognition-header fallback, not proof of a Bengali admission gate.
   V32 `processInternal` returns the whole input unchanged when any Bengali
   character occurs, before mixed-span conversion; handle the known
   mid-sentence regression separately. The production candidate needs
   a device-proven locale-gate repair rather than the unverified rc8 analogy,
   v29 mixed-language script logic,
   loanword spellings, and correct committed-text path, with device evidence.
   `GboardRamblerLayoutPair` has `adjust`, `showToggle`, `toggleOn`,
   `setToggleOn` methods. No direct non-extension invoke to LayoutPair was
   found in the narrow classes.dex/classes2/classes3 scan, so its host wiring
   may be through other class methods, fields, or reflection; trace it before
   porting. The EN/BN layout UI must be verified on device.
3. **Clipboard presentation and behavior, high effort/high risk.** V32 has
   `GboardRamblerClipOrder`, `ClipRecents`, `ClipRecentsUi`, `ClipDrag`,
   `ClipSmooth`, `ClipMask`, `ClipAccess` in `classes.dex`. Direct v32 host
   calls: `classes3.dex` `Lkta;->b` and `Lkut;->E` call
   `ClipOrder.apply(List)`; `Lkut;->F` calls
   `ClipRecents.read(Context)`; `Lkut;->p` calls `ClipDrag.attach(...)`
   and `ClipMask.shouldMask(Context,boolean)`; `classes2.dex` `Lksu;->z`
   and `Llae;->c` call `ClipMask.shouldMask(...)`. Recents is known to trim a
   displayed list section, not proven to limit stored clipboard capacity.
   Port drag, order, mask, recents UI and saved preference together; verify
   actual stock adapter list ownership, retention and capacity on device.

## P1: baseline product settings and routing

4. **AdvancedVoice and official voice selection, high effort/high risk.** V32
   runtime/settings classes include `GboardAdvancedVoice1803Runtime`,
   `GboardAdvancedVoice1803RuntimeSettings`, `GboardAdvancedVoice1803Policy`,
   `GboardAdvancedVoiceSettings`, `GboardAdvancedVoiceSettingsFeature`, plus
   `GboardRambler1803OfficialSelectionRuntime` and `...StockPolicy`.
   `classes.dex` `Lacps;->g` calls `AdvancedVoice1803Runtime.afterFlagValue`;
   `Laaeo;->a` and `VoiceSettingsFragment->aF` update official selection;
   `VoiceSettingsFragment->aD/ac/f` bracket voice settings scope;
   `Lkcm;->ge` brackets default-selection suppression. Runtime also exposes
   initial-settings, MDD-provider, native-readiness and formatter hooks.
   Dependencies include SharedPreferences, reflection handles, official
   selection scope, host flag reader and UI registry. Do not assume the
   standalone Lite hook reproduces this behavior.
5. **Animation selector, medium effort/medium risk.** V32's
   `GboardRamblerAnimationSettings`, dialog runnable and settings-feature
   lambdas survive in the extension DEX. `GboardRambler1803StockPolicy`
   invokes `AnimationSettings.isAnimationFlag/readMode`; UI selection lives
   in the extension settings activity. Restore feature UI, preference key,
   flag mapping and visual behavior together.
6. **Diagnostics / AD experiment, medium effort, product-mode sensitive.** V32
   contains `GboardRamblerDiag/DiagUi`, `VoiceDiag`,
   `GboardRamblerAdExperiment/Ui`. V32 direct host calls: `classes.dex`
   `Lkcm;->j` captures pre-commit; `classes2.dex` `Lkcn;->a/getModuleDef`
   records resolved backend; `classes3.dex` `Lkco;->a` captures apply,
   `Lkew;-><init>/a/b` records backend input/fallback/post-backend, and
   `Lkco/Lkcy` bump counters. Respect the established staging/production
   diagnostics split; no private text/audio logging without the prior
   security restrictions and user review.

## P2: installation and identity decisions

7. **minSdk and update lineage, medium effort/high release risk.** V32 minSdk
   is 32 and targetSdk 37; stock is minSdk 26 and targetSdk 37. The staging
   line intentionally keeps 26. A production port must decide whether to
   retain the v32 32 floor and check resources/APIs before lowering it. The
   production package remains `com.aidev2024.ramblerbangla` with the same
   release certificate, and versionCode must exceed 176004244. Staging is a
   separate app `com.aidev2024.ramblerbangla.staging`; it must never be
   promoted by renaming the package alone.
8. **Resources and packs, high audit effort/medium release risk.** Exact
   stock versus v32 ZIP comparison: stock 9,506 entries, v32 9,201; v32 adds
   only three names: `classes5.dex`,
   `lib/arm64-v8a/libdictation_jni.so` (4,080,904 bytes; SHA-256
   `791c7d538afd41588b890f12cf44a5074c3dcb04777d1324a30e1e498ed00f55`),
   and `res/drawable/ic_gemini_sparkle.xml` (680 bytes). All 146 asset names
   and bytes are identical. All 15 common native libraries are byte-identical;
   v32 has the one added dictation JNI library. Stock has 302 res names absent
   in v32 (166 PNG, 134 WebP, 2 XML: `res/OhF.xml` and
   `res/xml/splits0.xml`). Of 8,779 common XML resource files, 8,643 differ
   in raw bytes, likely resource rewriting/repackaging but not assumed
   semantically equivalent. The 54 common PNG and 80 common WebP files are
   byte-identical. `resources.arsc` and manifest differ as expected. Stock
   has five META-INF/services entries absent in v32; inspect whether their
   removal changes provider loading before porting. V32 is minSdk 32, stock
   26; the added JNI and resource references need install-time and runtime
   checks for both floors. The extra v32 library's exact linkage/call path
   remains to be mapped, so do not guess it is safe to omit.

## Release gate

Port each component on pinned base bytes, verify exact symbols and method
signatures, run static and device matrices (including the owner's real mixed-language
dictations and the clipboard/voice-gate regressions), then review the complete
artifact before signing or updating production. A green source rig is not an
Android T1 verdict. This document is a port checklist, not a build approval.

See `STOCK-V32-VOICE-LOCALE-TRACE.md` for the separate pinned layout-registration versus recognition-header distinction; neither establishes voice admission.

## 18.0.3 analogy is not an 18.3.1 target

The pinned upstream `GboardAdvancedVoice1803ZhTwPatch.kt` targets an
`Lsdc;-><init>(Context,...,Set)` with 23 parameters and an `Lrwr;` formatter
constructor in Gboard 18.0.3. On the hash-pinned stock 18.3.1 base,
`Lsdc;-><init>(Lbcsx;)V` is a coroutine adapter, and `Lrwr;` has only
`apply(Object)`. Neither signature matches; copying the zh-TW injection
would target the wrong class. The local Rambler Lite
`admitExactBengaliLocales(Set)` method is an OFF-by-default experiment, not
an upstream or v32 implementation. Its standalone test does not establish
that Bengali is filtered at a supported-locale Set on this base. First
identify the 18.3.1 supported-locale source and obtain a device decode of
raw ASR, candidate text, and committed editor text; only then select a gate.
