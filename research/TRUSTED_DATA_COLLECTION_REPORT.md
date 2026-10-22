# Trusted Data Collection & Governance Report for Kanglish FOSS

**Date:** Sun 10/18/2026
**Master Catalog Path:** `data/trusted/trusted_master.jsonl`
**Total Curated Records:** 172,140

---

## 1. Executive Summary & Architecture
To ground the Kanglish-to-English translation pipeline in authenticated lexical, transliteration, conversational, and slang data, we established a **governed, provenance-preserving data collection pipeline**.

### Core Guarantees:
1. **Separation of Transliteration vs. Semantics (Rule 4):** Aksharantar mappings (`kan.zip`) are strictly categorized as `transliteration` with empty English meanings, preventing erroneous assumptions that Romanized script proves semantic translation.
2. **Provenance & License Preservation (Rule 3):** Every record retains explicit metadata: `source`, `license`, `attribution`, `source_url`, and `source_checksum`. Different licenses (`ODC-OdBL`, `CC-BY-4.0`, `CC0-1.0`) are kept in separate partitions and never commingled into an uncredited blob.
3. **No AI Meaning Marked as Human-Verified (Rule 8):** AI-generated or synthetic data is strictly prohibited from carrying `human-verified` status.
4. **Dual-Reviewer Gate for Slang Gold (Rule 8):** Slang and profanity terms require $\ge 2$ independent native-speaker checks (`reviewer_kannada_1`, `reviewer_kannada_2`) before achieving `human-verified` status. Single-reviewer terms are quarantined in `needs-human-review`.
5. **Isolation of External Candidates (Rule 5):** Easy Kannada Typing observations are stored in `data/candidates_unverified/` with low confidence (0.2) and zero repeated endpoint querying.
6. **Integrity of Protected Benchmarks (Rule 9):** Protected files (`benchmark_test_v1_draft.csv`, `eval.locked.csv`, `dev.csv`) were cryptographically verified and remain 100% untouched.

---

## 2. Row Counts and Coverage Breakdown

### By Data Source:
| Source | Data Domain | License | Row Count |
| :--- | :--- | :--- | :--- |
| `alar_kannada_english_dict` | Direct source | Tracked | 156,620 |
| `bpcc_h_daily_conversational` | Direct source | Tracked | 8,484 |
| `aksharantar_transliteration` | Direct source | Tracked | 7,025 |
| `curated_street_slang_gold` | Direct source | Tracked | 11 |

### By Data Type:
| Data Type | Description | Count |
| :--- | :--- | :--- |
| `lexicon` | Verified partition | 156,620 |
| `conversational` | Verified partition | 8,484 |
| `transliteration` | Verified partition | 7,025 |
| `slang_profanity` | Verified partition | 11 |

### By Review Status (Lifecycle Enforcement):
| Review Status | Description | Count |
| :--- | :--- | :--- |
| `raw` | Status gate | 172,129 |
| `human-verified` | Status gate | 10 |
| `needs-human-review` | Status gate | 1 |

### Isolated Unverified Candidates (Rule 5):
- **Candidate File:** `data/candidates_unverified/easy_kannada_candidates.csv`
- **Total Quarantined Entries:** 3
- **Status:** `needs-human-review`, Confidence: `0.20`, Zero endpoint requests.

---

## 3. Ambiguity & Polysemy Detection
A total of **226 records** were automatically flagged for contextual polysemy review:
- **`avatārika guru` (ಅವತಾರಿಕ ಗುರು)**: Slang address 'dude / bro', or literal 'teacher / master' (ಗುರು).
- **`ide` (ಇಡೆ)**: Can mean 'there is / present', or the English loanword 'idea'.
- **`ide` (ಇಡೆ)**: Can mean 'there is / present', or the English loanword 'idea'.
- **`ide` (ಇದೆ)**: Can mean 'there is / present', or the English loanword 'idea'.
- **`ide` (ಇದೆ)**: Can mean 'there is / present', or the English loanword 'idea'.
- **`ide` (ಇದೆ)**: Can mean 'there is / present', or the English loanword 'idea'.
- **`uttējana kodu` (ಉತ್ತೇಜನಕೊಡು)**: Can mean 'give' (ಕೊಡು) or 'horn' / 'branch' (ಕೋಡು / ಕೊಂಬು).
- **`oḷaśuṇthi kodu` (ಒಳಶುಂಠಿಕೊಡು)**: Can mean 'give' (ಕೊಡು) or 'horn' / 'branch' (ಕೋಡು / ಕೊಂಬು).

---

## 4. Licence Constraints & Attribution Table
| Dataset | License | Attribution Requirement | Downstream Reuse Constraint |
| :--- | :--- | :--- | :--- |
| **Alar Dictionary** | `ODC-OdBL-1.0` | `(c) V. Krishna / Alar project` | Derivative databases must remain ODC-OdBL; must retain attribution. |
| **BPCC-H-Daily** | `CC-BY-4.0` | `AI4Bharat / BPCC-H-Daily` | Credit AI4Bharat; commercial and academic reuse permitted. |
| **Aksharantar** | `CC0-1.0 / CC-BY-4.0` | `AI4Bharat / Aksharantar` | Public domain mined data / CC-BY on benchmark splits. |
| **Curated Slang** | `Community-Curated` | `Kanglish FOSS Community` | Dual native-speaker verified internal gold dataset. |
| **Easy Kannada Candidates** | `Proprietary-Isolated` | `External Web Observation` | Strictly quarantined; non-redistributable until permission verified. |

---

## 5. Next Actions
1. **Lexical Grounding Bridge:** Run phonetic join between Aksharantar transliteration roots and Alar English definitions to build high-confidence, verified Kanglish-English vocabulary lookup tables.
2. **Native Speaker Verification Queue:** Recruit a second native Kannada speaker to review pending slang (`SLANG-0011-PENDING`) and promote to gold.
3. **Conversational Synthesis with Provable Grounding:** Use BPCC conversational patterns grounded by Alar lexical definitions to generate grammatically varied training sets without ungrounded hallucinations.
