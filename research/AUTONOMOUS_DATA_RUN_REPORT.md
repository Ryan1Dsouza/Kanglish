# Autonomous Data Run Report

**Project:** `kanglish-foss`
**Date:** 2026-10-18
**Phase:** 6 — BPCC-H-Daily Dataset Ingestion

---

## 1. File Inspection (Verified, Not Assumed)

### Local file
| Field | Value |
|---|---|
| Path | `data/raw/bpcc_h_daily/daily/kan_Knda.tsv` |
| Size | 1,684,850 bytes (1,645 KB) |
| SHA-256 | `f7c049f9217610f93dae24307e7a9fd4f078a5628929a8098fc871b5675973ef` |
| Pinned revision | `5bde309374f21c39e7c3d505f28ae11f58f2a220` |
| Download method | `hf download ai4bharat/BPCC daily/kan_Knda.tsv --repo-type dataset --revision 5bde309...` |
| Git status | **Excluded** via `.gitignore` (`data/raw/`) — confirmed |

### Encoding and format
- Detected from raw hex: **UTF-8, no BOM**, LF line endings
- Delimiter: **TAB (`\t`)**
- Header row present: `src_lang`, `tgt_lang`, `src`, `tgt`

### Row audit
| Metric | Value |
|---|---|
| Total rows (excl. header) | **8,489** |
| Empty `src` fields | 0 |
| Empty `tgt` fields | 0 |
| Duplicate `src` values | 0 |
| Duplicate `tgt` values | 9 |
| Duplicate `(src, tgt)` pairs | **0** |

### Direction and alignment
- `src_lang` = `eng_Latn` (100% of rows — verified by set check)
- `tgt_lang` = `kan_Knda` (100% of rows — verified by set check)
- `src` = **English reference text**
- `tgt` = **Kannada native script**
- Alignment is confirmed: every row has both fields non-empty

### Rows with no Kannada script in `tgt` (5 rows excluded)

These are app/service names that were left untranslated:

| Row # | src | tgt |
|---|---|---|
| 1319 | `instagram` | `instagram` |
| 2981 | `olly` | `olly` |
| 3639 | `myspace` | `myspace` |
| 3760 | `google uber` | `google uber` |
| 7378 | `pandora` | `pandora` |

### Token length distribution
| Field | Min words | Max words | Mean words |
|---|---|---|---|
| `src` (English) | 1 | 38 | 8.4 |
| `tgt` (Kannada) | 1 | 33 | 6.5 |

**Domain:** Conversational, voice-assistant-style daily commands. Significantly better domain fit for Kanglish than `en-kannada-cleaned` (formal/news).

---

## 2. License and Provenance

| Field | Value |
|---|---|
| Declared license | **CC-BY-4.0** |
| Repository card | `ai4bharat/BPCC` README.md (inspected via MCP) |
| Sub-corpus | `daily/` — BPCC-H-Daily subset |
| Provenance | Part of IndicTrans2 benchmark parallel corpus (ai4bharat) |
| HF login required | Yes — `hf auth login` with read token before `hf download` |

> [!NOTE]
> The repository card confirms CC-BY-4.0 for the BPCC-H sub-corpus.
> Attribution required: "IndicTrans2, AI4Bharat, CC-BY-4.0."
> No restriction on research use.

---

## 3. Leakage and Benchmark Validation

```
Blacklist entries checked: 15
Rows matching blacklist: 0

Benchmark inputs checked: 100
Overlap with BPCC src: 0
Overlap with BPCC tgt: 0
```

**The BPCC-H-Daily data has no overlap with the locked evaluation benchmark or the leakage blacklist.**

---

## 4. Processed Sample

### Output
- **File:** `data/processed/bpcc_h_daily_v1/kan_en_sample.csv`
- **Rows:** 100 (from 8,484 eligible rows)
- **Size:** 60,344 bytes

### Schema (16 fields per row)

| Field | Description |
|---|---|
| `id` | Stable ID: `BPCC-CAND-00001` … |
| `source_row_index` | 1-based row number in source TSV |
| `english_reference` | Original English sentence (`src`) |
| `kannada_native` | Original Kannada native script (`tgt`) |
| `src_lang` | `eng_Latn` |
| `tgt_lang` | `kan_Knda` |
| `source_dataset` | `ai4bharat/BPCC` |
| `source_subset` | `daily` |
| `source_file` | `daily/kan_Knda.tsv` |
| `source_revision` | `5bde309374f21c39e7c3d505f28ae11f58f2a220` |
| `source_url` | HF repo URL |
| `license` | `CC-BY-4.0` |
| `generation_method` | `corpus_aligned` |
| `transliteration_method` | `none_applied` |
| `review_status` | `unreviewed` |
| `notes` | Explicit disclaimer |

### Validation results (verified by script)
- All 100 rows `review_status=unreviewed` ✅
- All 100 rows `generation_method=corpus_aligned` ✅
- All 100 rows have non-empty `english_reference` ✅
- All 100 rows have non-empty `kannada_native` ✅
- All 100 rows have `source_revision` ✅

---

## 5. What This Data Is and Is NOT

> [!IMPORTANT]
> **`bpcc_h_daily_v1/kan_en_sample.csv` is not Kanglish training data.**
> - The `kannada_native` field is in native Kannada script, not Romanized Latin.
> - `transliteration_method=none_applied` — no conversion has been done.
> - `review_status=unreviewed` on every row.
> - Do not fine-tune any model on this data as-is.
> - The English field is the **reference translation**, not the model input.
> - The note in row 1 highlights a name substitution risk: "george" → "ಭುವನ" (a different name was used in the Kannada translation). This type of proper-noun drift is a known issue in BPCC-H and must be checked before use.

---

## 6. Dataset Manifest (4 entries)

`data/manifest/dataset_manifest.csv` updated:

| ID | Name | Rows | License |
|---|---|---|---|
| DSET-001 | Aksharantar (Kannada) | 2,906,728 train | CC0/CC-BY-4.0 |
| DSET-002 | IN22-Conv (mteb mirror) | 1,503 test | CC-BY-4.0 |
| DSET-003 | English-Kannada Cleaned | 800,000 train | Apache-2.0 |
| DSET-004 | **BPCC-H-Daily (Kannada)** | **8,489** | **CC-BY-4.0** |

---

## 7. Files Created / Modified

| File | Action | Notes |
|---|---|---|
| `data/raw/bpcc_h_daily/daily/kan_Knda.tsv` | Downloaded by user | git-excluded, 1.6 MB |
| `data/processed/bpcc_h_daily_v1/kan_en_sample.csv` | Created | 100 rows, all unreviewed |
| `data/manifest/dataset_manifest.csv` | Updated | DSET-004 added |
| `research/AUTONOMOUS_DATA_RUN_REPORT.md` | Created | This file |

**Protected files — all untouched:**
`data/test.csv`, `data/glossary.csv`, `scripts/score.py`, `scripts/baseline.py`,
`scripts/glossary_run.py`, `data/benchmark_test_v1_draft.csv`, `scripts/benchmark.py`,
`scripts/transliterate_corpus.py`

---

## 8. Next Steps

### Immediate (blocking)
1. **Apply transliteration to BPCC-H-Daily.** Run the existing pipeline:
   ```powershell
   # BPCC uses Kannada in the tgt column; the pipeline needs a shim to read TSV
   # Either extend transliterate_corpus.py to accept TSV sources, or
   # convert the TSV sample to parquet first:
   python.exe scripts/transliterate_corpus.py `
       --training-parquet data/processed/bpcc_h_daily_v1/converted.parquet `
       --limit 100 --out data/processed/bpcc_h_daily_v1/kanglish_candidates_v1.csv
   ```

2. **Verify the proper-noun drift issue.** Row 1: "george" (English) → "ಭುವನ" (Kannada, a different name). This is a known BPCC-H annotation artifact. Screen for similar cases before training use.

3. **Prioritize BPCC over en-kannada-cleaned.** The conversational domain (mean 8.4 English words/sentence) is a much closer match to Kanglish use cases than the formal news corpus.

### Medium term
4. Run `scripts/transliterate_corpus.py --unit-test` to confirm 24/24 pass after any future changes.
5. Extend the transliteration pipeline to accept TSV input directly (add `--training-tsv` flag and `tgt`/`src` column mapping).
6. After transliteration: human spot-check of at least 20 output rows before any model use.

---

## 9. Exact Verified Commands Run

```powershell
# Inspect file
python.exe audit_bpcc.py          # rows=8489, cols=[src_lang,tgt_lang,src,tgt], 0 nulls
python.exe check_leakage.py       # 0 blacklist hits, 0 benchmark overlap
python.exe build_bpcc_sample.py   # 100 rows written, all validated
python.exe update_manifest.py     # 4 entries in manifest

# Unit tests still passing
python.exe scripts/transliterate_corpus.py --unit-test   # 24/24 pass
```
