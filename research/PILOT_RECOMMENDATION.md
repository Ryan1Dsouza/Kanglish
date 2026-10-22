# Pilot Dataset Recommendation & Implementation Plan (`PILOT_RECOMMENDATION.md`)

**Project:** `kanglish-foss`  
**Document Version:** 1.0 (Phase 2)  
**Date:** 2026-10-18  
**Status:** Ready for Implementation  

---

## 1. Executive Summary & Recommended Scope

Before attempting any fine-tuning or scaling up data collection, we propose constructing a **high-quality, fully reviewed pilot dataset of 250 sentence pairs**. 

This pilot serves two vital functions:
1. It immediately provides an **uncorrupted, held-out 100-sentence benchmark** to replace the saturated 3-row test file (`data/test.csv`).
2. It tests and validates the data collection, transliteration, deduplication, and human review pipeline on a manageable scale before scaling to thousands of examples.

---

## 2. Dataset Partitioning & Split Allocation

The 250 items will be partitioned into three strictly isolated splits:

| Split | Target Volume | Purpose | Contamination Constraint |
| :--- | :---: | :--- | :--- |
| **`test`** | **100 pairs** | Locked, uncorrupted evaluation benchmark. Run only for formal evaluation. | Permanent lock. Never exposed in prompt few-shots or training. |
| **`dev`** | **50 pairs** | Validation set used for error analysis, prompt iteration, and glossary expansion. | Isolated from training; used to calibrate thresholds. |
| **`train`** | **100 pairs** | Pilot training set for prompt few-shot pools and early LoRA feasibility testing. | Completely disjoint from `test` and `dev`. |

---

## 3. Three-Tier Data Provenance & Composition

To guarantee linguistic authenticity while maintaining strict licensing hygiene, the pilot is composed across three clearly distinguishable tiers:

```
                            ┌──────────────────────────────────────┐
                            │    Pilot Dataset (250 Pairs)         │
                            └──────────────────┬───────────────────┘
                                               │
             ┌─────────────────────────────────┼────────────────────────────────┐
             ▼                                 ▼                                ▼
┌───────────────────────────┐     ┌───────────────────────────┐     ┌───────────────────────────┐
│  Tier 1: Human-Authored   │     │  Tier 2: Transliterated   │     │  Tier 3: Targeted         │
│  Gold Chat (75 pairs)     │     │  IN22-Conv (100 pairs)    │     │  Synthetics (75 pairs)    │
│  - Real Bengaluru campus  │     │  - Real spoken dialogue   │     │  - Tense, negation, and   │
│  - Native chat slang      │     │  - Human English bitext   │     │    slang disambiguation   │
│  - License: CC0-1.0       │     │  - License: CC-BY-4.0     │     │  - License: CC0-1.0       │
└───────────────────────────┘     └───────────────────────────┘     └───────────────────────────┘
```

### Tier 1: Human-Authored Gold Campus Chat (75 Sentence Pairs — 30%)
- **Source:** Written directly by native/fluent Kannada speakers familiar with Bengaluru college group chats.
- **Coverage:** Authentic casual messaging, campus slang (*maga*, *guru*, *machha*, *scene*, *meter*, *chindi*), informal requests, campus logistics.
- **License:** Contributed under **`CC0-1.0` (Public Domain)**.
- **Generation Method:** `human_authored`.

### Tier 2: Transliterated Spoken Dialogue from `IN22-Conv` (100 Sentence Pairs — 40%)
- **Source:** Extracted from the conversational benchmark `ai4bharat/IN22-Conv` (mirrored openly at `mteb/IN22-Conv`).
- **Why This Is Robust:** 
  - `IN22-Conv` already contains **human-certified English reference translations** (`eng_Latn`) paired with **spoken Kannada sentences** (`kan_Knda`).
  - There is **zero English hallucination risk** because the English text is verified human translation.
  - The native Kannada spoken sentences (e.g. *"ಅಮ್ಮಾ, ನಾಳೆ ನಾವು ಸಿನ್ಮಾ ನೋಡಕ್‌ ಹೋಗಣ"*) are converted to Romanized Kanglish (*"Amma, naale naavu cinema nodok hogona"*) using rule-based transliteration.
- **License:** **`CC-BY-4.0`** (Fully permissive open-source with attribution).
- **Generation Method:** `corpus_transliterated`.

### Tier 3: Controlled Linguistic Synthetics & Disambiguation (75 Sentence Pairs — 30%)
- **Source:** Targeted synthetic sentence pairs designed to probe specific failure modes observed during Phase 1:
  - **Negation variations:** Testing `illa` (absence) vs `beda` (don't want) vs `alla` (not that) vs `aagalla` (cannot).
  - **Slang disambiguation:** Disambiguating `guru` (bro vs spiritual teacher) and `meter` (guts vs electrical meter).
  - **Subject/Honorific forms:** Comparing informal `bartiya?` vs polite `barthira?`.
- **License:** **`CC0-1.0`**.
- **Generation Method:** `synthetic_templated` (independently validated).

---

## 4. Proper Use of `ai4bharat/Aksharantar`

A major point clarified during our Hugging Face audit:
> **`ai4bharat/Aksharantar` is a word-level transliteration corpus (2.9M Kannada word pairs), NOT a sentence translation corpus.**

### How Aksharantar IS Used:
- **Phonetic Spelling Generator:** When converting native Kannada sentences from `IN22-Conv` into Romanized Kanglish, `Aksharantar` provides real, human-verified phonetic spelling variations.
  - E.g. For `ಮಾಡಬೇಕು`, Aksharantar lists `["madbeku", "maadabeku", "maadbeku"]`.
- **Lexical Coverage Checker:** Cross-referencing our vocabulary against Aksharantar's 2.9M pairs ensures that regional spelling variants are accounted for.

### How Aksharantar is NOT Used:
- It is **never** used to generate sentence-level English meanings (it only maps Roman letters to Kannada letters, not Kannada to English).

---

## 5. Review & Quality Assurance Protocol

To prevent self-confirming model loops, the following review standards are mandatory:

1. **Anti-Circular Validation Rule:** Under no circumstances may an LLM evaluated on this benchmark be used to generate or validate its own ground truth.
2. **Native Review Requirement:** Every synthetic or transliterated pair must receive `native_linguist_verified` status before being promoted into the `test` or `dev` split.
3. **Acceptable Alternatives Annotation:** Translators must supply at least one acceptable alternative translation in the `notes` column for any colloquial or slang sentence.

---

## 6. Illustrative 20-Sentence Pilot Sample

Below is an illustrative cross-section of the pilot dataset across the 3 tiers, adhering strictly to `PILOT_DATASET_SCHEMA.md`:

| ID | Split | Tier | Kanglish Input | Kannada Script Reference | English Reference Translation | Notes / Slang |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| `KANG-TEST-00001` | `test` | Tier 1 (Human) | `maga ivattu lab ge barthiya?` | ಮಗ ಇವತ್ತು ಲ್ಯಾಬ್‌ಗೆ ಬರ್ತಿಯಾ? | Are you coming to the lab today, dude? | slang: maga (dude), alt: Bro, will you come to the lab today? |
| `KANG-TEST-00002` | `test` | Tier 1 (Human) | `machha canteen ge hogona baa` | ಮಚ್ಚಾ ಕ್ಯಾಂಟೀನ್‌ಗೆ ಹೋಗೋಣ ಬಾ | Bro, let's go to the canteen, come on. | slang: machha (bro/buddy), category: invitation |
| `KANG-TEST-00003` | `test` | Tier 1 (Human) | `guru project submission yavaga?` | ಗುರು ಪ್ರಾಜೆಕ್ಟ್ ಸಲ್ಲಿಕೆ ಯಾವಾಗ? | Bro, when is the project submission? | slang: guru (bro), category: wh_question |
| `KANG-TEST-00004` | `test` | Tier 1 (Human) | `ivattu attendance tumba strict ide` | ಇವತ್ತು ಅಟೆಂಡೆನ್ಸ್ ತುಂಬಾ ಸ್ಟ್ರಿಕ್ಟ್ ಇದೆ | Attendance is very strict today. | category: code_mixed |
| `KANG-TEST-00005` | `test` | Tier 1 (Human) | `ninna internal marks score yeshtu?` | ನಿನ್ನ ಇಂಟರ್ನಲ್ ಮಾರ್ಕ್ಸ್ ಸ್ಕೋರ್ ಎಷ್ಟು? | What is your internal marks score? | category: college_academics |
| `KANG-TEST-00006` | `test` | Tier 1 (Human) | `avanige meter illa maga, hogalla` | ಅವನಿಗೆ ಮೀಟರ್ ಇಲ್ಲ ಮಗ, ಹೋಗಲ್ಲ | He has no guts dude, he won't go. | slang: meter illa (no courage/guts) |
| `KANG-TEST-00007` | `test` | Tier 1 (Human) | `chindi aagide boss presentation` | ಚಿಂದಿ ಆಗಿದೆ ಬಾಸ್ ಪ್ರೆಸೆಂಟೇಶನ್ | The presentation was fantastic, boss! | slang: chindi (superb/awesome) |
| `KANG-TEST-00008` | `test` | Tier 2 (IN22) | `amma, naale naavu cinema nodok hogona` | ಅಮ್ಮಾ, ನಾಳೆ ನಾವು ಸಿನ್ಮಾ ನೋಡಕ್‌ ಹೋಗಣ. | Mom, let's go for a movie tomorrow. | source: IN22-Conv, colloquial spoken |
| `KANG-TEST-00009` | `test` | Tier 2 (IN22) | `nange ivattu school illa` | ನಂಗೆ ಇವತ್ತು ಸ್ಕೂಲಿಲ್ಲ. | I don't have school today. | source: IN22-Conv, contraction: school illa |
| `KANG-TEST-00010` | `test` | Tier 2 (IN22) | `naale college rajeyide` | ನಾಳೆ ಕಾಲೇಜು ರಜೆಯಿದೆ. | Tomorrow is a college holiday. | source: IN22-Conv |
| `KANG-TEST-00011` | `test` | Tier 2 (IN22) | `neenu coffee kuditiya athva tea na?` | ನೀನು ಕಾಫಿ ಕುಡಿತೀಯಾ ಅಥವಾ ಟೀನಾ? | Will you drink coffee or tea? | source: IN22-Conv, alternative question |
| `KANG-TEST-00012` | `test` | Tier 2 (IN22) | `nanna bag alli pusthaka ide` | ನನ್ನ ಬ್ಯಾಗ್‌ನಲ್ಲಿ ಪುಸ್ತಕ ಇದೆ. | The book is in my bag. | source: IN22-Conv, location: ide |
| `KANG-TEST-00013` | `test` | Tier 2 (IN22) | `avaru yaavaga illige barthare?` | ಅವರು ಯಾವಾಗ ಇಲ್ಲಿಗೆ ಬರ್ತಾರೆ? | When will they come here? | source: IN22-Conv, respectful 3rd person |
| `KANG-TEST-00014` | `test` | Tier 3 (Synthetic) | `nange aa book beda, bere kodi` | ನನಗೆ ಆ ಪುಸ್ತಕ ಬೇಡ, ಬೇರೆ ಕೊಡಿ. | I don't want that book, give me another one. | category: negation (beda = don't want) |
| `KANG-TEST-00015` | `test` | Tier 3 (Synthetic) | `idu nanna pen alla, avanadhu` | ಇದು ನನ್ನ ಪೆನ್ ಅಲ್ಲ, ಅವನದು. | This is not my pen, it is his. | category: negation (alla = not that) |
| `KANG-TEST-00016` | `test` | Tier 3 (Synthetic) | `nanage ee vishaya gottilla guru` | ನನಗೆ ಈ ವಿಷಯ ಗೊತ್ತಿಲ್ಲ ಗುರು. | I don't know about this matter, bro. | category: negation (gottilla = don't know) |
| `KANG-TEST-00017` | `test` | Tier 3 (Synthetic) | `naale nanindha barokke aagalla` | ನಾಳೆ ನನ್ನಿಂದ ಬರೋಕೆ ಆಗಲ್ಲ. | I cannot make it tomorrow. | category: negation (aagalla = cannot) |
| `KANG-TEST-00018` | `test` | Tier 3 (Synthetic) | `sir swalpa adjust maadi please` | ಸರ್ ಸ್ವಲ್ಪ ಅಡ್ಜಸ್ಟ್ ಮಾಡಿ ಪ್ಲೀಸ್. | Sir, please adjust and accommodate a little. | idiom: adjust maadi, polite request |
| `KANG-TEST-00019` | `test` | Tier 3 (Synthetic) | `cab book aagide, five minutes alli baratte` | ಕ್ಯಾಬ್ ಬುಕ್ ಆಗಿದೆ, ಐದು ನಿಮಿಷದಲ್ಲಿ ಬರುತ್ತೆ. | The cab is booked, it will arrive in five minutes. | category: code_mixed verbs |
| `KANG-TEST-00020` | `test` | Tier 3 (Synthetic) | `neevu naale office ge barthira sir?` | ನೀವು ನಾಳೆ ಆಫೀಸ್‌ಗೆ ಬರ್ತೀರಾ ಸರ್? | Are you coming to the office tomorrow, sir? | category: polite 2nd person (barthira) |

---

## 7. Next Recommended Actions

With the benchmarking and pilot schemas formally documented:
1. **Curate the 100-sentence Benchmark (`data/benchmark_test_v1.csv`):** Assemble the complete 100 held-out sentences conforming to `PILOT_DATASET_SCHEMA.md`.
2. **Develop the Benchmark Runner (`scripts/benchmark.py`):** Adapt the scoring logic from `scripts/score.py` to evaluate models across all 8 linguistic categories and generate category-level breakdown reports.
3. **Execute the Baseline vs Glossary Evaluation:** Benchmark the local `qwen2.5:3b` and `gemma2:2b` models across the 100 test sentences to establish the genuine, statistically valid baseline for `kanglish-foss`.
