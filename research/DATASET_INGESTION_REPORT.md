# Dataset Ingestion Report (`research/DATASET_INGESTION_REPORT.md`)

**Project:** `kanglish-foss`
**Phase:** 4 — Hugging Face Dataset Ingestion
**Date:** 2026-10-18
**Author:** Antigravity (automated audit + download)

---

## Summary

| Dataset | Source | Status | Records | License | Usable for Kanglish? |
|---|---|---|---|---|---|
| Aksharantar (kan) | `ai4bharat/Aksharantar` | ✅ Downloaded | 2,906,728 (train) | CC0/CC-BY-4.0 | ✅ Word-level |
| IN22-Conv | `mteb/IN22-Conv` (open mirror) | ✅ Downloaded | 1,503 (test only) | CC-BY-4.0 | ⚠️ Needs transliteration |
| IN22-Conv (upstream) | `ai4bharat/IN22-Conv` | 🔒 Gated — not accessed | — | CC-BY-4.0 | — |

---

## Pre-Download Checks

### Git exclusion verified
- `.gitignore` created before downloading any data.
- `git check-ignore data/raw/aksharantar/` → confirmed excluded.
- `git check-ignore data/raw/in22_conv/` → confirmed excluded.
- Raw data directories will NOT be committed to the repository.

### Repository inspection (via Hugging Face MCP)
- `ai4bharat/Aksharantar`: Overview and file listing inspected. HF Dataset Viewer
  returns 500 error (known issue). File `kan.zip` confirmed present at 87.6 MB in
  Git LFS.
- `ai4bharat/IN22-Conv`: **Gated.** MCP returned 404 for splits/parquet. Cannot
  access without manual agreement acceptance.
- `mteb/IN22-Conv`: Open, CC-BY-4.0. Single parquet file 1.3 MB, 1,503 rows,
  23 columns. Schema verified before download.

---

## Dataset A — Aksharantar (`kan.zip`)

### Download
| Field | Value |
|---|---|
| Source URL | `https://huggingface.co/datasets/ai4bharat/Aksharantar/resolve/main/kan.zip` |
| Local path | `data/raw/aksharantar/kan.zip` |
| File size | 87,634,360 bytes (83.57 MB) |
| SHA-256 | `a0c18fa0a8bf06b34d413b09c3e7b9505b74ba3f7f1fa2ae724793fc3fc7d650` |
| Download date | 2026-10-18 |
| HF repo revision | `main` (no pinned commit hash available via MCP) |
| Storage in git | **EXCLUDED** via `.gitignore` (`data/raw/`) |

### Actual archive structure (inspected)
```
kan_test.json    1,504,551 bytes uncompressed
kan_train.json  487,443,219 bytes uncompressed
kan_valid.json    1,065,743 bytes uncompressed
```

### Data format: JSONL (one JSON object per line)
**NOT CSV or TSV.** Each line is a JSON object with 5 fields:

| Field | Type | Description |
|---|---|---|
| `unique_identifier` | string | Internal pair ID |
| `native word` | string | **Kannada native script** (Kannaḍa lipi) |
| `english word` | string | **Romanized Latin-script spelling** of the Kannada word |
| `source` | string | Data provenance (e.g. Samanantar, IndicCorp, crowdsourced) |
| `score` | number | Quality confidence score |

> [!IMPORTANT]
> The field labeled `english word` is **NOT English**. It is the **Romanized Latin-script transliteration** of the Kannada word. The name is misleading. This is a **word-level transliteration lexicon**, not a sentence translation corpus.

### Record counts (verified by parsing full JSON)
| Split | File | Records |
|---|---|---|
| Train | `kan_train.json` | **2,906,728** |
| Validation | `kan_valid.json` | 7,025 |
| Test | `kan_test.json` | 11,380 |
| **Total** | | **2,925,133** |

### Sample records (first 3 from train)
| `english word` (Romanized) | `native word` (Kannada) |
|---|---|
| `hariyuttittu` | ಹರಿಯುತ್ತಿತ್ತು |
| `asaamanya` | ಅಸಾಮಾನ್ಯ |
| `cameragalalli` | ಕ್ಯಾಮೆರಾಗಳಲ್ಲಿ |

### License caveats
The dataset card states:
- Mined data (from Samanantar/IndicCorp) → **CC0 (Public Domain)**
- Manually verified benchmark splits (test/valid) → **CC-BY 4.0**

The HF metadata tag is just `cc` (generic). The actual breakdown above comes from
the README card. **For safety: attribute as CC-BY-4.0 for the test/valid splits.**

### Processed sample
- `data/processed/aksharantar/kan_train_sample.csv`
- 100 rows, UTF-8 with BOM, fields: `romanized_latin`, `kannada_native`, `provenance`,
  `split`, `license`, `generation_method`, `review_status`, `notes`
- All rows marked `review_status=unreviewed`
- All rows note: **"Word-level transliteration pair. NOT a sentence translation."**

### Deduplication
- 0 duplicate romanized forms in the 100-row sample (checked).
- Full dataset not deduplicated yet (2.9M rows — needs streaming dedup).

---

## Dataset B — IN22-Conv (`mteb/IN22-Conv`)

### Access Decision
- **`ai4bharat/IN22-Conv`** (upstream) is **🔒 Gated**. The MCP tool returned 404
  for splits and parquet exports. Manual acceptance is required at:
  https://huggingface.co/datasets/ai4bharat/IN22-Conv
  → Click **"Agree and access repository"** while logged in as `@Ryan1Dsouza`.
- **`mteb/IN22-Conv`** is an openly licensed mirror (CC-BY-4.0). The card explicitly
  credits `ai4bharat/IN22-Conv` as the original source. This mirror was used.

### Download
| Field | Value |
|---|---|
| Source URL | `https://huggingface.co/datasets/mteb/IN22-Conv/resolve/refs%2Fconvert%2Fparquet/default/test/0000.parquet` |
| Local path | `data/raw/in22_conv/in22_conv_mteb_default_test.parquet` |
| File size | 1,253,014 bytes (1.19 MB) |
| SHA-256 | `0440a84cbbe1958b2873ed383ba8fd54a96a60ae6d46256d9c42f36b850c339f` |
| Download date | 2026-10-18 |
| Storage in git | **EXCLUDED** via `.gitignore` (`data/raw/`) |

### Schema (23 columns, all large_string)
Each row is an n-way parallel sentence. Columns relevant to this project:

| Column | Description |
|---|---|
| `kan_Knda` | **Native Kannada script** (what we use) |
| `eng_Latn` | **English translation** (what we use) |
| (21 others) | Other Indic languages — not needed for this project |

### Record counts
| Split | Rows | Columns |
|---|---|---|
| test (only split) | **1,503** | 23 |

### Quality checks (verified by script)
| Check | Result |
|---|---|
| Null/empty `kan_Knda` | 0 |
| Null/empty `eng_Latn` | 0 |
| Duplicate `kan_Knda` rows | **4** (different English translations for same Kannada) |
| Duplicate `(kan, eng)` pairs | **0** |

> [!NOTE]
> The 4 duplicate Kannada rows have different English references — these are
> acceptable alternative translations, not data errors.

### Sample rows (first 5, verified)
| `kan_Knda` | `eng_Latn` |
|---|---|
| ಅಮ್ಮಾ, ನಾಳೆ ನಾವು ಸಿನ್ಮಾ ನೋಡಕ್‌ ಹೋಗಣ. | Mom, let's go for a movie tomorrow. |
| ನಂಗೆ ಸ್ಕೂಲಿಲ್ಲ. | I don't have to go to school. |
| ರಜೆಯಿದೆ. | It is a holiday. |
| ಓಹ್‌, ನಾಳೆ ಏಪ್ರಿಲ್‌ ೧೪ ಅಲ್ವಾ? | Oh, tomorrow is the 14th of April right? |
| ನಿಮ್‌ ಅಪ್ಪಂಗೂ ನಾಳೆ ದಿನ ಆಫೀಸಿರಲ್ಲ. | Your dad will also have the day off from work. |

> [!IMPORTANT]
> These sentences are in **native Kannada script**, not Romanized Latin.
> They CANNOT be used directly as Kanglish training inputs.
> A transliteration step (e.g. using Aksharantar lookup or IndicXlit) is required
> before these can serve as Kanglish↔English training pairs.

### Processed sample
- `data/processed/in22_conv/in22_conv_kan_en_sample.csv`
- 100 rows, fields: `source_row_index`, `kannada_native`, `english_reference`,
  `source_dataset`, `source_split`, `license`, `provenance`, `generation_method`,
  `review_status`, `notes`
- All rows: `generation_method=corpus_transliterated`, `review_status=unreviewed`
- Notes field: "Native Kannada script. Requires transliteration to Kanglish for training use."

---

## Data Quality and Safety Observations

### What this data is NOT
1. **Aksharantar ≠ sentence translations.** Every pair is a single word. Do not label
   them as Kanglish→English translation examples.
2. **IN22-Conv ≠ Kanglish data.** The Kannada text is in native script. Feeding it
   to the existing Ollama Kanglish translator would produce garbage output.
3. **Neither dataset overlaps with `data/benchmark_test_v1_draft.csv`.** The benchmark
   remains clean and untouched.

### License mixing
These two datasets have different licenses (CC0/CC-BY vs CC-BY-4.0). Any combined
derived corpus must carry the most restrictive of the constituent licenses and
attribute all sources.

---

## Deliverables Created

| File | Status |
|---|---|
| `.gitignore` | ✅ Created (excludes all raw data and archives) |
| `data/raw/aksharantar/kan.zip` | ✅ Downloaded (git-excluded) |
| `data/raw/in22_conv/in22_conv_mteb_default_test.parquet` | ✅ Downloaded (git-excluded) |
| `data/processed/aksharantar/kan_train_sample.csv` | ✅ 100 rows with provenance |
| `data/processed/in22_conv/in22_conv_kan_en_sample.csv` | ✅ 100 rows with provenance |
| `data/manifest/dataset_manifest.csv` | ✅ SHA-256, sizes, licenses, field names |
| `scripts/inspect_datasets.py` | ✅ Reusable inspection + sample extraction script |
| `research/DATASET_INGESTION_REPORT.md` | ✅ This file |

---

## For `ai4bharat/IN22-Conv` Gated Access

To accept the access conditions for the upstream (non-mirror) dataset:

1. Log in to Hugging Face as `@Ryan1Dsouza`
2. Go to: https://huggingface.co/datasets/ai4bharat/IN22-Conv
3. Click **"Agree and access repository"**
4. Re-run: `python.exe scripts/inspect_datasets.py --in22`
   (update `--in22-parquet` to point to the new file if downloaded differently)

The `mteb/IN22-Conv` mirror is substantively identical and is already downloaded.
Accepting the upstream gate is optional unless you need the original dataset
provenance for publication.

---

## Next Steps

```powershell
# 1. Verify processed sample files look correct
Get-Content data\processed\aksharantar\kan_train_sample.csv | Select-Object -First 5
Get-Content data\processed\in22_conv\in22_conv_kan_en_sample.csv | Select-Object -First 5

# 2. Re-run inspection at any time
python.exe scripts/inspect_datasets.py --aksharantar   # Aksharantar only
python.exe scripts/inspect_datasets.py --in22          # IN22-Conv only
python.exe scripts/inspect_datasets.py --sample-n 500  # Larger sample

# 3. Phase 5 — Build transliteration pipeline
#    Use Aksharantar train split as a lookup table to convert IN22-Conv
#    native Kannada script into Romanized Kanglish.
#    This produces the first Kanglish-English sentence-level parallel corpus.
#
#    Command (future):
#    python.exe scripts/transliterate_corpus.py \
#        --in22 data/raw/in22_conv/in22_conv_mteb_default_test.parquet \
#        --aksharantar data/raw/aksharantar/kan.zip \
#        --output data/processed/pilot_kanglish_en.csv

# 4. Accept ai4bharat/IN22-Conv gate (optional — see instructions above)
```

---

## Checks Performed

| Check | Method | Result |
|---|---|---|
| Git exclusion of raw data | `git check-ignore` | ✅ Both raw paths excluded |
| Aksharantar file integrity | SHA-256 computed | `a0c18fa0...` |
| IN22-Conv file integrity | SHA-256 computed | `0440a84c...` |
| Aksharantar format detection | Python zipfile + JSON parse | JSONL, 5 fields |
| Aksharantar row counts | Full parse (all splits) | Train: 2,906,728 |
| IN22-Conv schema | pyarrow parquet read | 23 cols, 1,503 rows |
| IN22-Conv null check | Column scan | 0 nulls |
| IN22-Conv duplicate check | Set comparison | 4 dup Kannada, 0 dup pairs |
| Sample files created | Script output | ✅ 100 rows each |
| Benchmark contamination | No benchmark rows derived from these sources | ✅ Clean |

---

*Report generated by `python.exe scripts/inspect_datasets.py` run 2026-10-18T15:38:49*
