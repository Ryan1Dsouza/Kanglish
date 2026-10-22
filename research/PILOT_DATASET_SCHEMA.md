# Pilot Dataset Schema & Contamination Protocol (`PILOT_DATASET_SCHEMA.md`)

**Project:** `kanglish-foss`  
**Document Version:** 1.0 (Phase 2)  
**Date:** 2026-10-18  
**Status:** Approved Specification  

---

## 1. Overview & Objectives

This specification defines the standard schema, storage format, and contamination-prevention protocol for the `kanglish-foss` dataset repository. 

The schema is designed to:
1. Provide a rigorous, version-controlled bitext corpus for Kanglish-to-English translation.
2. Track complete provenance and licensing for every single row to ensure commercial viability and prevent legal contamination.
3. Differentiate between **human-written gold**, **transliterated spoken corpus data**, and **synthetic/templated pairs**.
4. Enforce strict split partitioning so that `test` and `dev` sets are never compromised by training leakage.

---

## 2. Storage Formats

To accommodate both lightweight standard-library Python scripts and larger modern data tooling, the dataset will be stored in two synchronized formats:
- **Primary Line-Oriented Format:** `data/corpus/kanglish_corpus_v1.jsonl` (UTF-8, one valid JSON object per line; easy to stream and inspect without memory overhead).
- **Tabular Export Format:** `data/corpus/kanglish_corpus_v1.csv` (UTF-8 with BOM `utf-8-sig`, standard RFC 4180 CSV for spreadsheet review).

---

## 3. Field Specification

Every entry in the corpus must conform to the following 11-field schema:

| Field Name | Type | Required? | Allowed Values / Description | Example |
| :--- | :---: | :---: | :--- | :--- |
| **`id`** | String | **Yes** | Unique primary key formatted as `KANG-{SPLIT}-{NUMBER:05d}`. Must be immutable. | `"KANG-TEST-00042"` |
| **`kanglish_input`** | String | **Yes** | The raw Romanized Latin-script Kannada sentence as written in chat/informal context. | `"ivattu lab ge hogbeka?"` |
| **`kannada_reference`** | String | *Optional* | The corresponding native Kannada script rendering (`U+0C80`–`U+0CFF`), if available. | `"ಇವತ್ತು ಲ್ಯಾಬ್‌ಗೆ ಹೋಗ್ಬೇಕಾ?"` |
| **`english_reference`** | String | **Yes** | Natural, fluent English translation in the appropriate informal/casual register. | `"Do we have to go to the lab today?"` |
| **`source`** | String | **Yes** | Short identifier of the provenance source: `human_gold_chat`, `in22_conv_derived`, `synthetic_gemini_reviewed`, `dakshina_derived`. | `"in22_conv_derived"` |
| **`source_url`** | String | **Yes** | Canonical URL, DOI, or repository path where the source text originated. | `"https://hf.co/datasets/ai4bharat/IN22-Conv"` |
| **`license`** | String | **Yes** | Exact declared license of the source: `CC0-1.0`, `CC-BY-4.0`, `Apache-2.0`, `CC-BY-SA-4.0`, or `CC-BY-NC-4.0`. | `"CC-BY-4.0"` |
| **`generation_method`** | String | **Yes** | Enum: `human_authored`, `corpus_transliterated`, `synthetic_llm_generated`, `synthetic_backtranslated`. | `"corpus_transliterated"` |
| **`review_status`** | String | **Yes** | Enum: `unreviewed`, `peer_reviewed_pass`, `native_linguist_verified`, `rejected`. | `"native_linguist_verified"` |
| **`split`** | String | **Yes** | Enum: `train`, `dev`, `test`. Once assigned to `test`, an item can never be reassigned. | `"test"` |
| **`notes`** | String | *Optional* | JSON-encoded string or text noting alternative translations, linguistic category, and slang tags. | `"category: questions, slang: none, alt: Do we need to visit the lab today?"` |

---

## 4. JSONL Example Representation

```json
{
  "id": "KANG-TEST-00015",
  "kanglish_input": "machha class start aaytha illva?",
  "kannada_reference": "ಮಚ್ಚಾ ಕ್ಲಾಸ್ ಸ್ಟಾರ್ಟ್ ಆಯ್ತಾ ಇಲ್ವಾ?",
  "english_reference": "Bro, has the class started or not?",
  "source": "human_gold_chat",
  "source_url": "internal/curated_bengaluru_chats",
  "license": "CC0-1.0",
  "generation_method": "human_authored",
  "review_status": "native_linguist_verified",
  "split": "test",
  "notes": "slang: machha (buddy/bro), category: polar_question, alt: Buddy, did class start or not?"
}
```

---

## 5. Deduplication & Normalization Protocol

Because Romanized Kannada lacks standardized spelling, surface-level string deduplication is insufficient. Two messages can be identical in meaning despite different orthography (e.g. *barthira* vs *bartira* vs *barteera*).

### Normalization Pipeline for Deduplication:
```
[Raw Kanglish Input]
         │
         ▼
 1. Unicode NFKC Normalization & Lowercasing
         │
         ▼
 2. Punctuation & Whitespace Compression (Strip non-alphanumeric except apostrophes)
         │
         ▼
 3. Phonetic Character Normalization (Mapping common variants: 'ee'->'i', 'oo'->'u', 'th'->'t', 'dh'->'d')
         │
         ▼
 4. Canonical Hash Generation (SHA-256 fingerprint of normalized string)
```

### Deduplication Rules:
1. **Exact Duplicate Rule:** If `SHA-256(canonical(kanglish_input))` matches an existing row, the duplicate is flagged. If the translations are identical, it is merged. If translations differ, it is flagged for manual disambiguation.
2. **Translation Duplicate Rule:** If `canonical(english_reference)` is identical and Levenshtein similarity of `kanglish_input` exceeds $85\%$, it is treated as a duplicate variation and isolated into the same split.

---

## 6. Train / Dev / Test Leakage & Contamination Prevention

Contamination is the greatest threat to valid machine learning evaluation. To guarantee that evaluation metrics reflect true generalization:

### Rule 1: Strict Partitioning by Canonical Cluster
All spelling variations of an identical sentence (e.g. *"naale bartiya?"*, *"naale barthiya?"*, *"nale bartiya?"*) belong to the **same cluster** and **must reside in the exact same split**. Never place one variation in `train` and another in `test`.

### Rule 2: Prompt Few-Shot Blacklist
All sentences used as in-context learning prompts in any script or model card must be logged in `data/corpus/leakage_blacklist.txt`.
- Current blacklisted items:
  - `eno maadtidya?`
  - `nanna jothe bartiya?`
  - `oota aitha?`
  - `naale college ge barthira?`
  - `yenu guru ivattu plan?`
  - `sakkath aagide`
  - All 8 sentences from `test_generalization.py`

Any row matching any blacklisted sentence is permanently barred from the `test` and `dev` splits.

### Rule 3: Split Ratio Guidelines
For the full corpus:
- **`train`:** $70\%$
- **`dev`:** $15\%$ (Used for hyperparameter search, prompt engineering, and glossary expansion)
- **`test`:** $15\%$ (Locked, held-out benchmark. Run **only** for final reporting).

---

## 7. Licensing & Commercial Provenance Tracking

To ensure that `kanglish-foss` can eventually be released under an unencumbered permissive open-source license (e.g. MIT or Apache-2.0):

1. **Tag Inherited Restrictions:** Any data derived from `ai4bharat/samanantar` must be tagged as `CC-BY-NC-4.0`.
2. **Quarantine Non-Commercial Data:** Non-commercial data may only be placed in an isolated directory (`data/corpus/non_commercial/`) and must **never be mixed with the core Apache-2.0 dataset**.
3. **Verified Safe Upstreams:**
   - `ai4bharat/IN22-Conv`: `CC-BY-4.0` (Permissive with attribution).
   - `ai4bharat/Aksharantar`: `CC0` and `CC-BY-4.0` (Permissive).
   - `ramachandrajoshi/english-kannada-cleaned`: `Apache-2.0` (Permissive).
   - Human-authored gold chat sentences: Dedicated by author under `CC0-1.0` (Public Domain).
