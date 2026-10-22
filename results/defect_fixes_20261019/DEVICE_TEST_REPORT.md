Kanglish FOSS - six-defect repair update

19 October 2026. This update covers only the six requested defects. No training or weight changes were performed. The final source and APK are in the isolated checkout `C:/Users/ryan1/kanglish-defect-fixes/mobile/android`. Two other agents were editing the shared workspace; their concurrent cloud UI changes broke the shared task-3 build. The isolated checkout starts from the verified task-2 snapshot and excludes those unrelated additions. It must be integrated with their work before treating the shared tree as the final build.

**Implementation and verification**

| Task | What changed | Verification |
|---|---|---|
| 1. 16 KB alignment | Enabled `ANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=ON` with NDK 27.2.12479018. No fallback linker flag was needed. | All three LOAD segments show `0x4000` in `llvm-readelf -lW`. `zipalign -c -P 16 -v 4` passes on the final APK. The stage-1 build opened on the S23 FE without the compatibility dialog. |
| 2. Clipboard task isolation | The clipboard activity uses a translucent theme, empty task affinity, no preview/animation, excludeFromRecents and noHistory. Bubble and notification use the same NEW_TASK/NO_ANIMATION launch intent. It reads only after focus and finishes in `finally`. Logs describe the path and length without logging clipboard contents. | On S23 FE, the real WhatsApp conversation remained the focused app in all three post-capture samples; the capture used temporary task 4091, separate from MainActivity's task 4090, then finished. Its result appeared in the overlay over WhatsApp. No compatibility dialog appeared. Task metadata and one-time dispatch tests pass on APIs 28 and 35. |
| 3. Time/negation hints | Input-word matches for naale, ivattu, ninne, alla, illa and beda take priority within the eight-hint budget. The system prompt explicitly preserves time references. Debug logging records the final hints and full prompt for exactly the two specified sentences; release/arbitrary private-message prompt logging is excluded. | Unit tests confirm both requested time hints, all six hints under budget pressure, duplicate precedence, case/punctuation handling and exclusion of substrings. Actual post-fix neural outputs are **not measured** because the user deferred further device tests. |
| 4. Notifications | Enabling the bubble explains the notification paste shortcut and requests POST_NOTIFICATIONS on Android 13+. Denial, cancellation and Not now still start the bubble; the UI reports notifications off. The app does not repeatedly prompt after the explanation. | Grant, denial, Not now and repeat behavior pass in Robolectric on APIs 33 and 35; the older-Android path passes on API 28. Physical permission-dialog/notification-action checks remain deferred. |
| 5. Glossary review | Listed every bundled entry whose meaning contains the literal separator ` / `. No entry was modified. | **162 of 489 entries** are listed in `GLOSSARY_ALTERNATIVES_REVIEW.md`, with asset index, Kanglish and the unchanged meaning. Device-local learned entries were not inspected after device access was deferred. |
| 6. Compact overlay | Reduced padding/margins, put copy/open/clear on one 48dp action row, replaced the fixed 280dp content area with wrap-content scrolling capped at 200dp, and clamp placement using measured panel height. | Rendered tests show a short panel at **344 x 259dp** and long content at **344 x 360dp** under the mdpi test configuration. Short content does not scroll; long content scrolls within the cap. Physical positioning, dragging and large-font checks remain deferred. |

The activity-based clipboard approach worked on this S23 FE, so no focusable-overlay alternative was introduced. It still briefly obtains input focus to satisfy Android clipboard rules; the source conversation remains visually underneath and MainActivity is not raised. This is device evidence for the tested Android 16 setup, not a guarantee across every OEM/version.

**Time-word results**

| Input | Before this repair, observed on phone | After this repair |
|---|---|---|
| `naale college ge barthira?` | `Are you coming to college?` - omitted tomorrow | Pending device re-test; final prompt includes `naale = tomorrow`. |
| `yenu guru ivattu plan?` | `What is the plan bro?` - omitted today | Pending device re-test; final prompt includes `ivattu = today`. |

No output was post-edited, no translation accuracy was inferred from hint-presence tests, and no retraining was performed. On the next controlled device run, inspect the `KanglishPrompt` log tag while translating those exact strings, and compare the resulting English with the owner's existing references.

**Build and diff record**

All six tasks have a successful debug build and a freshly executed unit-test suite. Passing test invocation counts were **27, 29, 32, 39, 39, 41**, respectively (SDK-parameterized cases count separately). Final lint has **0 errors / 155 warnings**. The initial task-4 test failure was fixed by dispatching the paused test looper after dialog clicks; the application permission flow then passed. The first task-3 build failure came from concurrent shared-tree changes, and the isolated build passed.

Diff summaries (application paths are relative to mobile/android):

- Task 1: one file, +1/-0; native-build argument.
- Task 2: five files, +51/-11; manifest/theme/capture/launch handling and task tests.
- Task 3: four files, +55/-4; hint selection, scoped diagnostics and tests.
- Task 4: three files, +136/-8; notification flow, strings and tests.
- Task 5: one report, +170/-0; glossary unchanged.
- Task 6: four files, +104/-9; bounded scroll view, layout, placement and tests.

Detailed task patches, archived test XML, build logs, alignment reports and captured device evidence are under `C:/Users/ryan1/kanglish-foss/results/defect_fixes_20261019`. The cumulative patch is based on the original repair baseline; do not apply it blindly over other agents' concurrent changes. The final APK has **not** been installed after the device-test deferral.

**Remaining device re-tests:** install the integrated final APK; recheck absence of the compatibility dialog; repeat WhatsApp copy-to-bubble and notification paste with grant/denial; verify both time words in generated output and collect prompt logs; inspect compact-panel placement, long-message scrolling, dragging and font scaling. The user asked us to defer these checks because the other agents still need the phone. No further ADB actions were taken after that instruction.

**No-cloud constraint incident:** During the stage-2 WhatsApp test, the installed app displayed a cloud-review result. At least one request containing the selected message and local translation therefore went to its configured reviewer, contrary to the requested constraint. We stopped the app, confirmed the persisted cloud-review flag was true, and changed it to false. This was disclosed immediately. We did not make additional device translations after discovering it. The phone/workspace was concurrently in use by other agents; subsequent testing was deferred. Do not describe this entire session as having made zero cloud calls. No cloud-provider code was added by this patch.

Final APK SHA-256: `141d0a6c841beea79d803a27eebc1244e8cf8c7f6053144b3a6bfa6880721f76`.

The historical device report below predates these fixes and is retained as the baseline.

---

Kanglish FOSS — S23 FE device test report

19 October 2026. Tested through wireless ADB on the owner's Samsung SM-S711B (Galaxy S23 FE), Android 16, 1080 × 2340 display. This is a bounded functional smoke test, not a release certification or an accuracy benchmark.

**Result:** The repaired app runs native 0.5B inference, translates exact glossary phrases, loads the sample chat, and copies/pastes text. A real message selected in the owner's nominated WhatsApp group reached the floating translator. That workflow still has two substantial problems: an Android native-library compatibility warning interrupted it, and the clipboard activity brought Kanglish's main screen in front of WhatsApp. The application is usable for further testing, but the floating experience is not ready to call reliable.

The repaired debug APK was installed over the existing app with `adb install -r`. Existing app data and the saved model were retained. No application-source changes or model training were performed during this device-test stage. No WhatsApp messages were sent, deleted, reacted to, or forwarded. No cloud-review requests were intentionally invoked; cloud review was off. This was not a network-capture audit.

**Observed functional behavior**

| Check | Result and limits |
|---|---|
| App launch and native model | Passed. The native library loaded and the interface displayed “On-device model ready.” |
| Typed neural translation | Returned results for both owner-authored evaluation sentences. Both lost a time reference; see below. |
| Exact glossary phrase | `sakkath aagide` returned `It's awesome / great.` through the deterministic path. |
| In-app clipboard | Copy translation → Clear → Paste preserved the copied output. |
| Empty input | Displayed “Enter or paste a message.” |
| Floating service | Started, displayed its bubble, minimized, copied its output, and closed successfully. Dragging and rotation were not exercised. |
| WhatsApp copy → bubble | Captured the selected message exactly and produced an English result after the compatibility dialog was dismissed. Copying that result back into Kanglish also worked. Its linguistic correctness was not graded because no owner reference was supplied. |
| Sample chat | Loaded the bundled sample as message cards. Translating the first row returned `Hey, what's the plan?` for `Hey guru scene enu ivattu?`. Clearing the sample returned to the empty chat screen. A real exported-file import was not tested. |
| Android `PROCESS_TEXT` receiver | A direct ADB intent carrying `sakkath aagide` produced the expected glossary output. This validates the receiver, not its discovery in WhatsApp's or another app's selection menu. |
| Runtime stability | No fatal-exception, native-fatal-signal, or ANR markers were found in the inspected current-process log; its crash-buffer query was empty. This is limited evidence, not proof against all crashes. |

**Translation evidence from the owner's existing test file**

| Input | Existing owner reference | Actual phone output |
|---|---|---|
| `naale college ge barthira?` | `Are you coming to college tomorrow?` | `Are you coming to college?` |
| `yenu guru ivattu plan?` | `What's the plan today bro?` | `What is the plan bro?` |
| `sakkath aagide` | `It's awesome` | `It's awesome / great.` |

The first two examples used neural inference and omitted “tomorrow” and “today.” The last used the glossary, so it is not evidence of neural-model accuracy. These three examples do not support an overall accuracy percentage. The private WhatsApp example was inspected locally and its overlay result captured in a cropped screenshot; this report does not reproduce the group's messages or identify its participants. No expected translations or evaluation rows were added or changed.

**Issues to address first**

1. **High — Native binary lacks 16 KB page compatibility.** Android showed “This app isn't 16 KB-compatible. ELF alignment check failed” and named `lib/arm64-v8a/libkanglish_llama.so`. Inspection of the APK confirmed all three ELF load segments have 4,096-byte alignment. This phone currently reports 4,096-byte pages, so successful execution here does not establish support for 16 KB devices. The warning held focus while the clipboard trampoline waited, making the bubble appear unresponsive; it appeared again during the direct text-selection test. Rebuild/package the native library for 16 KB compatibility and verify the resulting APK. Suppressing the warning is not a fix.
2. **High — Clipboard translation interrupts WhatsApp navigation.** Starting the transparent clipboard activity brought the existing Kanglish task forward, with MainActivity underneath the overlay. After the clipboard capture, the experience did not remain over the originating conversation. Review task affinity and activity/task handling, then repeat copy → bubble → dismiss from WhatsApp. Clipboard access itself succeeded once focus became available.
3. **High — Meaning preservation needs a reviewed 0.5B baseline.** The observed time-word omissions change the meaning. Keep the agreed 0.5B focus; build a broader owner-reviewed evaluation covering time, negation, pronouns, slang, spelling and language/dialect coverage before further tuning. Keep functional test passes separate from language-quality scores.
4. **Medium — Chat UI remains bulky.** The Translate/Chats/Settings navigation is readable on this device, but only about two complete message cards fit on screen. Repeated original/translation labels, large empty translation areas, and three per-message actions consume substantial space. The bubble also covers part of the chat content while Kanglish is open. Compact rows and secondary correction actions would reduce congestion. The floating panel similarly reserves a large area for very short results.
5. **Medium — Notification permission is denied.** The bubble worked despite this, but the notification paste action was not available for validation. The source audit already identified the missing Android 13+ runtime notification-permission flow.

**The model actually on the phone** is `Kanglish_Qwen_0.5B_V3_Merged`, Qwen2 architecture, GGUF v3, metadata size label **494M**, and file type **7 / Q8_0**. The saved file is about **506 MiB**. It is not Q4_K_M, despite the quantization recommended in Settings. Metadata was inspected from the file header; it is not an independent parameter recount or a weights-quality audit.

The native runtime reported six threads and a 1,024-token context. One warm memory snapshot showed **699,165 KiB PSS (about 683 MiB)**, 745,734 KiB RSS, and 52,116 KiB swap PSS. These are different accounting measures; do not add them together or treat the snapshot as peak usage. One load took about 31.6 seconds while the phone was locked/dozing; that is not a controlled cold-load benchmark. UI polling observed neural results at roughly 5.61 and 3.74 seconds, including ADB/UIAutomator overhead. No token-throughput, battery-drain, thermal, or zero-latency claim is supported.

**Still untested:** `ACTION_SEND` through an actual share sheet, source-app selection-menu availability, accessibility hold detection, empty/non-text/expired clipboard, permission revocation, model import failure and reload recovery, large exports, long-context behavior, concurrency stress, process-death recovery, rotation, large fonts, cloud review, and sustained thermal/battery behavior. Accessibility remained off. The temporary sample and typed test input were cleared and the bubble was stopped; the saved model was retained. The first interrupted translation attempt and the attempt over Android App Info were inconclusive and are excluded from the results above.

**Evidence:** [device artifacts](../../results/device_smoke_20261019), including `03_neural_translation.json`, `04_neural_translation.json`, `05_glossary_translation.json`, `06_copy_paste.json`, `10_android_16kb_warning.png`, `10_whatsapp_overlay.png`, `10_whatsapp_clipboard.json`, `11_sample_translated.png`, `12_process_text_result.png`, `elf_alignment.json`, `model_metadata.json`, `memory_after_translation.txt`, and `runtime_final.log`. Captures of the WhatsApp translation are cropped to the Kanglish panel. Artifact numbers are capture identifiers, not counts of successful tests.

Tested APK SHA-256: `c28247b371d33b3256e1ad5033b5a86616c93cde1d4951a9e1891057b87428d8`.
