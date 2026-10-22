# Phase 3 Repair Report (`research/PHASE3_REPAIR_REPORT.md`)

**Project:** `kanglish-foss`
**Date:** 2026-10-18
**Triggered by:** Post-implementation audit of benchmark_test_v1_draft.csv and
scripts/benchmark.py following their initial generation.

---

## 1. Files Changed

| File | Change Type | Summary |
|---|---|---|
| `data/benchmark_test_v1_draft.csv` | Modified | Fixed provenance (all 100 rows), 10 row-level corrections |
| `scripts/benchmark.py` | Rewritten | Full safeguard overhaul (see section 3) |
| `data/corpus/leakage_blacklist.txt` | Unchanged | Already correct |
| `research/BENCHMARK_REVIEW_ISSUES.md` | Created | Audit findings per row |
| `research/PHASE3_REPAIR_REPORT.md` | Created | This file |

**Files NOT touched (per user instruction):**
`data/test.csv`, `data/glossary.csv`, `scripts/score.py`,
`scripts/baseline.py`, `scripts/glossary_run.py`

---

## 2. Dataset Corrections

### 2a. Provenance (ALL 100 rows)

Every row previously claimed:
```
provenance=human_gold_chat
source_url=internal/curated_bengaluru_chats
license=CC0-1.0
```

All three fields were false. The examples were AI-generated.
`CC0-1.0` requires a human author. The source path does not exist.

**Corrected to:**
```
provenance=synthetic_draft_ai_generated
source_url=  (empty)
license=unlicensed-draft
review_status=unreviewed  (unchanged)
```

### 2b. Row-level corrections

| Row ID | Severity | What was wrong | What was done |
|---|---|---|---|
| KANG-TEST-00014 | **A** | `hotte` = stomach, NOT late/delayed. Reference "How late has the meeting gotten?" was factually wrong. | Input changed to `meeting yeshtu late aagide?`; reference corrected. |
| KANG-TEST-00046 | **A** | `naale` = tomorrow. Reference said "yesterday" — a direct contradiction. The disallowed_traps column even said `naale=tomorrow` is the error, yet the reference made that same error. | Reference corrected to "Will you skip class tomorrow?" |
| KANG-TEST-00053 | **B** | "Where are you respectfully?" is ungrammatical English. | Rewritten as "Akka, where are you?" |
| KANG-TEST-00060 | **B** | "What did he say not telling?" is ungrammatical English. | Rewritten as "What is he not telling (us)?" |
| KANG-TEST-00067 | **B** | "Which class are you politely in?" is ungrammatical. | Rewritten as "Which class are you in?" |
| KANG-TEST-00082 | **C** | Slash in primary_reference makes keyword extraction inconsistent. `baagle` unclear. | Slash removed; moved to alternatives. |
| KANG-TEST-00097 | **B** | Slash in primary_reference. Two different readings conflated. | Slash removed; ambiguity noted. |
| KANG-TEST-00100 | **B** | `naale` (tomorrow) + `ninne` (yesterday) in same sentence — contradictory. Reference picked one silently. | Reference replaced with `[FLAGGED: contradictory naale+ninne - requires native speaker review]`. No translation assigned. |
| KANG-TEST-00015 | **C** | "Come here my phone has charge" — missing conjunction. | Fixed to "My phone is charged, come here". |
| KANG-TEST-00021 | **C** | Slash in primary_reference. | Removed; alternatives updated. |

Severity-B rows were corrected where the English grammar was clearly wrong.
Rows where the Kanglish input itself is uncertain are flagged and documented
in `research/BENCHMARK_REVIEW_ISSUES.md` — NOT silently rewritten.

---

## 3. `scripts/benchmark.py` Safeguards Added

### Previously missing; now implemented:

| Safeguard | Implementation |
|---|---|
| **Review status gate** | Exits with error if any row has `review_status=unreviewed` and `--smoke-test` not set |
| **`--smoke-test` mode** | Tests Ollama connectivity and output format. Explicitly labels results as "no accuracy claimed". Bypasses the review gate. |
| **`--row-limit N`** | Evaluates only the first N rows |
| **`--validate` mode** | Validates CSV structure, checks contamination (exact + near-duplicate), reports flagged references. No model calls. |
| **Unknown prompt rejection** | `sys.exit()` on unknown `--prompt` name. No silent fallback. |
| **Error response detection** | `[ERROR:` prefix detected; error rows excluded from score counts. |
| **Ollama connectivity check** | Explicit ping before evaluation; exits clearly if model unreachable. |
| **Unique result filenames** | `results/benchmark_run_MODEL_PROMPT_MODE_TIMESTAMP.csv` |
| **Full record fields** | Added `review_status`, `glossary_mode`, `is_error_response`, `timestamp` to every result row. |
| **Near-duplicate contamination check** | Phonetic normalization (`ee→i`, `oo→u`, `aa→a`, etc.) + `difflib.SequenceMatcher`; flags similarity ≥ 0.80 |
| **Flagged reference detection** | References starting with `[FLAGGED:` are reported as validation issues |
| **Category validation** | Checks against the 8 known valid category names |
| **Duplicate ID detection** | Reports duplicate IDs with location of first occurrence |

### Scoring corrections:

| Issue | Fix |
|---|---|
| `going`/`coming` in same synonym cluster | Split into separate directional clusters: `{go, going, goes}` and `{come, coming, comes}` |
| `_stem("cancelled")` → `"cancell"` (double-l) | Added double-consonant collapse after suffix stripping |
| `_word_matches` used regex `\b` against raw output text — stem of output never matched stem of keyword | Switched to set-based matching: extract all output words, add their stems, check set intersection against keyword candidates (matching `score.py`'s approach) |

---

## 4. Tests Actually Run

| Test | Method | Result |
|---|---|---|
| `scripts/benchmark.py` syntax | `python -m py_compile` | **PASS** |
| 38 unit tests (synonyms, stemming, matching, intent, commentary, error detection, Wilson CI) | `scratch/bench_test.py` | **38/38 PASS** |
| `--validate` mode on 100-row CSV | `python scripts/benchmark.py --validate` | **Ran. Reported 3 known issues (2 near-duplicates, 1 flagged row). No crashes.** |
| Review status gate (formal run blocked) | `python scripts/benchmark.py --row-limit 3` | **PASS — correctly exited with error.** |
| Unknown prompt rejection | `python scripts/benchmark.py --prompt v99_bogus` | **PASS — correctly exited with error.** |
| Smoke test (Ollama live) | `python scripts/benchmark.py --smoke-test --row-limit 2` | **PASS — Ollama reachable, 2 rows processed, no errors, no accuracy claimed.** |
| Full formal benchmark | **NOT RUN** | Blocked by review gate (all 100 rows unreviewed). Correct behaviour. |

---

## 5. Remaining Issues

### Must fix before ANY formal benchmark run:

1. **All 100 rows are `review_status=unreviewed`.**
   A native Kannada/Kanglish speaker must review every row.
   See `research/BENCHMARK_REVIEW_ISSUES.md` for row-specific issues.

2. **3 validation warnings** (reported by `--validate`):
   - `KANG-TEST-00051` (`ivattu yeshtu class ide?`) — 82% similar to blacklisted `ivattu class ide`. May need to be replaced or confirmed as sufficiently distinct.
   - `KANG-TEST-00096` (`swalpa wait maadri`) — 91% similar to blacklisted `swalpa wait maadu`. Very close variant. Recommend replacing.
   - `KANG-TEST-00100` — flagged reference (contradictory temporal input). Requires native speaker resolution.

3. **Severity-A issues** already corrected but should be re-verified by a native speaker:
   - KANG-TEST-00014 (hotte→late replacement)
   - KANG-TEST-00046 (naale tense correction)

4. **`score.py` has the same `going`/`coming` merged-synonym bug** as the original `benchmark.py`.
   However, modifying `score.py` was explicitly out of scope for this repair.
   The two scorers will now produce slightly different results for sentences
   involving directional motion. This divergence is documented here.
   Recommendation: fix `score.py` in a future task.

### Advisory (not blocking):

5. **No McNemar's test implemented.** The benchmark plan calls for a p-value comparing
   baseline vs glossary. Wilson CI is reported but paired significance test is not yet coded.

6. **No per-row `acceptable_alternatives` scoring.** The scorer only checks
   `primary_reference`. A model output matching an acceptable alternative (e.g.
   "Forget it" for `beda bidi`) will currently fail even if it is correct.

---

## 6. Exact Next Commands

```powershell
# 1. Review the 3 validation warnings and fix or confirm them:
python scripts/benchmark.py --validate

# 2. After native speaker review of rows, update review_status in the CSV:
#    Change review_status from "unreviewed" to "peer_reviewed_pass" or
#    "native_linguist_verified" for confirmed rows.

# 3. Once all rows are reviewed, run a full smoke test to confirm connectivity:
python scripts/benchmark.py --smoke-test --models qwen2.5:3b

# 4. Then run the formal benchmark (will be unblocked once review_status is updated):
python scripts/benchmark.py --models qwen2.5:3b gemma2:2b --prompt v1_baseline

# 5. To run score.py on the original 3-row sanity test (unchanged):
python scripts/score.py qwen2.5:3b v1_baseline
```

---

## 7. What Was NOT Done (Assumptions Avoided)

- No model was downloaded or trained.
- No rows were silently verified without being listed in `BENCHMARK_REVIEW_ISSUES.md`.
- No accuracy figures were claimed from the smoke test output.
- `score.py` was not modified (out of scope; divergence documented above).
- The 3 validation near-duplicate warnings were NOT automatically resolved;
  they require manual inspection.
- Row 00100 was NOT given a guessed translation; it was explicitly flagged.
