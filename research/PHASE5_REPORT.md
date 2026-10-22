# Phase 5 Report: Transliteration Pipeline

**Project:** `kanglish-foss`
**Date:** 2026-10-18
**Phase:** 5 — Transliteration-to-Training-Data Pipeline

---

## 1. Summary

| Step | Status | Key Finding |
|---|---|---|
| Evaluate protection (IN22-Conv) | ✅ Blocked by safety code | Eval file rejected at load time |
| Audit `english-kannada-cleaned` | ✅ Inspected via MCP | Apache-2.0, 802K rows, formal/news domain |
| Ingest train sample | ✅ 200 sentences processed | 63.7% token coverage by dictionary |
| Build `scripts/transliterate_corpus.py` | ✅ 24/24 unit tests pass | |
| Pilot run (200 sentences) | ✅ Complete | 36.4% UNK rate — poor fit |
| Write `kanglish_candidates_v1.csv` | ✅ 195 candidate rows | All unreviewed, machine-generated |
| Update `dataset_manifest.csv` | ✅ 3 entries | |

**Overall verdict:** The dictionary baseline achieves 63.7% token coverage on formal Kannada sentences. 84% of sentences contain at least one unknown token. The corpus domain (news, political speeches) is a poor match for conversational Kanglish. The candidates are labelled machine-generated and unreviewed; they are **not ready for fine-tuning**.

---

## 2. Dataset C — `ramachandrajoshi/english-kannada-cleaned`

### MCP Inspection Results

| Field | Value |
|---|---|
| Repo | `ramachandrajoshi/english-kannada-cleaned` |
| License | **Apache-2.0** ✅ (commercial-safe) |
| Actual row count | Train: 800,000 / Val: 1,000 / Test: 1,000 → **802,000 total** |
| README claim | "Train 8,00,000 / Val 1,000 / Test 1,000 / **Total 5,02,000**" |
| README inconsistency | Total "5,02,000" is a corrupt Indian-numeral rendering; real total is 802,000 |
| Columns | `english_sentences`, `kannada_sentences` (2 columns, native Kannada script) |
| Format | Parquet (HF auto-converted from CSV) |
| Upstream provenance | `damerajee/en-kannada` (referenced in README Acknowledgements) |
| Domain | Formal: news, political speeches, Wikipedia. NOT conversational. |

### Provenance Caveat

> [!WARNING]
> The card acknowledges derivation from `damerajee/en-kannada` but provides no
> further upstream source documentation (corpus license chain, original crawl
> source). The cleaned derivative is licensed Apache-2.0 by the author.
> Use with attribution. Do not treat as having a fully audited provenance chain.

### Download Record

| Field | Value |
|---|---|
| Source URL | `https://huggingface.co/datasets/ramachandrajoshi/english-kannada-cleaned/resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet` |
| Local path | `data/raw/en_kan_cleaned/train_0000.parquet` |
| Size | 88,464,180 bytes (84.36 MB) |
| SHA-256 | `64274bb377c5eb40f76ba3ec791e4d08eb57d0ed164cc51541e122566a916ce4` |
| Split ingested | **train only** (val and test NOT ingested — reserved for future evaluation use) |
| Rows used | **200** (pilot) of 800,000 available |

---

## 3. Transliteration Pipeline: `scripts/transliterate_corpus.py`

### Design

The script implements a **word-level dictionary lookup** using the Aksharantar
`kan_train.json` word pairs (2,906,728 records, 2,871,160 unique native forms).

**Per-token logic (explicit and reproducible):**
1. **Punctuation** (`.,!?;:"()[]{}/%\`) — preserved verbatim.
2. **Numeric tokens** (`^[\d.,]+$`, no Kannada chars) — preserved verbatim.
3. **Latin/English tokens** (`^[A-Za-z0-9'-]+$`, no Kannada chars) — preserved verbatim (code-mixed English).
4. **Kannada token with 1 dictionary match** — replaced with the Romanized form.
5. **Kannada token with 2+ dictionary matches** — first candidate used, token prefixed with `<<AMB>>`, all candidates stored in `token_details`.
6. **Kannada token with 0 dictionary matches** — replaced with `<<UNK>>`. **Never silently guessed.**
7. **Other/mixed tokens** — `<<UNK>>`.

**Candidate selection method:** First insertion order in Aksharantar JSONL. When multiple romanizations exist for one native word, the first occurrence in the training file is selected. This is deterministic but not frequency-ranked.

### Safety

- **Evaluation block:** `load_training_corpus()` computes the absolute canonical path of the requested file and compares it against the IN22-Conv eval parquet path. A `ValueError` with `"SAFETY BLOCK"` message is raised if they match. Tested and verified in unit tests.
- **No silent guessing:** UNK tokens are always marked. The pipeline never invents a transliteration.
- **Provenance stamped on every output row:** source dataset, source URL, source split, source row index, transliteration method, Aksharantar source, timestamp.

### Unit Test Results

**24/24 tests passed** (exit code 0). Tests covered:

| Category | Tests |
|---|---|
| Punctuation preservation (period, question mark) | 4 |
| Latin/English token preservation | 2 |
| Unknown token marking (UNK) | 4 |
| Ambiguous entry handling (AMB + candidates stored) | 4 |
| Repeated word | 2 |
| Pure English code-mixed sentence | 3 |
| Coverage score calculation | 1 |
| Deterministic output | 1 |
| Safety block: eval file rejected | 1 |
| Numeric + % token | 2 |

---

## 4. Pilot Run Results (200 sentences)

**Command:**
```powershell
python.exe scripts/transliterate_corpus.py --limit 200 --out data/processed/kanglish_candidates_v1.csv
```

### Coverage Statistics

| Metric | Value |
|---|---|
| Sentences processed | 200 |
| Candidates written | **195** (5 had zero matched Kannada tokens — excluded) |
| Total Kannada tokens | 1,466 |
| Tokens matched | **934 (63.7%)** |
| Tokens unmatched (UNK) | **534 (36.4%)** |
| Tokens ambiguous (AMB, first candidate taken) | **376 (25.6%)** |
| Sentences with any UNK | **168 (84.0%)** |
| Low-coverage sentences (<50%) | **33 (16.5%)** |

### Output File Statistics (`kanglish_candidates_v1.csv`)

| Metric | Value |
|---|---|
| Rows | 195 |
| Coverage min/max | 0.167 / 1.000 |
| Coverage mean | 0.664 |
| Coverage median | 0.667 |
| Rows with UNK tokens | 163 (83.6%) |
| Rows with AMB tokens | 158 (81.0%) |
| `review_status` | `unreviewed` (100%) |
| `generation_method` | `machine_transliterated` (100%) |

### Sample Failures (low coverage, <50%)

```
[0.33]  '90ರಷ್ಟು ಚಿತ್ರೀಕರಣ ಪೂರ್ಣಗೊಂಡಿದೆ.'
      → '<<UNK>> <<AMB>>chitreekarana <<UNK>>.'

[0.00]  '720ಪಿ ಎಚ್ಡಿ ರೆಕಾರ್ಡಿಂಗ್'
      → '<<UNK>> <<UNK>> <<UNK>>'

[0.00]  'ಮೊದಲ ಶಾಟ್'
      → '<<UNK>> <<UNK>>'

[0.17]  'ಫೋನ್ 160 ಗ್ರಾಂ ತೂಗುತ್ತದೆ ಮತ್ತು 9.7 ಮಿಮೀ ದಪ್ಪವಾಗಿರುತ್ತದೆ'
      → '<<AMB>>phoone 160 <<UNK>> <<UNK>> <<UNK>> 9.7 <<UNK>> <<UNK>>.'

[0.43]  'ಜೀವನ ಮಟ್ಟವು ದೇಶದಿಂದ ದೇಶಕ್ಕೆ ಬದಲಾಗುತ್ತದೆ ಎಂಬುದು ನಿಜ.'
      → '<<UNK>> <<UNK>> deshadinda <<AMB>>deshakke <<UNK>> embudu <<UNK>>.'
```

### Analysis of Failures

1. **Loanwords/tech terms** (`ಶಾಟ್` = "shot", `ರೆಕಾರ್ಡಿಂಗ್` = "recording", `ಬ್ಲಾಗ್` = "blog") — these are transliterations of English words into Kannada script. Aksharantar has limited coverage of borrowed vocabulary.
2. **Inflected compound forms** (`ಚಿತ್ರೀಕರಣ` = "filming/shooting") — morphologically complex, often not in Aksharantar as whole tokens.
3. **Numeric-Kannada composites** (`90ರಷ್ಟು` = "about 90%") — fused tokens the tokenizer cannot split.
4. **Template placeholders** (`{-ಬ್ರಾಂಡ್-ಹೆಸರು-}`) — noisy data artifacts from the source corpus.

---

## 5. What This Data Is and Is NOT

> [!IMPORTANT]
> **`kanglish_candidates_v1.csv` is NOT Kanglish training data.**
> - All 195 rows are machine-generated via dictionary lookup.
> - 83.6% contain at least one `<<UNK>>` marker — they are **incomplete translations**.
> - The source corpus is formal Kannada (news, politics) — not the informal, conversational, code-mixed Kanglish this project targets.
> - `review_status=unreviewed` on every row.
> - No row has been validated by a native speaker.
> - Do not fine-tune any model on this data as-is.

---

## 6. Recommendations

### Immediate (blocking)
1. **IndicXlit evaluation is needed.** The 36.4% UNK rate on a well-resourced corpus is too high for the dictionary baseline alone. `ai4bharat/IndicXlit` is a sequence-to-sequence transliterator that handles inflected forms and OOV words.
   ```powershell
   # Recommended next step:
   pip install ai4bharat-transliteration
   # Then run transliterate_corpus.py with --method indicxlit flag (to be added)
   ```
2. **Use IN22-Conv as the sentence source instead.** The 1,503 sentences from IN22-Conv are conversational (school, family, movies) — far closer to actual Kanglish than the formal en-kannada-cleaned corpus.

### Medium term
3. **Human review of even 50 candidates** would be sufficient to quantify how many machine-transliterated outputs are usable without correction.
4. **Frequency-rank the AMB candidates** — currently the first Aksharantar insertion is taken. A frequency-weighted selection (e.g. by `score` field in Aksharantar) would reduce ambiguity errors.
5. **Filter out low-coverage rows (<70%)** before any review pass — this removes 63 of the 195 candidates, leaving 132 higher-quality rows.

### Not recommended
- Do not use the locked `data/benchmark_test_v1_draft.csv` as any part of the training pipeline.
- Do not claim any machine-transliterated output is authentic Kanglish.
- Do not begin fine-tuning until at least one batch of candidates has passed native speaker review.

---

## 7. Files Created / Modified

| File | Action | Notes |
|---|---|---|
| `data/raw/en_kan_cleaned/train_0000.parquet` | Created | git-excluded, 84.36 MB |
| `data/processed/kanglish_candidates_v1.csv` | Created | 195 rows, machine-generated |
| `scripts/transliterate_corpus.py` | Created | 24/24 unit tests pass |
| `data/manifest/dataset_manifest.csv` | Updated | DSET-003 added |
| `research/PHASE5_REPORT.md` | Created | This file |

**Protected files untouched:**
`data/test.csv`, `data/glossary.csv`, `scripts/score.py`, `scripts/baseline.py`,
`scripts/glossary_run.py`, `data/benchmark_test_v1_draft.csv`, `scripts/benchmark.py`

---

## 8. Exact Next Commands

```powershell
# 1. Re-run unit tests at any time
python.exe scripts/transliterate_corpus.py --unit-test

# 2. Inspect candidates
python.exe -c "
import csv
rows = list(csv.DictReader(open('data/processed/kanglish_candidates_v1.csv', encoding='utf-8-sig')))
for r in rows[:5]:
    print(r['coverage_score'], r['romanized_input'][:80])
"

# 3. Filter to coverage >= 0.70 for review priority
python.exe -c "
import csv
rows = list(csv.DictReader(open('data/processed/kanglish_candidates_v1.csv', encoding='utf-8-sig')))
good = [r for r in rows if float(r['coverage_score']) >= 0.70]
print(len(good), 'rows with coverage >= 0.70')
"

# 4. When ready: scale to 1000 sentences
python.exe scripts/transliterate_corpus.py --limit 1000 --out data/processed/kanglish_candidates_v2.csv

# 5. Future: install IndicXlit for sequence-to-sequence transliteration
pip install ai4bharat-transliteration
```
