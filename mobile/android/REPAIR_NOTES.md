# Android repair pass — 19 October 2026

This pass targets the existing Qwen2.5 0.5B app. No model training, model downloads, or owner-maintained evaluation/glossary data changes were performed.

## Try the build

APK: `app/build/outputs/apk/debug/app-debug.apk` (ARM64, Android 9 or newer).

1. Install the APK over the existing app if its signing key matches. A signing mismatch needs to be resolved without deleting app data; uninstalling would remove imported models and saved corrections.
2. Open **Settings → Choose 0.5B GGUF** and select your Kanglish Qwen2.5 0.5B model. GGUF weights are not bundled with the APK.
3. Enable **WhatsApp floating bubble** and grant **Display over other apps** when Android asks.
4. In WhatsApp, copy a text message, then tap the **K** bubble. Copying alone does not trigger translation. Accessibility access is not needed for this flow.
5. Alternatively, open Kanglish, tap **Paste**, then **Translate**. Android text selection and plain-text sharing also route into Kanglish where the source app supports those actions.

The foreground notification has a **Paste copied text** action as another entry point. Its availability depends on notification permission. Cloud review is off by default and remains separate from the native translation engine.

## Changes

- **Clipboard:** Removed the read from `onResume()`. The transparent activity now reads only after its window receives focus. Previously the early read could return null and permanently consume the attempt. Removed background clipboard polling/listening.
- **Navigation:** Translate is the landing page; chat imports have their own tab; model, overlay, optional cloud review, and saved corrections are in Settings. Removed the duplicate test input and diagnostic glossary hints from the primary UI. Fixed dark-theme contrast and system-bar/keyboard insets.
- **Entry points:** Text selection and sharing fall back to the app when overlay permission is absent. Overlay text is scrollable; controls have larger touch targets; a newer request cancels the older coroutine and prevents stale results from replacing it. An in-flight native decode still finishes before another native request can run.
- **Model lifecycle:** Serialized native operations across activity and service, moved unload off the main thread, made model status reads nonblocking, and auto-load the saved model from either entry point. Imports stage and validate a candidate before replacing the saved file; failed imports preserve the previous file. Explicit unload disables automatic loading until a model is imported again.
- **0.5B translation:** Exact saved glossary phrases bypass inference. The prompt is shorter, keeps bounded conversation context, and escapes ChatML delimiters in source text. Unknown full sentences require a model instead of presenting partial word substitution as a complete translation. Legitimate translations beginning with “I cannot” are no longer discarded. These prompt changes have not been evaluated for linguistic accuracy.
- **Native reliability:** JNI text uses UTF-8 byte arrays so emoji and non-ASCII text do not pass through modified UTF-8. Prompt prefill is batched; context and output limits return explicit errors; multi-line output is preserved. Runtime context remains 1,024 tokens, with up to 192 output tokens.
- **Privacy:** Removed bundled API credentials; introduced a fresh, disabled cloud opt-in setting even for upgrades from the previous default-enabled setting; masked key inputs; disabled Android backup and cleartext HTTP in the manifest. Existing user-entered provider keys are retained. Rotate previously bundled credentials if they were live.
- **Experimental accessibility:** Restricted capture to deliberate holds/selections in WhatsApp/WhatsApp Business/Telegram while the bubble is running. Ordinary taps and unrelated apps no longer trigger it.

## Verification

From `mobile/android`:

```powershell
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug --console=plain
```

- Debug ARM64 APK builds, including the C++/JNI library.
- 20 unit/Robolectric tests pass: clipboard lifecycle and dispatch on API 28 and 35, permission fallback, sharing, paste fidelity, navigation, privacy defaults, failed import preservation, glossary routing/sharing, prompt handling, and the existing parser cases.
- Android lint completes with no errors. Nonblocking warnings remain, including resource internationalization, dependency versions, and legacy UI code.
- Rendered previews of Translate, Chats, Settings, and the overlay were inspected under `app/build/outputs/ui-preview/`. These are Robolectric renders, not device screenshots.

## Required device checks

No Android device was attached during this pass. Android's real clipboard permission enforcement, OEM background-activity behavior, WhatsApp integration, and native inference speed/quality remain unverified on the S23 FE.

Check: copy → bubble with the model loaded; empty clipboard; a multiline message with emoji; repeated quick requests; selection without overlay permission; failed GGUF import; unload/reload; process restart; rotation; and airplane mode with cloud review off. Experimental hold detection is not a guaranteed replacement for copy → bubble.

The next model-quality milestone should stay on 0.5B: evaluate the current GGUF against an owner-reviewed held-out set, group errors by negation, pronouns, code mixing and slang, then fine-tune and compare the quantized candidate against that baseline. Larger models are not required for that work.
