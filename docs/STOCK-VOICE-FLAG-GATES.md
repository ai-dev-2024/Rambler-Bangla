# Stock 18.3.1 voice flag defaults versus observed device eligibility

Exact stock APK SHA-256 `2672a08a0292a307b9f62cd0fa6f48f3bc2334a2f2d9daff7db9d54fc4a2a7e3`. This is independent local DEX inspection following Beta's stock-only static lead (`#tab-room`, thread 1790596911.650769, Beta message 1790597907.781269). The post is third-party research; the facts below were rechecked from pinned stock `classes.dex`. No v32 diff or runtime verdict is implied.

`Lajrr.<clinit>` defines four distinct runtime flags/defaults:

| Field/flag | Stock default | Scope |
|---|---|---|
| `Lajrr.m` / `s3_asr_language_tags_list` | Long comma-separated lower-case list includes `bn-bd`, `bn-in`, `bn-latn`, `en-us` | S3 ASR tag default, **not** live engine selection |
| `Lajrr.p` / `s3_langid_languages_list` | Base language list contains `en`, not `bn` | S3 LangID, secondary languages |
| `Lajrr.l` / `fallback_ondevice_input_method_entries` | `de-DE,en-AU,en-CA,en-GB,en-IN,en-US,es-ES,es-US,fr-FR,hi-IN,id-ID,it-IT,nl-NL,pt-BR,ru-RU` | Fallback on-device auto-pack eligibility, no Bengali by default |
| `Lajrr.k` / `ondevice_input_method_entries` | `en-US` | Primary on-device auto-download default |

`Lamgk.e()` parses flags m and p separately with `Lamgk.d(String)->Set`. `Lamgk.b(Lajpe;)Z` checks full locale tag against S3 ASR Set; `Lamgk.c(Lajpe;)Z` checks base language against LangID Set. `Lamgi.f` calls `Lamgk.b` over primary and alternate locale choices; `Lamgi.d` calls `Lamgk.c` when gathering secondary languages. `Lvze.f/g` controls a fallback on-device Set used in `Lvze.e`; its `c` path also checks readiness through `Lvwl.i`, so its default Set alone does not decide live handling. `Lvxk.f` parses the primary on-device Set; `Lvxk.c` separately tests pack readiness. `Lvwy.b` contains a selected-subtype/on-device download path. `Lamgl.a` is a separate contact-request list read in `Lvti.g`, not a universal voice gate (verify that usage independently before attributing its business purpose).

Result: a blanket claim that Bengali is missing from *the* ASR admission Set is false for the stock S3 default. The actual runtime flag values, selected backend, downloaded model, eligibility decision, LangID routing and final editor commit remain UNOBSERVED. Avoid making a patch based on the wrong 18.0.3 signatures or this default-list inspection. Native-arm64 evidence still needs the active flags and backend, request locale and raw ASR, candidate before/after, and editor commit.
