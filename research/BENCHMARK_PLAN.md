# Kanglish Evaluation Benchmark Plan (`BENCHMARK_PLAN.md`)

**Project:** `kanglish-foss`  
**Document Version:** 1.0 (Phase 2)  
**Date:** 2026-10-18  
**Status:** Approved for Implementation  

---

## 1. Executive Summary & Purpose

The goal of `kanglish-foss` is to provide a reliable, offline-first decoder for Romanized Kannada (Kanglish) chat messages. 

To date, development has relied on a 3-row sanity check (`data/test.csv`). While achieving a 100% (3/3) pass rate on that file demonstrates that dynamic glossary injection is functioning, **a 3-sentence test cannot be reported as real-world accuracy**. A 3-sentence sample has near-zero statistical confidence, covers less than 1% of conversational syntax, and suffers from heavy development exposure.

This document establishes a **comprehensive, uncorrupted evaluation benchmark** (target: 100–150 held-out test items) covering authentic Bangalore college chat, slang, code-mixed English, tense, negation, grammatical person, and pragmatic ambiguity.

---

## 2. Contamination & Exposure Audit of Existing Assets

Before constructing a clean benchmark, we must identify and quarantine every sentence and lexical pattern that has already been exposed during Phase 1 prompt engineering and glossary tuning.

### Saturated Assets (Must be Quarantined from the Benchmark):

| Asset Source | Exposed Sentences / Phrases | Why It Is Contaminated |
| :--- | :--- | :--- |
| **`data/test.csv`** | 1. `naale college ge barthira?`<br>2. `yenu guru ivattu plan?`<br>3. `sakkath aagide` | Used repeatedly to tune prompt instructions, `score.py` synonym maps, and whole-word matching thresholds. **Must remain strictly a regression test, not the benchmark.** |
| **`scripts/baseline.py` & `glossary_run.py`** | 1. `eno maadtidya?` → *What are you doing?*<br>2. `nanna jothe bartiya?` → *Will you come with me?*<br>3. `oota aitha?` → *Did you eat?* | Saturated as few-shot in-context learning prompts. Any model evaluated on these exact items will have prompt leakage. |
| **`test_glossary.py`** | Direct inclusion of `test.csv` rows in prompt few-shots. | Prompt context incorporates the test inputs directly. |
| **`test_generalization.py`** | 1. `naale barthini`<br>2. `maga illi baa`<br>3. `ivattu class ide`<br>4. `guru scene enu?`<br>5. `tumba chennagide`<br>6. `ninne movie nodide`<br>7. `oota aaytha?`<br>8. `swalpa wait maadu` | Directly influenced manual additions in `data/glossary.csv` (lines 47–62), creating memorized dictionary mappings. |
| **`data/glossary.csv` (lines 58–62)** | Multi-word phrase entries: *"There's class today"*, *"Bro, what's the plan?"*, *"Wait a little"*, etc. | Evaluates memorized phrase lookup rather than compositional language understanding. |

> **Contamination Rule:** None of the 14 sentences above may be included in the new benchmark dataset. The benchmark must be strictly held-out.

---

## 3. Linguistic Dimensions of Coverage

The benchmark will evaluate 8 core linguistic axes representative of real-world Bangalore college and WhatsApp group messaging:

```
                          ┌─────────────────────────────────────┐
                          │     Kanglish Benchmark Axes         │
                          └──────────────────┬──────────────────┘
                                             │
      ┌──────────────────┬───────────────────┼───────────────────┬──────────────────┐
      ▼                  ▼                   ▼                   ▼                  ▼
┌──────────────┐  ┌──────────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────┐
│  Everyday    │  │  Bangalore   │   │  Code-Mixed  │   │  Grammar:     │   │  Negation &  │
│ Conversation │  │  Slang &     │   │  English     │   │  Tense, Person│   │  Ambiguity   │
│ & Greetings  │  │  Address     │   │  Nouns/Verbs │   │  & Question   │   │  Resolution  │
└──────────────┘  └──────────────┘   └──────────────┘   └───────────────┘   └──────────────┘
```

### Axis 1: Everyday Conversation & Social Interaction (15%)
- Greetings, plans, meeting up, food, campus logistics.
- *Examples:*
  - `ivattu canteen ge hogona?` (Shall we go to the canteen today?)
  - `class start aaytha?` (Has the class started?)
  - `assignment submission yavaga?` (When is the assignment submission?)

### Axis 2: Bangalore Slang & Terms of Address (20%)
- Slang terms that models frequently mistranslate literally or fail on:
  - Address: `guru` (bro/dude, not spiritual teacher), `maga` (dude/bro, not son), `machha` (buddy), `bro/man`.
  - Quality/State: `chindi` (superb/torn), `sakkath` (awesome), `khatarnak` (crazy/intense), `bombat` (excellent).
  - Colloquial idioms: `scene enu` (what's the plan/drama?), `meter illa` (no courage/guts), `meter jaasti` (too confident), `adjust maadi` (please accommodate/adjust).

### Axis 3: Code-Mixed English with Kannada Inflections (20%)
- English root verbs and nouns with Kannada case endings and verbal suffixes:
  - Dative suffix `-ge`: `lab ge` (to the lab), `project ge` (for the project).
  - Instrumental/Ablative `-inda`: `bus inda` (by bus), `sir inda` (from sir).
  - English verbs + `maadu` (do): `call maadu` (call me), `book maadu` (book it), `submit madtiya?` (will you submit?).
  - English verbs + `aagide` (happened): `cancel aagide` (it is cancelled), `upload aagilla` (it has not uploaded).

### Axis 4: Questions & Sentence Types (15%)
- Polar (Yes/No) questions formed with suffixes:
  - Informal 2nd person: `bartiya?` (Will you come?), `madtidya?` (Are you doing it?).
  - Polite / Plural 2nd person: `barthira?` (Are you coming?), `hogtira?` (Will you go?).
  - Completion suffix `-aaytha?`: `oota aaytha?` (Had food?), `project mugitha?` (Is the project finished?).
- Wh-Content questions:
  - `yenu` (what), `yaaru` (who), `yelli` (where), `yaake` (why), `yaavaga` (when), `yeshtu` (how much / how many), `hege` (how).

### Axis 5: Grammatical Person & Honorific Registers (10%)
- Models frequently drift between 1st and 2nd person. The benchmark must test:
  - 1st Person: `naanu baralla` (I will not come), `naavu hogona` (Let us go).
  - 2nd Person Informal: `neenu baa` (You come), `ninna kelsa aaytha?` (Is your work done?).
  - 2nd Person Polite/Plural: `neevu barthira?` (Are you coming?), `nimma phone kodi` (Please give your phone).
  - 3rd Person Respectful: `avru helidru` (They / he / she said).

### Axis 6: Tense & Aspect Consistency (10%)
- Past: `ninne nodide` (I saw yesterday), `aaytu` (done), `bandru` (they came).
- Present Continuous: `madtidini` (I am doing), `bartidare` (they are coming).
- Future / Intended: `naale madteeni` (I will do tomorrow), `hogbeku` (have to go).

### Axis 7: Negation & Rejection (10%)
- Distinct forms of negation in Kannada that trip up basic decoders:
  - Non-existence / Absence: `illa` (not there / no / haven't).
  - Rejection / Negative desire: `beda` (don't want / no need).
  - Categorical identity negation: `alla` (is not that).
  - Capability negation: `aagalla` (cannot happen / not possible).
  - Knowledge negation: `gottilla` (don't know).
  - Obligation negation: `bekagilla` (not needed).

---

## 4. Multi-Reference Ground Truth Design

Kanglish conversations have multiple valid translations depending on register and regional phrasing. A single rigid reference translation unfairly penalizes good model outputs.

Every benchmark row will have:
1. **Primary Reference (`primary_reference`)**: Natural, contemporary conversational English.
2. **Acceptable Alternatives (`acceptable_alternatives`)**: Semantically valid variations (e.g. *"What's the plan, dude?"* vs *"What's the plan, bro?"* vs *"What are you planning today, man?"*).
3. **Disallowed Traps (`disallowed_traps`)**: Literal mistakes that basic decoders make (e.g. translating `guru` as "teacher", or `maga` as "my son").

---

## 5. Quantitative Evaluation Metrics & Scoring Rubric

To evaluate models objectively without human intervention for every run, the benchmark uses a multi-faceted metric:

```
Total Item Score = [Semantic Keyword Match (0.0–1.0)] 
                   × [Grammar & Intent Penalty (0.0 or 1.0)] 
                   - [Commentary Penalty (0.35)]
```

### 1. Semantic Keyword & Stem Match (Fuzzy Whole-Word)
- Extracts core content keywords from references (filtering stop-words).
- Matches whole-word tokens against stems and curated synonym clusters (`bro` = `dude` = `guru` = `man`).
- Item passes if matched keyword ratio is **$\ge 70\%$**.

### 2. Intent & Polarity Preservation
- **Question Preservation:** If input ends with `?` or interrogative particle, output MUST end with `?` or be a valid question. Flipping a question into a statement (*"You are coming tomorrow."*) fails.
- **Polarity Preservation:** If input is negative (`illa`, `beda`, `aagalla`), output MUST contain negation (`not`, `no`, `don't`, `cannot`). Flipping negation fails.
- **Person Preservation:** If input asks 2nd person (`-ira?`), output cannot drift into 1st person statement (*"Tomorrow I am going"*).

### 3. Commentary & Noise Penalty (Strict 0.35 Deduction)
- Outputs must be clean translations. 
- Penalized if containing:
  - Parenthetical notes: `(asking about attendance)`
  - Explanatory labels: `Note:`, `Translation:`, `Meaning:`
  - Meta-commentary: `Here is the English translation...`
  - Multi-line repetitions or untranslated Kanglish echoes.

---

## 6. Reproducible Comparison Protocol

The benchmark script will automate a rigorous head-to-head comparison:

```bash
# Evaluation run command
python scripts/benchmark.py --models qwen2.5:3b gemma2:2b --output results/benchmark_run.csv
```

### Evaluation Protocol:
1. **Model A (Baseline):** Raw prompt without glossary hints. Temperature = 0 (deterministic).
2. **Model B (Glossary-Augmented):** Prompt with dynamic glossary injection (`v1_baseline` header). Temperature = 0.
3. **Statistical Reporting:**
   - Total items ($N \ge 100$).
   - Accuracy by category (Slang, Negation, Tense, Code-mixing).
   - $95\%$ Wilson Score Confidence Intervals.
   - P-value (McNemar's test for paired categorical data) to verify if glossary augmentation yields a statistically significant improvement over baseline.

---

## 7. IndicXlit + IndicTrans2 Comparison Roadmap

As established in `research/HUGGINGFACE_AUDIT.md`, `ai4bharat/indictrans2-indic-en-dist-200M` cannot directly decode Romanized Latin Kanglish. However, it can be tested in a **Two-Stage Pipeline**:

```
[Raw Kanglish] ──▶ [IndicXlit (138MB)] ──▶ [Kannada Script] ──▶ [IndicTrans2 (200M)] ──▶ [English Translation]
```

### Roadmap to Run This Later:
1. **Dependency Isolation:** 
   - `IndicTrans2` requires `torch`, `transformers`, `sentencepiece`, and `IndicTransToolkit`.
   - To keep `kanglish-foss` dependency-free, this will be placed in an optional virtual environment / evaluation sub-module (`benchmarks/indictrans/`), keeping core scripts stdlib-only.
2. **Licensing & Access:**
   - Both `IndicXlit` and `IndicTrans2` are **MIT licensed** (commercially safe).
   - `IndicTrans2` is gated on Hugging Face; the user's `@Ryan1Dsouza` token provides automated access.
3. **Expected Trade-Offs to Measure:**
   - **Advantage:** Dedicated encoder-decoder translation trained on 230M sentences.
   - **Disadvantage:** Two inference steps (higher latency); phonetic transliteration mistakes in Stage 1 compound into mistranslations in Stage 2.
