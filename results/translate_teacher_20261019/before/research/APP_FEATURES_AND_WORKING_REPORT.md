**Kanglish Translator: app features, working, technology, and current status**

Prepared on 19 October 2026 from the Android source code, dataset artifacts, and saved quality/build results in `kanglish-foss`.

Kanglish Translator is an Android app that converts Kannada written in English/Latin letters into English meaning. Its intended use is understanding informal messages, including mixed Kannada-English sentences, slang, and profanity. The current app is development version **0.1.0**, with package name `org.kanglish.app`. It supports Android 9 and later, and the current native build targets 64-bit ARM phones (`arm64-v8a`).

The main translation runs on the phone using an imported language model, assisted by a bundled glossary. Optional cloud review can check results from Chats and the floating bubble. The existing model has demonstrated hallucinations, so the app's translation accuracy remains a development issue. Live audio captions are a proposed feature and are not included in this build.

The implemented user features are listed below. The main navigation has three tabs: **Translate**, **Chats**, and **Settings**. **Saved corrections** opens from Settings.

| Feature | What the user can do | How it currently works |
| --- | --- | --- |
| Quick text translation | Type or paste a Kanglish message and get English meaning. | The Translate tab runs the local glossary/model translation path. It currently does not request cloud-teacher review. |
| Clipboard input | Paste copied text into the translator. | An explicit Paste button reads the clipboard. Clear removes the input and result. |
| Copy a quick result | Copy the generated English text for use elsewhere. | The result card includes a Copy translation button and selectable text. |
| WhatsApp chat import | Open a WhatsApp `.txt` export. | Android's document picker reads the selected text file and the parser builds a message list. |
| Bundled sample chat | Try the chat interface without supplying an export. | Try sample loads a text asset bundled with the APK. |
| Conversation display | Read messages with their sender, timestamp, original text, and translation. | A RecyclerView displays one message card per parsed message, with translation status. |
| Individual translation | Translate, retry, or retranslate a particular message. | The selected message uses preceding messages as limited context. |
| Translate all | Translate the imported conversation in order. | Batch processing visits messages sequentially and skips those already marked translated. |
| Copy a chat message | Copy a translation, or the original if translation has not completed. | Each message card has a Copy action. |
| Clear a chat | Remove the current imported conversation from the screen. | The app cancels associated UI jobs and clears the in-memory message list. |
| Report a wrong meaning | Enter a correction or explain a missed nuance. | The message is flagged and the original, generated answer, correction, sender, and timestamp are saved locally. |
| View saved corrections | Inspect and clear the stored feedback log. | Settings opens a dedicated Saved corrections screen. This log is separate from the learned glossary. |
| Import an offline model | Choose a GGUF model from device storage. | The app copies the file into private storage, checks its GGUF signature, and attempts native loading before accepting it. |
| Model status and unloading | See whether the model is ready and release it from memory. | Settings shows the current engine state. A successfully imported model can reload on startup; explicitly unloading disables that automatic reload. |
| Glossary-assisted translation | Get immediate answers for known complete phrases and useful hints for other messages. | The bundled glossary and locally saved meanings are checked before model inference. |
| Optional cloud review | Enable a teacher model and save provider API keys. | Cloud review settings contain an opt-in switch and Gemini/Groq key fields. Review is available for Chats and the bubble. |
| Teacher verdicts | See agreement, an alternative translation, or uncertainty. | Strict response parsing requires an explicit `match`, `mismatch`, or `uncertain` verdict. |
| Save a teacher meaning | Keep a suggested meaning for future local lookups. | A valid mismatch suggestion can be added to the local glossary. Uncertain results do not expose this action. |
| Floating translation bubble | Translate copied text while another app remains in view. | Enable the bubble, copy a message, and tap the bubble or its Paste copied text action. An overlay shows the original and English result. |
| Floating-panel controls | Move, minimize, clear, close, copy, or open the main app. | Both the bubble and expanded panel can be dragged. The panel also supports optional cloud review and saving a suggested meaning. |
| Notification shortcut | Reach clipboard translation while the bubble service runs. | A foreground-service notification includes a Paste copied text action and a shortcut to the main app. |
| Android text selection and sharing | Send selected/shared text to Kanglish from compatible apps. | `ACTION_PROCESS_TEXT` and `ACTION_SEND` accept plain text. The result opens in the overlay when available, otherwise the text is passed to the main translator. |
| Experimental hold detection | Attempt translation after holding or selecting a message in supported messaging apps. | An optional accessibility service handles selection/long-click events in WhatsApp, WhatsApp Business, and Telegram while the bubble is running. |
| Progress and failure feedback | See loading, pending, translated, and failed states. | Progress indicators, retry actions, model checks, and input/context errors support recovery from operational failures. |

The chat parser recognizes common WhatsApp export headers, including bracketed timestamps, optional seconds, and AM/PM times. It preserves multiline message bodies and has basic filtering for the English encryption notice and `<Media omitted>` marker in parsed messages. Plain text without a recognized header can become individual messages. This is a text parser; unusual export formats, localized system notices, and attachments do not have comprehensive support. Pasting into the main Translate tab translates the pasted text as one input; file import is the chat-parsing workflow.

The floating bubble uses Android's overlay permission and a foreground service. Clipboard access is initiated through a small transparent activity that waits for real window focus, which accommodates Android's clipboard access restrictions. The normal copy-and-tap workflow does not require accessibility access. Hold detection is experimental, depends on the messaging app exposing useful accessibility text, and currently accepts detected text from 2 to 500 characters. It does not provide universal screen translation or OCR.

**A local translation follows these steps:**

1. The app trims the message, rejects empty input, and enforces a 4,000-character application limit.
2. It checks whether the entire message matches a bundled or learned glossary phrase. This comparison ignores case and normalizes whitespace. A match returns its stored English meaning without loading the model.
3. For other input, the app finds relevant glossary entries. Matching includes phrases, repeated-letter normalization, and limited spelling tolerance. These matches become hints for the model; they do not establish the sentence's meaning by themselves.
4. The app ensures that an imported GGUF model is loaded. Full-sentence translation outside exact glossary matches requires this model.
5. It builds a compact Qwen ChatML prompt asking for natural English while preserving meaning, names, negation, slang, and profanity. The input is presented as text to translate. Up to eight glossary hints can be included.
6. Chat translation can include the three preceding original messages, each limited to 160 characters. The quick translator and floating bubble normally translate one message without this conversation history.
7. Kotlin calls the native C++ inference library through JNI. The native engine generates a complete response, and the app removes chat delimiters and surrounding whitespace before displaying it.
8. In Chats and the bubble, an enabled cloud teacher can review the displayed student answer afterward. The original local answer remains visible alongside any teacher feedback.

The native engine is **llama.cpp**. The reference student artifact currently present in the workspace is the fine-tuned **Qwen2.5 0.5B v3** model in **GGUF Q8_0** format. Its file size is **531,067,840 bytes**, approximately 531 MB or 506 MiB. The model is imported separately; it is not bundled into the approximately 26.3 MB debug APK.

Native inference uses a 1,024-token context, up to 192 generated tokens, temperature 0.1, seed 42, and a CPU thread count selected between four and six. A shared lock coordinates model access from the activity and overlay, and the model's temporary attention cache is cleared between requests. The 4,000-character input limit is only an initial check: the prompt, glossary, chat history, and reserved output must still fit the smaller token budget. Oversized prompts, loading failures, blank responses, and generation-limit failures produce errors. The current UI receives the completed translation; it does not stream individual generated tokens.

The model picker verifies the GGUF format and successful native loading. It does not establish that every loadable model is suitable for Kanglish or for this prompt format. The Settings layout still contains a `Q4_K_M` description, while the inspected v3 artifact is `Q8_0`; that label is outdated descriptive text rather than detected model metadata.

The bundled glossary contains **489 entries**. Locally accepted teacher suggestions are appended to `learned_glossary.json` in private app storage and can override an existing meaning for the same source phrase. Exact matching can make a repeated phrase fast and consistent. It can also repeat a wrongly saved meaning. Related sentences still depend on model generalization.

The repository also contains an older token-replacement rule engine. The active production translation service uses its whole-phrase exact lookup, followed by the language model for other messages. General word-by-word replacement is not the current full-sentence fallback.

**The teacher-student design operates at two different stages.** During desktop training, a larger teacher generates text examples, and the smaller student is fine-tuned on input/answer pairs. The training scripts use supervised fine-tuning and LoRA, merge the adapter into the base model, and export/quantize the result to GGUF. This process produces model weights for later import into Android.

During app use, the local student translates first. If cloud review is enabled for the relevant workflow, the app sends the original message and the student's answer to a configured provider. The current code tries Gemini's `gemini-flash-lite-latest` endpoint first and then a Groq fallback configured as `qwen/qwen3.8-27b`. These are provider settings found in the code; live model availability and teacher accuracy were not verified in the recorded audit. The fallback is an alternative reviewer, not an independent second vote on every successful Gemini review.

The teacher is prompted to check negation, person, tense, names, numbers, slang, and unsupported additions. It can agree, propose a different translation, or say that the meaning is uncertain. The parser rejects missing or incorrectly typed fields, unusable translations, and malformed responses. An uncertain response requires a reason and an empty suggested translation. Network or response failures do not count as successful agreement. Each provider has eight-second connection and read timeout settings, so cloud review has no tight response-time guarantee.

The app's **Save meaning** action changes a local glossary entry. It does not train the student, change its weights, or teach all related grammatical forms. A manually entered wrong-meaning correction is saved to `feedback_nuance.json` and shown as feedback; that action currently does not automatically add the correction to the glossary. Clearing saved corrections clears the feedback log, not the separate learned glossary. No automatic feedback upload or in-app retraining workflow is implemented.

Teacher agreement is useful feedback, but it is not proof of a correct translation. Both models can share a mistake, and a strict JSON parser only validates the structure of a review. The local student currently has no demonstrated, calibrated mechanism that reliably abstains on unknown words.

The technologies used in the project are:

| Area | Technology | Purpose |
| --- | --- | --- |
| Android implementation | Kotlin 2.1.20, XML layouts, ViewBinding | Native application logic and UI binding. |
| UI components | AndroidX AppCompat 1.7.0, Material Components 1.12.0, ConstraintLayout 2.2.0, RecyclerView 1.3.2 | Tabs, forms, dialogs, message cards, and layouts. |
| Android support and lifecycle | Core KTX 1.15.0, Activity KTX 1.9.3, Lifecycle libraries 2.8.7 | Activity integration and lifecycle-aware operations. |
| Background work | Kotlin coroutines 1.8.1, coroutine jobs, Mutex | Move translation/network work off the UI thread and coordinate model access. |
| On-device inference | llama.cpp, C++17, JNI, GGUF | Run the imported language model locally. |
| Student model | Qwen2.5 0.5B family, project v3 fine-tune, Q8_0 artifact | Generate English translations from Kanglish. |
| Optional teacher providers | Gemini API and Groq API | Review completed local translations. |
| HTTP and JSON | `HttpURLConnection`, Android `org.json` | Send provider requests and parse responses without a separate app backend. |
| Local persistence | SharedPreferences, private JSON files, private GGUF file | Store settings, keys, feedback, learned meanings, and the imported model. |
| Android integration | Storage Access Framework, clipboard APIs, intents, WindowManager overlays, foreground and accessibility services | Import files and translate selected/copied text alongside other apps. |
| Build tooling | Gradle 8.9, Android Gradle Plugin 8.7.2, Android SDK 35 | Compile and package the Android app. |
| Native build tooling | NDK 27.2.12479018, CMake 3.22.1 | Build the ARM64 native inference library. |
| Java compatibility | Java/Kotlin JVM target 17 | Compile application bytecode for the configured Android build. |
| Desktop ML training | Python, PyTorch, Hugging Face Transformers and Datasets, PEFT LoRA, TRL SFTTrainer | Prepare and fine-tune student models. |
| Data and teacher utilities | Python standard-library audit/export scripts, existing `requests` and PyArrow utilities | Validate data, call teacher-generation APIs, and ingest source datasets. |
| Desktop inference experiments | Ollama at `localhost:11434` | Run model comparisons, diagnostic probes, and research workflows on the computer. |
| Automated tests | Python unittest, JUnit 4.13.2, Robolectric 4.14.1 | Check dataset processing and Android behavior. |

Ollama belongs to the desktop research workflow. The phone runs llama.cpp directly and does not need a desktop Ollama server for local translation. The project also contains experiments with larger Qwen2.5 models and Gemma2; those experiments are separate from the current 0.5B Android student.

The data collection includes several different kinds of sources. Counts below describe the historical processed catalogue, not the number of independently reviewed conversational training examples.

| Source | Recorded catalogue contribution | Intended role and qualification |
| --- | --- | --- |
| Alar Kannada-English dictionary | 156,620 lexical records | Word senses and definitions. Dictionary pointers and unresolved references need filtering before use as English answers. |
| BPCC daily conversation data | 8,484 conversational records | Kannada-English sentence pairs. Native-script sentences still differ from informal Latin-script chat input. |
| Aksharantar | 7,025 transliteration records in this catalogue | Kannada-script/Romanized word alignment. Its Romanized field is Kannada written in Latin letters, not an English semantic translation. |
| Slang seed collection | 11 records | Candidate informal meanings; placeholder reviewer labels did not establish real human verification. |

These contributions total **172,140 historical catalogue records**. Additional source material includes the larger Aksharantar word corpus, an English-Kannada cleaned corpus, and 1,503 IN22-Conv evaluation-only rows. Downloading or cataloguing a source does not mean all its rows trained the shipped model. Source-specific provenance, attribution, and license metadata are retained in the data workflow.

The historical v3 training file contains **6,492 rows**: 6,227 baseline rows and 265 teacher-generated pairs. The audit found 497 targets containing Kannada, including 467 dictionary-pointer targets, and a builder that selected 2,500 dictionary entries all beginning with `a`. Teacher-generated text had not been independently established as correct. The existing reviewed development/evaluation files were empty, and the old three-example owner test was too small to establish accuracy.

The repaired candidate export is stored under `data/processed/quality_v1/`. It contains **4,491 training candidates and 504 validation candidates**, for **4,995 total**. These comprise 2,500 dictionary pairs spread across 21 initial letters and 2,495 Kannada-script BPCC sentence pairs. Checks found no invalid English targets or detected input-family, answer-family, or source-group overlap between the two splits. Each retained input/answer pair was checked against its recorded source.

A separate review queue contains **2,195 rows** requiring review or exclusion, including unresolved dictionary references, untraceable legacy examples, unreviewed teacher outputs, reserved diagnostic inputs, and conflicting answers. Importer, reviewer-metadata, label-validation, and splitting safeguards have been repaired. These candidates remain unreviewed for the target conversational use case. They have **not been used to retrain the current v3 weights**, and the app's 489-entry glossary is a separate asset from this candidate export.

The repository supports further data work through source importers, metadata validation, deduplication, glossary experiments, teacher generation, training/quantization scripts, benchmarking, and representation-comparison workflows. Audit outputs preserve model/source hashes and diagnostic predictions. A planned human-review workflow provides for 20 development and 80 evaluation messages; it still needs genuine reviewed content before it can support a reliable accuracy claim.

**The observed quality results show why arbitrary input remains risky.** A saved diagnostic run tested the actual v3 GGUF through desktop Ollama using the Android prompt and glossary behavior. It contained 29 cases: 28 model calls and one exact glossary lookup. It was not a representative, human-scored accuracy benchmark.

| Input | Observed output | What the result shows |
| --- | --- | --- |
| `marmarisu` | `milk chocolate` | An unrelated meaning; the recorded Alar reference concerns sounds made by shaking or walking on leaves. |
| `naanu baralla ivattu` | `I will come to your house` | The output reverses the polarity and adds a destination relative to the existing unreviewed draft reference. |
| `naale college ge barthira?` | `Are you coming to college?` | It omits the time reference present in the owner's expected translation. |
| `zqxvpl` | `hey` | It assigns a definite meaning to an artificial unknown control. |

All four artificial negative controls received definite translations. Successful completion of an inference request therefore cannot be treated as a correct answer. There is no justified overall accuracy percentage for random Kannada/Kanglish words, and the teacher has not been separately benchmarked for semantic correctness. The recent repairs improve data handling and review behavior; they do not establish improved translation accuracy for unchanged weights.

The latest recorded validation from 19 October 2026 reports **48 passing Python tests**, **27 passing Android tests**, and a successful offline debug APK build. The existing APK and model were checked against their recorded hashes while preparing this report. These are software/build checks, not proof of linguistic accuracy. The repaired build has not been installed and tested on a physical phone as part of that validation, and live cloud-teacher behavior was not exercised.

The diagnostic desktop run measured approximately 34.9 seconds for the first model call including startup, followed by a median of about 420 ms for later calls on that computer. Those measurements do not establish phone performance, battery use, thermal behavior, or audio-caption latency.

Data handling depends on which features are enabled. Ordinary glossary/model translation runs locally. Cloud review is off by default; when enabled, the original message and generated translation from Chats or the bubble are sent to the configured provider. Provider availability, quotas, and charges depend on the user's account. The app stores API keys in ordinary private SharedPreferences; it does not implement encrypted key storage. Feedback, learned meanings, and the imported model use private app files. Android backup is disabled and cleartext network traffic is disallowed in the manifest.

The declared capabilities include internet/network access, drawing over other apps, foreground service operation, and notification access. Optional accessibility must be enabled separately in Android settings. File imports use the system document picker. There is no microphone permission in the current manifest. No account system, cloud chat-history sync, OCR, speech recognition, text-to-speech, or automatic conversation sending is implemented in the inspected app. Imported chat messages are held in memory; there is no dedicated persistent chat archive or full-chat export feature in the current UI.

**The requested live audio feature is feasible as a separate development task.** The confirmed output preference is **Kannada written in English letters only**. That means live Romanized Kannada captions, preserving the spoken Kannada wording rather than displaying its English meaning.

The proposed processing path is:

1. Capture microphone audio with an explicit listening control and Android microphone permission.
2. Detect speech and pauses so silence and background noise are not continually treated as words.
3. Run Kannada automatic speech recognition to obtain recognized text.
4. Convert Kannada script into readable Latin-letter Kannada, preserving English spans and names where possible.
5. Display provisional captions as speech arrives, revise unstable words, and finalize phrases after pauses.

A multilingual model through **whisper.cpp** is a possible FOSS speech-recognition component. A complete, reviewed Kannada-to-Latin Romanizer, or an evaluated **IndicXlit** integration, could handle the written form. These are candidates, not dependencies already integrated into this app. The existing English-translation student does not need to sit on the live Kanglish-caption path. An English-meaning view would be an additional downstream option if requested later.

Smooth conversation would require measurements on the intended phone: recognition accuracy, time to first caption, finalization delay, code-switching, regional speech, overlapping speakers, silence/noise behavior, battery use, and heat. The current app has no microphone capture, ASR integration, live audio caption pipeline, or measured audio latency. A useful next step is a phone-based Kannada ASR prototype before committing to a particular model or latency promise.

For the existing text app, the next quality work is to obtain native-speaker-reviewed informal Kanglish conversations, freeze an independent evaluation set, retrain from validated data, and compare negation, names, tense, unknown-word behavior, and hallucinations against the unchanged v3 baseline. Physical-device checks should cover model memory/loading, clipboard and overlay behavior, and cloud review. The incorrect static quantization label and the configured Groq model's current availability also need verification before release.

To use the available development build, install the debug APK on a compatible ARM64 Android phone, open Settings, and import the intended v3 GGUF. The Translate tab then handles individual messages, Chats accepts text exports, and Settings enables the optional bubble and cloud review. Exact glossary phrases work even when no model is loaded.

The main artifacts and evidence for this report are:

- [Android debug APK](../mobile/android/app/build/outputs/apk/debug/app-debug.apk), 26,252,606 bytes.
- [Current v3 GGUF model](../mobile/android/app/build/outputs/apk/debug/kanglish_qwen_0.5b_v3.gguf), 531,067,840 bytes.
- [Main activity and workflows](../mobile/android/app/src/main/java/org/kanglish/app/ui/MainActivity.kt) and [actual main layout](../mobile/android/app/src/main/res/layout/activity_main.xml).
- [Local translation service](../mobile/android/app/src/main/java/org/kanglish/app/inference/TranslationService.kt), [prompt](../mobile/android/app/src/main/java/org/kanglish/app/inference/TranslationPrompt.kt), and [native inference](../mobile/android/app/src/main/cpp/kanglish_inference.cpp).
- [Cloud teacher service](../mobile/android/app/src/main/java/org/kanglish/app/inference/TeacherService.kt) and [response parser](../mobile/android/app/src/main/java/org/kanglish/app/inference/TeacherResponseParser.kt).
- [Android build configuration](../mobile/android/app/build.gradle.kts) and [permissions/integrations](../mobile/android/app/src/main/AndroidManifest.xml).
- [Dataset and student quality audit](QUALITY_AUDIT_2026-10-19.md), [repair report](QUALITY_REPAIR_2026-10-19.md), and [recorded final checks](../results/repair_20261019/final_checks.json).
- [Repaired candidate manifest](../data/processed/quality_v1/manifest.json) and [independent source verification](../results/repair_20261019/dataset_verification.json).
