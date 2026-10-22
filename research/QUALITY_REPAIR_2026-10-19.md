**Reliability repairs — 19 October 2026**

The data-export and teacher-response defects identified in the audit have been repaired. An updated Android debug APK is built. The v3 model weights have not been retrained, so these changes do not establish improved translation accuracy.

The new [candidate export](../data/processed/quality_v1/manifest.json) contains 4,491 training candidates and 504 internal validation candidates. There are 2,500 dictionary pairs sampled across 21 initial letters and 2,495 Kannada-script conversation pairs. Every retained input and English target was checked against its recorded source row, with source/license/attribution metadata retained. No Kannada-containing targets or unresolved dictionary cross-references remain in this export. This is a source-backed candidate dataset, not a human-reviewed real-chat benchmark.

The [review queue](../data/processed/quality_v1/review_queue.jsonl) contains 2,195 existing rows: 467 dictionary-pointer targets, 30 other Kannada-containing targets, 1,405 legacy pairs without traceable semantic sources, 264 teacher pairs, 24 reserved diagnostic/evaluation inputs and five source rows with conflicting targets. One additional teacher pair falls in the reserved-input category. Neither teacher output nor placeholder reviewer names are promoted to human verification.

[The preparation script](../scripts/prepare_quality_dataset.py) reads the existing sources and writes to a new directory, refusing to replace a previous export. It excludes protected evaluation and previous diagnostic inputs, preserves source records, quarantines conflicting answers, and groups spelling variants, source siblings and shared answers before splitting. Both splits contain dictionary and conversation data. Independent checks found zero input-family, answer-family or source-group overlap between them. No new English reference translations or owner evaluation rows were written.

[Shared quality checks](../scripts/trusted_pipeline/quality.py) reject dictionary pointers, Kannada in English targets, malformed examples and empty data. The Alar importer no longer restores a bad definition through its fallback. The legacy comprehensive builder samples across the dictionary instead of taking its first 2,500 entries. The v3 merger and both v3 training entry points reject invalid labels, and training uses grouped splits rather than the appended teacher block as validation. Historical training and catalogue snapshots remain available for comparison; run the new exporter for repaired candidates.

The slang importer now discards the known placeholder reviewer identifiers, emits those seed entries as candidates needing review, and records a real source-file checksum. Schema validation rejects those placeholder identities when an old record claims human verification. This detects the older catalogue's misleading labels rather than silently validating them.

On Android, [TeacherResponseParser](../mobile/android/app/src/main/java/org/kanglish/app/inference/TeacherResponseParser.kt) requires typed fields and an explicit `match`, `mismatch` or `uncertain` verdict. Empty objects, missing fields, blank translations, invalid field types and extra text no longer imply agreement. An uncertain review must contain a reason and no proposed translation. Both providers receive the same review contract. This is a format and behavior safeguard; their real semantic accuracy has not been benchmarked.

Chat and the floating panel display an uncertain verdict and hide “Save meaning.” Uncertain or unapproved results cannot enter the glossary through the chat action. Retranslation clears the old suggestion/review state. A review is not attached if the student's text changed while the network request was running. Cloud review continues to use the user's existing opt-in setting.

**Validation:** 48 Python tests passed, including ten new data-regression tests. All 27 Android tests passed, including seven new response/UI tests. The changed data-test module also passed after the final manifest-accounting update. Offline Android assembly succeeded. [Independent dataset checks](../results/repair_20261019/dataset_verification.json) validated all 4,995 candidate pairs against their source records and checked output hashes. Protected evaluation/glossary files and historical v3/teacher training files retain their original hashes. The APK is at [app-debug.apk](../mobile/android/app/build/outputs/apk/debug/app-debug.apk); it has not been installed on a phone or tested against live cloud-teacher responses.

To prepare another candidate version:

```powershell
python -B scripts/prepare_quality_dataset.py --out data/processed/quality_NEXT
```

The next useful quality step is native-speaker review of real informal Kanglish conversations and a frozen independent evaluation cohort, then a measured retraining experiment. These candidates still contain Kannada-script BPCC sentences and dictionary definitions, and exclude unreviewed synthetic chat pairs; blindly training on them could lose conversational coverage. The existing 20-message development and 80-message evaluation workflow can provide the missing evidence. The current data supports structural validation, not a new accuracy claim.

The live-audio request remains a separate feasible feature: Kannada recognition followed by Romanization and incremental captions. No microphone or ASR feature is included in this repair. Its next implementation step would be microphone capture, speech/noise segmentation and a Kannada recognizer benchmark on the target phone, followed by a full-script Romanizer. The English-translation student need not be on that caption path.
