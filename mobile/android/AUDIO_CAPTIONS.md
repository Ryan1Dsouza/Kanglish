# Live Kannada captions

The Translate screen now has **Live Kannada captions**. It recognizes spoken Kannada and displays Kannada written in English letters. It does not translate the speech into English meaning. A GGUF model or API key is not required for this feature.

1. Install the new debug APK, then open **Kanglish → Translate → Live Kannada captions**.
2. Tap **Start** and allow the microphone permission.
3. Say “ನಾನು ಬರಲ್ಲ ಇವತ್ತು” and pause. A correctly recognized phrase displays `naanu baralla ivattu`.
4. Speak another phrase. Partial captions update in place; finalized phrases accumulate below one another.
5. Tap **Stop** to finish the current phrase. **Copy captions** copies finalized text. **Clear** stops listening and removes the transcript.

The default uses Android's on-device speech recognizer. If the screen reports that on-device recognition or Kannada is unavailable, check the speech provider's language downloads, or enable **Allow online recognition** and tap Start again. That switch allows the phone's configured speech provider to process audio online. It does not enable the app's teacher API. Some phones may have no Kannada-capable speech provider.

The first implementation uses `android.speech.SpeechRecognizer` with locale `kn-IN` and partial results, followed by a local, deterministic Kannada-to-Latin Romanizer. It introduces no library dependency, paid API, bundled speech model, or training. The exact speech model is controlled by the installed Android provider and is not exposed by this API. The connected S23 FE reported Google's `GoogleTTSRecognitionService` as its configured system provider; actual Kannada recognition support remains to be checked by speaking on the phone.

Listening starts only when requested. Online recognition is off whenever the screen is opened. Kanglish keeps captions in memory and writes no audio files or transcripts. Leaving the screen stops the recognizer and cancels scheduled restarts; closing/recreating the screen clears the transcript. Copying explicitly places finalized captions on the system clipboard. Online provider processing follows that provider's policies.

Partial results and pause detection depend on the provider. Recognition restarts between phrases, which can create brief gaps; this is not a measured gap-free streaming engine. Three consecutive empty/no-speech turns stop the session. Speech recognition can mishear words, and the basic phonetic Romanizer does not resolve alternate spellings, word meanings, dialects, or every rare Kannada character. Unsupported Kannada characters appear as `[?]`. It preserves Latin text and converts Kannada digits. No speech accuracy or latency claim has been established yet.

Validation: 51 Android unit/Robolectric tests passed, including Kannada vowels/conjuncts, mixed English and numbers, negation/time-word spelling, partial/final replacement, bounded transcript memory, offline-only failure, late-callback rejection, stop-with-final-result behavior, copy, and screen lifecycle. The audio UI was rendered and visually inspected at 360 × 800. These tests use simulated recognition callbacks; they do not establish real microphone or provider accuracy.

From `mobile/android`, reproduce the build and tests with:

```powershell
./gradlew.bat :app:testDebugUnitTest :app:assembleDebug --console=plain
```

The training-data review remains at Gate A. This feature does not change the translation prompt, training candidates, model weights, or quantization.
