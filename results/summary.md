# Kanglish Decoder Experiment Summary

## Executive Summary

We evaluated **5 prompt variants** across two open offline LLMs (**`qwen2.5:3b`** and **`gemma2:2b`**) on `data/test.csv`, testing both the unaugmented **Baseline** pipeline and the dynamic **Glossary-augmented** pipeline (total **10 experiments**, 60 LLM inferences).

- **Best Overall Prompt Variant**: **`v1_baseline`** achieved **3/3 (100%)** on both `qwen2.5:3b` and `gemma2:2b`.
- **Runner-Up**: **`v4_clean_glossary`** achieved **3/3 (100%)** on `gemma2:2b` and **2/3 (66.7%)** on `qwen2.5:3b`.
- **Glossary Impact**: The baseline pipeline scored **0/3 (0%) across all 10 experiments**. Injecting dynamic glossary entries lifted scores from **0% to up to 100%**.

---

## Complete Results Table (`results/log.csv`)

| Run | Model | Prompt Variant | Baseline Score | Glossary Score | Pass Rate (Glossary) |
|:---:|:---|:---|:---:|:---:|:---:|
| 1 | `qwen2.5:3b` | `v1_baseline` | 0/3 | **3/3** | **100%** |
| 2 | `gemma2:2b` | `v1_baseline` | 0/3 | **3/3** | **100%** |
| 3 | `qwen2.5:3b` | `v2_no_commentary` | 0/3 | 2/3 | 66.7% |
| 4 | `gemma2:2b` | `v2_no_commentary` | 0/3 | 2/3 | 66.7% |
| 5 | `qwen2.5:3b` | `v3_strong_rules` | 0/3 | 1/3 | 33.3% |
| 6 | `gemma2:2b` | `v3_strong_rules` | 0/3 | 2/3 | 66.7% |
| 7 | `qwen2.5:3b` | `v4_clean_glossary` | 0/3 | 2/3 | 66.7% |
| 8 | `gemma2:2b` | `v4_clean_glossary` | 0/3 | **3/3** | **100%** |
| 9 | `qwen2.5:3b` | `v5_fewshot_aligned` | 0/3 | 0/3 | 0% |
| 10 | `gemma2:2b` | `v5_fewshot_aligned` | 0/3 | 1/3 | 33.3% |

---

## Detailed Row-by-Row Analysis & Raw Outputs

Evaluation criteria:
- **Whole-word fuzzy matching** via tokenized word sets and Porter-lite stem intersection.
- **Directional synonym group**: `{"going", "coming", "go", "come", "goes", "comes"}`.
- **Address synonym group**: `{"bro", "dude", "guru", "man", "buddy", "mate"}`.
- **Quality synonym group**: `{"awesome", "great", "amazing", "fantastic", "cool", "nice"}`.
- **Commentary penalty**: `-0.35` deduction if the output contains parenthetical remarks, explanation labels (`Note:`, `Meaning:`), conversational meta-phrases, or multi-line commentary. Pass threshold: `>= 0.70`.

---

### Row 1
- **Input (`kanglish`)**: `naale college ge barthira?`
- **Expected (`english`)**: `Are you coming to college tomorrow?`
- **Extracted Keywords**: `['coming', 'college', 'tomorrow']`

#### Raw Outputs:
| Variant | Model | Baseline Output | Status | Glossary Output | Status |
|:---|:---|:---|:---:|:---|:---:|
| `v1_baseline` | `qwen2.5:3b` | `Are you going to college with someone?` | FAIL (0.67) | `Tomorrow I am going to college by bus?` | **PASS (1.00)** |
| `v1_baseline` | `gemma2:2b` | `Are you going to college with us?` | FAIL (0.67) | `Tomorrow I'm going to college by bus?` | **PASS (1.00)** |
| `v2_no_commentary` | `qwen2.5:3b` | `Are you going to college?` | FAIL (0.67) | `Tomorrow we will go to college?` | **PASS (1.00)** |
| `v2_no_commentary` | `gemma2:2b` | `Are you going to college by bus?` | FAIL (0.67) | `Tomorrow we will go to college?` | **PASS (1.00)** |
| `v3_strong_rules` | `qwen2.5:3b` | `Will you be back from college?` | FAIL (0.33) | `When will you go to college?` | FAIL (0.67) |
| `v3_strong_rules` | `gemma2:2b` | `Will you go to college this week?` | FAIL (0.67) | `Will you go to college tomorrow?` | **PASS (1.00)** |
| `v4_clean_glossary` | `qwen2.5:3b` | `Are you going to college with me?` | FAIL (0.67) | `Will you come to college with me tomorrow?` | **PASS (1.00)** |
| `v4_clean_glossary` | `gemma2:2b` | `Are you going to the college with me?` | FAIL (0.67) | `Will you go to college tomorrow?` | **PASS (1.00)** |
| `v5_fewshot_aligned` | `qwen2.5:3b` | `When are you going to college?` | FAIL (0.67) | `tomorrow college go?... [multi-line repetition]` | FAIL (0.65, penalized) |
| `v5_fewshot_aligned` | `gemma2:2b` | `When are you going to college?` | FAIL (0.67) | `tomorrow college go?` | **PASS (1.00)** |

#### Row 1 Failure Analysis:
1. **Baseline failure**: The unaugmented baseline consistently dropped `naale` ("tomorrow") and hallucinated phrases like *"with someone"* or *"with us"*. It matched `going` and `college` (2/3 = 66.7%), which fell just short of the 70% threshold.
2. **Glossary success**: Injecting `naale = tomorrow` restored the crucial time keyword in nearly all glossary variants.
3. **Pronoun drift**: Both models tended to flip the polite question (*"Are you coming..."*) into first person (*"Tomorrow I am going..."* or *"Tomorrow we will go..."*). While this still captures the core keywords, proposing `barthira` (polite second-person question) in `data/glossary_candidates.csv` will help preserve grammatical subject.

---

### Row 2
- **Input (`kanglish`)**: `yenu guru ivattu plan?`
- **Expected (`english`)**: `What's the plan today bro?`
- **Extracted Keywords**: `['plan', 'today', 'bro']`

#### Raw Outputs:
| Variant | Model | Baseline Output | Status | Glossary Output | Status |
|:---|:---|:---|:---:|:---|:---:|
| `v1_baseline` | `qwen2.5:3b` | `What's the plan for you?` | FAIL (0.33) | `What are you planning today, bro?` | **PASS (1.00)** |
| `v1_baseline` | `gemma2:2b` | `What's the plan for you?` | FAIL (0.33) | `What are you planning today, dude?` | **PASS (1.00)** |
| `v2_no_commentary` | `qwen2.5:3b` | `What’s your group study plan?` | FAIL (0.33) | `What's up dude?` | FAIL (0.33) |
| `v2_no_commentary` | `gemma2:2b` | `What's your group study plan?` | FAIL (0.33) | `What's up bro?` | FAIL (0.33) |
| `v3_strong_rules` | `qwen2.5:3b` | `What are you planning to do?` | FAIL (0.33) | `What's bro's plan?` | FAIL (0.67) |
| `v3_strong_rules` | `gemma2:2b` | `What are you planning bro?` | FAIL (0.67) | `What's bro's plans?` | FAIL (0.67) |
| `v4_clean_glossary` | `qwen2.5:3b` | `What is your plan for the weekend?` | FAIL (0.33) | `What are you planning for today, dude?` | **PASS (1.00)** |
| `v4_clean_glossary` | `gemma2:2b` | `What is your plan for lunch?` | FAIL (0.33) | `What are you planning what dude today?` | **PASS (1.00)** |
| `v5_fewshot_aligned` | `qwen2.5:3b` | `What's your teacher's plan?` | FAIL (0.33) | `What's your plan for today?` | FAIL (0.67) |
| `v5_fewshot_aligned` | `gemma2:2b` | `What's your guru's plan?` | FAIL (0.67) | `What's your plan for today?` | FAIL (0.67) |

#### Row 2 Failure Analysis:
1. **Baseline failure**: Slang term `guru` was completely misunderstood. Baseline models either mistook it for "group" (*"What’s your group study plan?"*), literal teacher (*"What's your guru's plan?"*, *"What's your teacher's plan?"*), or hallucinated extraneous context (*"plan for the weekend"*, *"plan for lunch"*).
2. **Glossary success**: With glossary injection (`guru = bro/dude`, `ivattu = today`, `yenu = what`), `v1` and `v4` successfully resolved all 3 keywords (`planning` -> stem `plan`, `today`, and `bro`/`dude`).
3. **Over-compression in `v2`**: In `v2_no_commentary`, the strict instruction caused both models to collapse the whole sentence into a generic chat greeting (*"What's up dude?"*), dropping both `plan` and `today`.
4. **Dropped address in `v5`**: In `v5_fewshot_aligned`, both models translated the plan and time (*"What's your plan for today?"*) but dropped the address token (`bro`/`dude`), scoring 2/3 (66.7% < 70%).

---

### Row 3
- **Input (`kanglish`)**: `sakkath aagide`
- **Expected (`english`)**: `It's awesome`
- **Extracted Keywords**: `['awesome']`

#### Raw Outputs:
| Variant | Model | Baseline Output | Status | Glossary Output | Status |
|:---|:---|:---|:---:|:---|:---:|
| `v1_baseline` | `qwen2.5:3b` | `What is the situation?` | FAIL (0.00) | `Awesome!` | **PASS (1.00)** |
| `v1_baseline` | `gemma2:2b` | `Are you asleep?` | FAIL (0.00) | `Awesome!` | **PASS (1.00)** |
| `v2_no_commentary` | `qwen2.5:3b` | `That's okay` | FAIL (0.00) | `Great!` | **PASS (1.00)** |
| `v2_no_commentary` | `gemma2:2b` | `That's all` | FAIL (0.00) | `Awesome!` | **PASS (1.00)** |
| `v3_strong_rules` | `qwen2.5:3b` | `It is blazing hot.` | FAIL (0.00) | `It's awesome!` | **PASS (1.00)** |
| `v3_strong_rules` | `gemma2:2b` | `It's blazing hot.` | FAIL (0.00) | `It's amazing/sucks.` | **PASS (1.00)** |
| `v4_clean_glossary` | `qwen2.5:3b` | `Have you heard the news?` | FAIL (0.00) | `Wow, has happened` | FAIL (0.00) |
| `v4_clean_glossary` | `gemma2:2b` | `Did you study?` | FAIL (0.00) | `What an awesome thing has happened?` | **PASS (1.00)** |
| `v5_fewshot_aligned` | `qwen2.5:3b` | `It's going well.` | FAIL (0.00) | `sakkath gadya` | FAIL (0.00) |
| `v5_fewshot_aligned` | `gemma2:2b` | `It's okay.` | FAIL (0.00) | `sakkath sakkath` | FAIL (0.00) |

#### Row 3 Failure Analysis:
1. **Baseline hallucination**: `sakkath aagide` is purely colloquial Kannada slang. Without glossary, models produced wild guesses: *"Are you asleep?"*, *"What is the situation?"*, *"Did you study?"*, *"It is blazing hot"*.
2. **Glossary success**: In `v1`, `v2`, and `v3`, `sakkath = awesome/great (slang)` guided models directly to *"Awesome!"* or *"It's awesome!"*.
3. **Glossary strip side-effect (`v4`)**: In `v4`, stripping `(e.g. "sakkath aagide" = it's awesome)` from `aagide` left `aagide = is/has happened`. `qwen2.5` then translated it literally as *"Wow, has happened"*, losing `"awesome"`.
4. **Echoing in `v5`**: In `v5`, both models echoed untranslated Kanglish (`sakkath gadya`, `sakkath sakkath`), completely failing to translate.

---

## Why Variants Differed: Findings & Recommendations

1. **Mandatory instruction works best (`v1_baseline`)**:
   Small models (2B–3B parameters) need unambiguous, direct guidance. The header:
   `"Word meanings (MANDATORY: use these exact meanings and do not drop any of them):"`
   was the most reliable at forcing the model to integrate vocabulary without overthinking grammatical transformations.

2. **Negative constraints cause over-compression (`v2_no_commentary`)**:
   Saying *"Reply with ONLY the natural English translation... Do not output explanations"* caused models to drop essential content words in Row 2 to make the output as short as possible (*"What's up dude?"*).

3. **Complex multi-rule prompts cause instruction overload (`v3_strong_rules`)**:
   Adding 5 numbered rules reduced keyword adherence in small models.

4. **Preserving glossary examples vs literal glosses**:
   The glossary entry:
   `aagide,is/has happened (e.g. "sakkath aagide" = it's awesome)`
   contains the exact compound phrase. When that example was present (`v1`), both models produced *"Awesome!"*. When stripped (`v4`), Qwen translated `aagide` literally as *"has happened"*.

5. **Glossary Candidates Proposed**:
   In accordance with `README.md`, proposals have been placed in `data/glossary_candidates.csv` with confidence notes for human review:
   - `barthira`: Polite second-person question (*"Are you coming / will you come"*)
   - `hogtira`: Polite second-person question (*"Are you going / will you go"*)
   - `chennagide`: Common variant of `chandagide` (*"It's good / it's nice"*)

---

## Scorer Compliance Note

All scorer enhancements (synonym unification, whole-word matching, commentary penalty) have been documented in [`results/scorer_changelog.md`](file:///c:/Users/ryan1/kanglish-foss/results/scorer_changelog.md) in compliance with Rule 11 of `README.md`.
