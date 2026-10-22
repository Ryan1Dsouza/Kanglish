**Dataset, student-model and live-audio audit — 19 October 2026**

The current v3 system is not reliable for arbitrary Kannada/Kanglish input. A local probe of the actual v3 GGUF produced unrelated word meanings, reversed negation and definite translations of artificial nonsense. The source collection is useful, but its current training export and evaluation process do not establish generalization. Cloud-teacher accuracy was not tested; no external teacher requests were made.

The requested audio output was clarified as **Kannada written in English letters only**. Live Kanglish captions are feasible as a separate speech-recognition and transliteration path. They do not require the English-translation student.

The reproducible evidence is in [the final dataset audit](../results/audit_20261019/verified_sources/dataset_audit.json), [all 29 probe outputs](../results/audit_20261019/verified_sources/student_probes.jsonl), [the probe manifest](../results/audit_20261019/verified_sources/probe_manifest.json), [source-file integrity checks](../results/audit_20261019/verified_sources/raw_source_integrity.json), and [evidence verification](../results/audit_20261019/verified_sources/verification.json). The earlier audit JSON in the parent directory records the initial sampling pass before Kannada cross-references were excluded from probe references; its probe candidates were not run.

**Observed behavior.** The probe used the existing 0.5B v3 Q8_0 GGUF, SHA-256 `ce172bdd5f50f6a65547c7b05268ea982674efb33795a2fbcd21f2d73e75ea1a`, through local Ollama. The Python adapter reproduced the current Android prompt and bundled glossary for these inputs, with temperature 0.1, seed 42, context 1,024 and output limit 192. It was desktop inference, not execution inside Android. No previous chat or user-learned glossary was supplied. Model and relevant source hashes stayed unchanged during the run.

| Input | Existing reference or diagnostic purpose | Actual output |
| --- | --- | --- |
| `naale college ge barthira?` | Owner test: “Are you coming to college tomorrow?” | “Are you coming to college?” — drops tomorrow |
| `sakkath aagide` | Owner test: “It's awesome” | “It's awesome / great.” — returned by exact glossary lookup |
| `class cancel aagilla naale` | Unreviewed draft: “Class has not been cancelled tomorrow” | “Class will be cancelled.” — contradicts the reference's negation |
| `naanu baralla ivattu` | Unreviewed draft: “I will not come today” | “I will come to your house” — reverses polarity and adds a destination |
| `marmarisu` | Alar: “to make a sound by shaking leaves or by walking on dry leaves.” | “milk chocolate” |
| `zqxvpl` | Artificial unknown input; no reference meaning asserted | “hey” |

There were 28 model calls and one exact-glossary result. All requests completed; `status: ok` in the evidence means operational success, not a correct translation. All four artificial negative controls received definite translations. No human accuracy ratings were created. The sample includes three owner tests, six unreviewed synthetic draft sentences, eight source-dictionary words in both Latin and Kannada forms, and four artificial controls. The dictionary forms were absent from v3's exact examples and the audit's token vocabulary; this does not establish absence from pretraining or related word families. This small diagnostic sample does not support a population accuracy percentage.

The first model call took about 34.9 seconds including startup; subsequent model calls had a median elapsed time of about 420 ms on this computer. These figures do not measure phone performance or audio latency.

**The training export has concrete quality problems.** All seven processed JSONL files parse, and all five raw source files match their recorded manifest hashes and sizes. Parsing and checksum success do not validate labels.

| Finding in current v3 | Measurement | Implication |
| --- | --- | --- |
| Training-file size | 6,492 rows: 6,227 baseline plus 265 teacher pairs | The large source catalogue is not equivalent to this many conversational training examples |
| Kannada in input | 3,652 rows, 56.25% | Much of the data differs from the app's informal Latin-script input |
| Kannada in target labelled as English | 497 rows, 7.66% | Targets include untranslated dictionary references |
| Targets beginning with `=` | 467 rows, 7.19% | Dictionary pointers are being trained as translation answers |
| Repeated normalized inputs | 250 additional rows; 194 inputs have multiple targets | Some are legitimate word senses, but they need sense/context handling; they are not 250 duplicate input/output pairs |
| Teacher review metadata | Missing on all 265 pairs | The generation scripts do not establish independent semantic review |
| Dictionary selection in comprehensive builder | First 2,500 qualifying entries; all 2,500 start with `a` | Vocabulary selection is severely biased toward one part of the dictionary |

For example, v3 trains `accarisu` to produce `= ಅಚ್ಚರಿಗೊಳ್ಳು.`. The same issue occurs in the larger source catalogue: 41,933 Alar records contain Kannada in `english_meaning`, and 39,659 begin with a cross-reference marker. These are often valid dictionary records but unsuitable as direct English translation targets without resolving the references.

The cause is visible in [the Alar importer](../scripts/trusted_pipeline/importers/alar_importer.py): its attempted Kannada check tests only the two endpoint characters U+0C80 and U+0CFF, not the Kannada Unicode range; its fallback also retains non-English definitions. The training builder checks target length but does not resolve or quarantine dictionary references. The existing schema validates metadata and status rules but accepts these targets. Cleaning the export is necessary even though the schema tests pass.

The full trusted catalogue contains 156,620 lexical entries, 8,484 conversational entries, 7,025 transliteration entries and 11 slang entries. Aksharantar records correctly leave the English-meaning field empty: Romanization is not semantic translation. Of 172,140 catalogue records, 172,129 are `raw`, 10 are labelled `human-verified`, and one needs review. The ten reviewed labels are produced from hardcoded `reviewer_kannada_1` / `reviewer_kannada_2` identifiers in [the slang importer](../scripts/trusted_pipeline/importers/slang_importer.py); all 11 slang checksums are placeholders rather than real SHA-256 values. The repository does not establish that these are independently reviewed gold labels.

**Generalization is not currently measured.** Both human-review experiment files contain zero rows. `python -B scripts/representation_experiment.py validate --ready` reports that neither cohort has reviewed records. The old owner test has only three rows, one of which (`sakkath aagide`) occurs in v3 training and also returns directly from the app glossary. The 100-row draft benchmark and 20-row synthetic development set are explicitly unreviewed; they cannot substitute for independent human evaluation.

Both v3 training scripts split the ordered training file at 98%. Since teacher pairs are appended after the baseline, all 130 validation rows come from the teacher block; four overlap training after punctuation normalization. The split has no independent real-chat cohort. Trainer token accuracy is not sentence-level translation accuracy. The autonomous pipeline's five printed example outputs are a smoke check, not a scored held-out evaluation.

**The teacher helps only if its own result is sound.** Training-time “distillation” here means supervised fine-tuning on generated text pairs. Generation checks nonempty strings and duplicate prompts, not correctness. Gemini and Groq are fallback sources, not two independent reviewers. All current teacher rows identify Gemini variants. Runtime verification shows the teacher the student's answer, asks for agreement, and has no calibrated uncertainty or abstention result. Both models can agree on the same mistake.

[TeacherService](../mobile/android/app/src/main/java/org/kanglish/app/inference/TeacherService.kt) also accepts a structurally valid response such as `{}`: missing `isMatch` defaults to `true`, and missing translation defaults to the student's answer, while `success` becomes `true`. Required field types and nonempty text should be checked before displaying a successful review. Network failures are different: they return `success=false`, and the current caller correctly checks that flag. Cloud review is off by default and therefore does not protect ordinary offline translations. Each provider has eight-second connect/read timeouts, making synchronous review unsuitable for smooth caption updates.

The app's “Learn” action saves the selected correction to the local glossary. It does not update the model weights or automatically teach related sentences. A mistaken correction can consequently become an exact lookup answer until corrected again.

The next quality work should resolve or quarantine dictionary pointers, sample vocabulary across the full lexicon, retain source/review/sense metadata, and balance reviewed informal Kanglish sentences. Split by conversation and spelling-variant family before augmentation, keep owner-written evaluation separate, and assess negation, names, numbers, person, tense, unseen words and unsupported-input behavior. Add explicit uncertainty handling and strict teacher response validation, then retrain and compare on the frozen reviewed cohort. More synthetic examples alone do not establish reliability.

**Live audio can use a simpler path:** microphone → speech activity detection → Kannada speech recognition → Kannada-to-Latin transliteration → live Kanglish captions. Show provisional captions while speech arrives, replace unstable words as recognition improves, and finalize at pauses. Preserve English spans and names. Avoid asking an English-translation LLM to recreate the Kannada wording.

A FOSS candidate is a multilingual model through [whisper.cpp](https://github.com/ggml-org/whisper.cpp), whose repository includes Android and streaming examples and Kannada language support. Its [streaming example](https://github.com/ggml-org/whisper.cpp/blob/master/examples/stream/README.md) uses repeated audio windows; it is a prototype, not proof of low latency on this phone. Use a reviewed full-script Romanizer for predictable conversion, or evaluate [IndicXlit's Kannada native-to-Roman model](https://github.com/AI4Bharat/IndicXlit). IndicXlit is a candidate requiring integration work, not an established Android dependency in this repo. The current Python word-lookup transliterator emits unknown markers for uncovered words and is not a complete caption solution.

The Android app currently declares no microphone permission and has no speech recognizer/audio capture implementation. Android's generic [SpeechRecognizer documentation](https://developer.android.com/reference/android/speech/SpeechRecognizer) also cautions that the default service may use remote servers and is not intended for continuous recognition; on-device service and Kannada availability must be checked separately if using that route. For this use case, benchmark the chosen recognizer on the target phone rather than promising an operating mode from the API name.

A reasonable product target to test is provisional updates within roughly 0.5–1 second and stable text shortly after a pause, with a 1–2 second finalization budget. These are proposed targets, not measurements or guarantees. Recognition accuracy, thermal load and battery use need physical-device testing. Speech/noise gating and an uncertainty display remain necessary because ASR can insert or mishear words even when transliteration is deterministic. The quality set should include natural Kannada, English code-switching, regional speech, overlapping speakers, background noise and silence.

**Verification and reproduction.** The 38 existing Python tests passed. The reviewed-cohort readiness check correctly failed because those files are empty. All protected evaluation/glossary hashes remained unchanged, and the captured predictions and model/source hashes were checked. This audit added diagnostic scripts and evidence; it did not create expected translations or modify model weights.

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/audit_dataset_quality.py --out results/audit_NEW_RUN
# With local Ollama running, register the existing GGUF; no model download is needed.
ollama create kanglish-audit-v3-20261019 -f results/audit_20261019/Modelfile.v3
python -B scripts/probe_student_quality.py --audit results/audit_NEW_RUN/dataset_audit.json --model kanglish-audit-v3-20261019 --gguf mobile/android/app/build/outputs/apk/debug/kanglish_qwen_0.5b_v3.gguf
```

The scripts refuse to overwrite existing audit/probe evidence. They use Python's standard library, and model requests are restricted to local Ollama. Keep the source snapshots and model digest with any future comparison; do not compare human accuracy numbers to the operational success counts in this diagnostic run.
