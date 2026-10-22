Kanglish FOSS — Current App Audit

Date: 19 October 2026
Scope: Current Android working tree after the repair pass, source/build inspection, and a physical-device smoke test on the owner's S23 FE running Android 16. The repaired APK was installed over the previous version while preserving app data. No training was run. This is not a complete acceptance test, a linguistic benchmark, or a network-traffic audit.

Kanglish currently runs local glossary translation and native 0.5B GGUF inference on the phone. In-app copy/paste, sample chat loading and row translation, and a direct Android PROCESS_TEXT intent returned results. A selected message from the owner's nominated WhatsApp group was copied into the floating translator, but a native-library compatibility warning interrupted the workflow and the trampoline brought Kanglish in front of WhatsApp. It is a working prototype with observed integration and translation-quality defects.

**Device findings that change the earlier source-only audit:**

- Android reports that `libkanglish_llama.so` is not 16 KB-compatible; its ELF load segments have 4,096-byte alignment. This phone uses 4,096-byte pages. The compatibility dialog held focus and delayed clipboard capture until dismissed, and appeared again in the text-selection test.
- WhatsApp copy-to-bubble captured the exact selected message and generated a result; copying that result back into the app passed. The navigation did not remain over WhatsApp. The private message's translation was not graded without an owner reference.
- The two owner-authored neural checks lost time words: `naale college ge barthira?` became `Are you coming to college?`, omitting tomorrow; `yenu guru ivattu plan?` became `What is the plan bro?`, omitting today. The glossary phrase `sakkath aagide` returned `It's awesome / great.` These are examples, not an overall accuracy score.
- The installed model is `Kanglish_Qwen_0.5B_V3_Merged`, labeled 494M, Q8_0, approximately 506 MiB on disk. It is not Q4_K_M. One warm process snapshot measured about 683 MiB PSS; it is not peak memory or a performance guarantee.
- The main tabs are readable, but chat cards remain bulky and the expanded overlay uses substantial space for short messages. Notification permission is denied. No fatal/ANR markers were found in the inspected current-process logs.

See [DEVICE_TEST_REPORT.md](DEVICE_TEST_REPORT.md) for exact evidence, test boundaries, untested cases, and recommended fixes. The implementation inventory below remains applicable; device outcomes are limited to the flows described above.

**The current build** is version 0.1.0, package `org.kanglish.app`, with a debug APK of 26,252,606 bytes (25.04 MiB). It supports ARM64 devices running Android 9/API 28 or newer and targets Android 15/API 35. The APK contains `libkanglish_llama.so`; it contains no GGUF model. A first-time user must import model weights to translate sentences beyond exact glossary matches.

**What a user can currently do:**

| Area | Implemented behavior | Practical limit |
|---|---|---|
| Translate tab | Type or paste a message, translate it, copy the English output, and clear the input. Multiline text is supported. | No conversation history or cloud review is supplied by this entry point. Translation quality depends on the imported model. |
| Chats tab | Import a WhatsApp `.txt` export or load the bundled sample; translate one message or a batch; copy translations; flag incorrect meanings. | The app imports an existing export. It does not export chats from WhatsApp or directly access WhatsApp's private database. |
| Chat parsing | Recognizes common dated sender/message formats, bracketed timestamps, optional AM/PM, and multiline message bodies. | This is a regex parser, not comprehensive support for every locale, system message, or media placeholder. It reads the entire file into memory. |
| Settings | Select/unload a model, configure the floating bubble, open accessibility settings, configure optional cloud review, and inspect/clear saved feedback. | Cloud settings are collapsed by default. Some settings and errors still need usability refinement. |
| Floating bubble | Show a draggable 56dp K bubble over other apps; copy a WhatsApp message and tap the bubble to translate; read, scroll, copy, clear, minimize, or close the result panel. | Requires overlay permission. Copying alone does not trigger translation. A real WhatsApp message was captured on the S23 FE after dismissing a compatibility dialog, but the flow brought Kanglish in front of WhatsApp. |
| Clipboard capture | A transparent activity waits for window focus, reads the first clipboard item's text, dispatches it, and closes. Empty or failed reads produce a message. | It is not a persistent clipboard monitor. Focus-dependent capture passed after dismissal of the Android compatibility warning; task navigation and interruption recovery remain defects or untested cases. |
| Notification action | The foreground-service notification offers “Paste copied text.” | Notification permission is denied on the tested phone. A runtime notification-permission request is not implemented. The notification action may therefore be unavailable on a fresh Android 13+ install. |
| Text selection and sharing | Handles Android `PROCESS_TEXT` and plain-text `ACTION_SEND`. Falls back to the main app when overlay permission is unavailable. | The direct PROCESS_TEXT receiver passed on device. Actual source-app menu discovery and ACTION_SEND through a share sheet remain untested. |
| Experimental hold detection | Watches deliberate long-click/selection events in WhatsApp, WhatsApp Business, and Telegram while the bubble is running; filters common UI labels and timestamps. | Requires accessibility access. Uses node-tree heuristics, accepts only 2–500 characters, and can still identify the wrong text or miss a message. Ordinary taps and arbitrary apps are excluded. |
| Corrections | Stores manually entered feedback locally; a cloud suggestion can be accepted with “Save meaning.” | Manual feedback records and learned glossary entries are different stores. A manual “Wrong Meaning?” correction does not automatically update the glossary. |

**The actual translation pipeline** has two local stages followed, in selected UI flows, by an optional external review:

1. Validate that the input is nonempty and at most 4,000 characters as counted by the app.
2. Look for a whole-input glossary match, ignoring case and normalizing whitespace. If found, return its stored meaning without calling the model.
3. Otherwise collect glossary hints, ensure a model is loaded, construct a compact Qwen-style ChatML prompt, and run native inference.
4. Return cleaned output or an explicit error. Without a model, an unmatched sentence produces a request to load one; partial word substitution is not presented as a complete sentence translation.
5. If cloud review is enabled, Chats and the floating overlay can send the original message and generated translation to the configured reviewer after local translation.

The bundled glossary currently contains **489 entries with 489 unique case-insensitive source terms**. This is an inventory count, not proof that every meaning has been reviewed or is correct. Fuzzy spelling matching and repeated-letter normalization supply model hints; they do not constitute a full Kannada morphology engine. The older token-replacement routine remains in the source, but the main translation service does not use it as its sentence fallback.

For imported chats, the prompt includes at most three preceding messages, each shortened to 160 characters, and at most eight glossary hints. It does not include sender identities in those context lines. The quick input and overlay call the translator without preceding chat history. Native KV memory is cleared between requests, so conversation context is supplied as prompt text rather than retained as a continuing model conversation.

The prompt requests preservation of meaning, names, negation, slang, and profanity. It escapes ChatML delimiters in supplied text. The app does not add a profanity censor or intentionally reject text for being vulgar. These are implementation choices, not guarantees that the model will translate faithfully, never refuse, or resist every instruction embedded in a message.

**The model runtime** uses one shared native model/context with serialized access across the app and overlay. Its current settings are:

| Setting | Current value |
|---|---|
| Intended model | Kanglish Qwen2.5 0.5B |
| Recommended quantization | Q4_K_M |
| Context window | 1,024 tokens |
| Prefill batch size | 512 tokens |
| Maximum generated output | 192 tokens |
| CPU threads | Selected between 4 and 6 by the native code |
| Sampling | Temperature 0.1; seed 42 |
| JNI text transport | UTF-8 byte arrays |
| KleidiAI | OFF in the inspected CMake cache |
| OpenMP | OFF in the inspected CMake cache |

The 4,000-character input check is not a promise that a message will fit: instructions, glossary hints, history, and the reserved output budget all consume the 1,024-token window. Oversized prompts and output-limit exhaustion return errors. This is principally a short-message runtime today; arbitrary long paragraphs and voice notes are not supported end to end.

Model import copies a candidate into internal storage, checks its GGUF header, tries to load it, and replaces the saved file only after success. Failure preserves the previous saved file and attempts to restore a previously loaded model. Model load/unload operations run away from the UI thread. The saved model can auto-load from either the app or overlay after a new process starts. Explicit unload disables automatic loading until a model is imported again; there is no separate “reload saved model” control.

The “0.5B” label is a recommendation, not an enforced architecture, parameter-count, or quantization check. The file picker accepts any file, and a loadable non-Qwen GGUF may still receive the Qwen-specific prompt format. Compatibility metadata needs stronger validation before the app can safely advertise general model swapping.

Newer quick/overlay requests cancel older coroutines, preventing stale UI results. An already-running native decode is not interrupted immediately; it finishes before another native request can use the engine.

**Learning currently means local dictionary updates.** Accepted cloud suggestions are written to `learned_glossary.json` and become available to the shared glossary in the app and overlay. Feedback is written separately to `feedback_nuance.json`. These are JSON files, not a Room/SQLite database. Saving a meaning does not change neural weights, train a LoRA adapter, or demonstrate generalization to different sentences. There is no built-in glossary pack import/export, synchronization, or editor for managing learned entries. Clearing feedback does not clear learned meanings.

**Privacy defaults have improved, with remaining gaps.** Cloud review defaults to off, including migration away from the earlier default-enabled preference. Bundled API credentials have been removed. Cleartext HTTP is disabled, and the manifest sets `allowBackup=false`. No analytics or telemetry SDK/call was identified in the reviewed application source and production dependency list; this was not a packet-capture audit or a complete audit of all transitive native code.

When a user enables cloud review and supplies a key, original text and local translations from Chats and the bubble leave the device over HTTPS. Gemini is attempted first, with Groq as a fallback. This is an explicitly network-enabled mode, so “100% offline” only describes the local translation path with cloud review off and a model already available. Quick translations on the Translate tab do not invoke the reviewer.

Provider keys are stored in ordinary private SharedPreferences. Masked input fields hide them on screen but do not provide app-level encryption or Android Keystore protection. Feedback and learned meanings likewise have no app-level encryption. Android sandboxing and device encryption are separate protections. Android 12+ data-extraction rules are not explicitly configured; lint flags this. Previously bundled credentials should be rotated if they were live.

The reviewer uses hard-coded provider/model identifiers. Availability, API-key validity, quotas, and reviewer accuracy were not tested. Network and parsing failures are generally converted to an unsuccessful result without a useful UI explanation. “The reviewer agrees” is an AI assessment, not a verified accuracy certificate.

**Evidence available today:**

| Check | Observed evidence | What it establishes |
|---|---|---|
| Build | The current debug ARM64 APK exists and matches the previous successful build. | Kotlin/resources/native code can be packaged together. |
| Automated tests | 20 passing tests; zero failures/errors in the saved reports. | Specified parser, clipboard-dispatch, navigation, privacy-default, glossary, prompt, and storage behaviors work in the test environment. |
| Clipboard tests | Include API 28 and API 35 Robolectric configurations. | The app waits for its focus callback and dispatches once; these tests do not reproduce Android's full device clipboard restrictions. |
| Lint | Zero errors; 163 warnings. | Static checks pass their error threshold. Warnings remain, including hard-coded text, small labels, dependency versions, accessibility, and backup configuration. |
| UI | Simulated renders and real S23 FE screens were inspected. | Main navigation is readable; chat cards and the overlay remain bulky. Rotation, large fonts, and other devices remain untested. |
| Device verification | Installed and tested on the S23 FE over wireless ADB; see DEVICE_TEST_REPORT.md. | Native inference and selected UI flows work, with observed compatibility/navigation defects. No controlled throughput, battery, thermal, or peak-memory benchmark was run. |
| Translation evaluation | `data/test.csv` has 3 rows; `data/benchmark_test_v1_draft.csv` has 100 rows, all marked unreviewed. | These files do not establish current-model accuracy. The 20 software tests are not 20 linguistic accuracy tests. |

Existing 0.5B merged-model and LoRA artifact directories are present in the workspace. Their presence does not establish training quality or mobile compatibility. No `.gguf` file was found under the repository's `models` directory, and none is packaged in the APK. Device testing confirmed the existing approximately 506 MiB Q8_0 GGUF in the app's internal storage.

**Remaining implementation findings, in priority order:**

1. **High — Fix the observed device integration defects.** Rebuild the native library with 16 KB-compatible alignment, then correct the clipboard activity task behavior so translation stays over WhatsApp. Repeat device acceptance for clipboard edge cases, actual selection/share menus, permission changes, and restart. A successful capture after dismissing the warning is not universal reliability.
2. **High — Translation quality has observed omissions and no broad benchmark.** The two owner-authored neural examples lost tomorrow/today. Establish an owner-reviewed held-out benchmark for the current 0.5B GGUF, including time, negation, pronouns, code mixing, slang, and spelling variants. Compare deployed quantizations before and after further tuning.
3. **Medium — Imported-chat state is transient.** The message list and translation results live in the Activity, without a ViewModel, saved-state implementation, or persistent chat store. Activity recreation/process death can lose the imported session and results. Saved feedback, learned meanings, and the model are separate persistent files.
4. **Medium — Notification setup is incomplete.** Add a clear runtime notification-permission flow so Android 13+ users can reach the promised notification paste action.
5. **Medium — Corrections do not consistently teach.** Manual feedback is logged but is not promoted to the glossary. There is no user-facing management of learned entries. JSON persistence uses whole-file, non-atomic writes; feedback synchronization is per repository instance, while app and overlay create separate instances. Concurrent writes or interrupted writes are risks. Glossary write errors are caught without informing the user that persistence failed.
6. **Medium — Model and input handling need clearer boundaries.** Validate compatible model metadata, expose reload of the saved model, communicate effective token limits, and handle very large chat imports without loading the whole export at once.
7. **Medium — Cloud mode needs stronger handling.** Add protected key storage, actionable network errors, current provider-model validation, and request limits for batch review. Review tasks can accumulate across many imported messages without a dedicated concurrency/rate limit.
8. **Release prerequisite — FOSS packaging is unfinished.** No project-level LICENSE/COPYING/NOTICE file was found at the repository root. The Gradle wrapper currently points to a ZIP under this machine's absolute path. The working tree reports the project files as untracked. Licensing/provenance, a portable checkout/build path, versioning, and release signing need attention before a public release claim.

**Roadmap features that are not implemented in the Android app** include voice-note transcription/translation, Whisper or Moonshine integration, OCR-based screen translation, community glossary pack import/export or synchronization, dynamic LoRA loading/adaptation, and on-device training. Broad dialect coverage is not established by a reviewed benchmark. A larger 1.5B/3B model is not required to address the current application defects; the agreed development focus remains 0.5B.

**Claims the available evidence does not support** are zero latency, zero battery drain, guaranteed accuracy, guaranteed refusal-free translation, fixed RAM usage, a measured token-per-second rate on the S23 FE, universal text-selection support, and KleidiAI acceleration in the current build. The defensible description today is: “An Android prototype for local Kanglish-to-English translation using a compact GGUF model and a local glossary, with copy-and-tap access, imported-chat support, and optional cloud review.”

The next milestone should fix 16 KB compatibility and WhatsApp task navigation while keeping the 0.5B model focus, followed by a reviewed quality baseline. Measure cold load, time to first token, total response time, peak memory, and repeated-use thermals on the phone, alongside the actual translation errors. Those results should guide the next fine-tuning run.

Evidence references, relative to `mobile/android`: `app/src/main/AndroidManifest.xml`; `app/build.gradle.kts`; `app/src/main/java/org/kanglish/app/ui/MainActivity.kt`; `app/src/main/java/org/kanglish/app/inference/TranslationService.kt`, `TranslationPrompt.kt`, and `TeacherService.kt`; `app/src/main/java/org/kanglish/app/data/GlossaryManager.kt`, `FeedbackRepository.kt`, and `WhatsAppParser.kt`; the overlay activity/service files; `app/src/main/cpp/kanglish_inference.cpp`; `app/src/main/assets/glossary.json`; `app/build/test-results/testDebugUnitTest/`; `app/build/reports/lint-results-debug.xml`; and the current `.cxx` CMake cache. Evaluation-file and root-license checks refer to the repository root.

Audited APK SHA-256: `c28247b371d33b3256e1ad5033b5a86616c93cde1d4951a9e1891057b87428d8`.
