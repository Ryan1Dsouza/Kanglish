# Phase 6 decision — 2026-10-18

**Recommendation:** retain direct translation as the operational baseline and test **C: original Kanglish plus an optional Kannada hint**. The next task is a **20-message, human-reviewed representation experiment**. BPCC-H-Daily is useful for source/transliteration diagnostics; it is neither authentic Kanglish nor training-ready data.

## Verified source and pilot

The local TSV is UTF-8 without BOM, 1,684,850 bytes, with columns `src_lang`, `tgt_lang`, `src`, `tgt`. It contains **8,489 data records**, all `eng_Latn -> kan_Knda`, with English and Kannada paired within each record. No separate English file is needed. There are no empty fields or duplicate pairs, nine repeated Kannada strings, and five targets without Kannada characters: **8,484 script-eligible records**, not approved translations.

The downloaded revision is **`5bde309374f21c39e7c3d505f28ae11f58f2a220`**. File SHA-256 **`f7c049f9217610f93dae24307e7a9fd4f078a5628929a8098fc871b5675973ef`** matches the local download metadata. The pinned repository metadata contains duplicate configurations named `daily`, including a `wiki/kan_Knda.tsv` mapping; use the exact pinned `daily/kan_Knda.tsv` path. Upstream identifies BPCC-H-Daily as training data; its HF split label `kan_Knda` denotes the language.

There are no original sentence/conversation IDs. Audited the existing **100-row** `data/processed/bpcc_h_daily_v1/kan_en_sample.csv`: records 1–100, indices excluding the header, verbatim English/Kannada, correct source metadata and all unreviewed; **zero audit errors**. This run did not create or change that sample. Raw record **2** pairs `george` with `ಭುವನ`; alignment does not establish semantic fidelity. Preserve the supplied reference and flag the discrepancy for bilingual review.

**License:** AI4Bharat explicitly declares **CC-BY-4.0** for H-Daily/H-Wiki in the [pinned IndicTrans2 README](https://github.com/AI4Bharat/IndicTrans2/blob/4f08e39cc6bf13cd62e2445dc725f22bff1a9219/README.md#license). Retain AI4Bharat/IndicTrans2/BPCC-H-Daily attribution, source/revision, the [license link](https://creativecommons.org/licenses/by/4.0/) and transformation notices. This publisher declaration does not establish per-row contributor provenance, personal-message consent, or a uniform license for BPCC/Aksharantar derivatives.

**Actually measured:** the unchanged dictionary functions processed only the existing first **100** records. Aksharantar's training member was scanned, retaining required lookup keys with the original candidate order/deduplication.

| Exclusive Kannada-token outcome | Count / 685 | Rate |
|---|---:|---:|
| One candidate | 224 | 32.70% |
| Multiple candidates | 86 | 12.55% |
| Unknown | 375 | 54.74% |

Additionally: **6 non-Kannada unknowns**, 95/100 messages with unknowns, 52/100 with ambiguity, and only 1/100 with neither. These are lookup statistics, not translation accuracy or full-corpus estimates. The original `n_unmatched` conflates Kannada and other unknowns; keep their denominators separate.

This probe measures **Kannada-to-Latin** generation. Runtime hints require **Latin-to-Kannada** conversion; neither this coverage result nor the Phase 5 result establishes quality in that reverse direction.

All six Latin-classified tokens were preserved, but they include app names, year ranges and an identifier; this barely tests English code-mixing. `ಇಮೇಲ್` became `emel`; `ಪ್ಲೇ`, `ಡಿಯೋನ್` and `ವ್ಯಾಕ್ಸಿನೇಷನ್‌` were unknown; `ಸೆಲಿನ್` selected `selene`. A unique match for `ಭುವನ` cannot fix the source's `george` discrepancy. Zero-width non-joiners appear in 120 unknown occurrences; normalization is a hypothesis, not a demonstrated remedy.

Saved `results/bpcc_h_daily_dictionary_probe_v1.json`: hashes, attribution, method, counters and 100 diagnostic outputs/token details, all **machine-transliterated/unreviewed**. Independent source-text, ID, hash and counter validation returned **exit 0, zero errors**. Nothing is approved for training.

Read-only screening against IN22-Conv's 1,503 test rows, original tests, draft benchmark and representation files found zero exact/character-near overlaps at 0.85. Sample records **11/36** are near duplicates (0.9778); keep them together. This heuristic does not prove semantic independence; evaluation text served only exclusion checking.

## Smallest TSV-support task — specified, not implemented

Add mutually exclusive `--training-tsv` support using stdlib `csv.DictReader`, validating the exact schema, language direction and pinned hash. Preserve English/Kannada verbatim and original record indices; report malformed/empty/non-Kannada exclusions; enforce an initial **1–100** limit. Zero must not mean unlimited.

Before writing BPCC outputs, replace the writer's **hard-coded cleaned-corpus name, URL and Apache-2.0 license** with explicit source provenance. A Parquet conversion alone would mislabel BPCC. Preserve legacy Parquet behavior, check evaluation paths before imports/reads, refuse protected/existing outputs, retain failed rows in diagnostic denominators and keep all outputs unreviewed.

Tests must cover alignment, exclusions/indices, limits, invalid schema/languages/hash, evaluation rejection, provenance and overwrite protection. With unchanged tokenization, reproduce **224/86/375** Kannada outcomes and 6 other unknowns on these 100 rows. Native reviewers must check entities and loanwords before any training use. This task is bounded infrastructure work, not permission to scale the dictionary.

## Architecture and one recommended next task

**C hypothesis:** the original text can rescue a fallible Kannada hint while preserving slang and English spans. **A** remains the fallback if hints do not help. **B**, mandatory IndicXlit then script translation, discards information and adds an unverified dependency. BPCC's assistant commands are more relevant than formal news but do not represent Bangalore chat, social context or Romanized spelling. The new **54.74% unknown** measurement provides no basis to scale the Phase 5 dictionary baseline.

Environment verified: Windows, Python **3.11.9**, i5-12450HX, ~23.7 GiB RAM, RTX 3050 Laptop **6,144 MiB VRAM**. Installed Ollama Qwen2.5:3b is ~1.9 GB; Gemma2:2b ~1.6 GB. Inference latency/peak memory were not measured. Local Qwen's license explicitly restricts use to non-commercial research; Gemma has custom terms. A permissively licensed deployment model still needs separate verification.

**Defer IndicXlit installation.** Fairseq, ai4bharat-transliteration and ONNX Runtime are absent; Python 3.11 does not establish compatibility after the previous 3.13 failures. If human hints help, test IndicXlit in an isolated, pinned compatible environment, potentially WSL/Linux, then import outputs through the existing CSV interface. Verify code/checkpoint/dependency licenses, offline loading and English-span handling; do not assume native Windows or an ONNX export works.

**Next task for Antigravity:** collect 20 genuine purpose-written or consented development messages, five per existing category. Two independent bilingual reviewers approve references and faithful Kannada hints; record permission, privacy and ambiguity decisions. BPCC/synthetic rows cannot fill these slots. Leave evaluation untouched.

After review, use the existing interface:

```powershell
python -B scripts/representation_experiment.py run --split dev --model qwen2.5:3b --representations original human --temperature 0 --seed 17 --num-ctx 2048 --num-predict 64 --dry-run
```

Only after preflight passes, repeat without `--dry-run`, review outputs and summarize the printed run directory. **Pilot gate:** all 20 pairs reviewed; at least **3 net additional accepted translations (15 percentage points)**, no increase in meaning/polarity/person/tense errors, and hint-arm p95 latency at most **2x** baseline. Count operational failures. This is development evidence, requiring later confirmation on the frozen 80-message cohort. Machine hints must pass independently. Keep A if human hints fail; consider another transliterator if human hints help but IndicXlit does not.

## Checks and delivery

- `python -B -m unittest discover -s tests -v`: **32 passed**, 2.671 s, exit **0**.
- `python -B scripts/transliterate_corpus.py --unit-test`: **24 passed**, exit **0**.
- `python -B scripts/representation_experiment.py validate`: exit **0**, empty 0/20 dev and 0/80 eval.
- `validate --ready` and the development `--dry-run`: each exit **2**, correctly blocking missing reviewed messages.
- Sample audit, bounded probe, overlap scan and diagnostic validation: exit **0**. Hash comparison confirms **31 existing files unchanged**.

Created only this memo and the diagnostic JSON. No script/translator/glossary/evaluation edits, installations, model downloads or training. Blockers: genuine reviewed messages, source quality defects, TSV provenance support, IndicXlit compatibility and a permissively licensed release model.
