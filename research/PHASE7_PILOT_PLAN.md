# Phase 7 Pilot Experiment Plan

**Project:** `kanglish-foss`
**Date:** 2026-10-18
**Goal:** 20-message controlled comparison of direct Kanglish translation (`original`)
vs. Kanglish translation augmented with a human-checked Kannada-script hint (`human`).

---

## 1. What this experiment measures

The hypothesis (Architecture C from `ASTRA_DECISION_AND_PHASE6_REPORT.md`):
> Adding a human-checked Kannada-script rendering as a fallible prompt hint
> rescues some translations that fail on Romanized input alone, while the
> original Kanglish remains the authoritative input.

The experiment does **not** test:
- Machine-generated transliteration (IndicXlit is deferred)
- Model fine-tuning
- Any change to the existing translator, glossary, or scoring scripts

---

## 2. Input data requirements

### Source: `data/representation_v1/dev.csv`

Must contain exactly **20 rows** with:
- `split=dev`
- `schema_version=representation-v1`
- IDs in `KGR1-0001` … `KGR1-0020` format
- 5 rows per category: `everyday`, `slang`, `code_mixed`, `spelling_grammar`
- Coverage: at least 1 question, 1 negation, 1 past-tense, 1 first-person,
  1 third-person statement across the 20 messages

### Readiness gate (enforced by `validate --ready`)

Every row must have:
- `usage_permission=granted`
- `privacy_review=pass`
- `reviewer_1_decision=accept`
- `reviewer_2_decision=accept`
- No `ambiguity_status=unresolved`

Rows with `kannada_script` filled also need `kannada_review=accept` and
`kannada_reviewer_id` set before the `human` representation can run.

### This is NOT in scope yet

- `data/representation_v1/eval.locked.csv` — locked, untouched, 0 rows. Do not
  add rows or run inference against it until the dev pilot passes the gate.

---

## 3. Representations compared

| Name | Prompt content | Source |
|---|---|---|
| `original` | Kanglish input only | `original_kanglish` field |
| `human` | Kanglish input + "Hint: [kannada_script]" | `kannada_script` field, reviewer-approved |

The system prompt (defined in `representation_experiment.py`) is identical for
both arms and explicitly states: *"An optional Kannada rendering is a fallible
hint; the original remains authoritative."*

---

## 4. Model and inference settings (fixed for both arms)

| Setting | Value | Rationale |
|---|---|---|
| Model | `qwen2.5:3b` | Already installed locally (~1.9 GB) |
| Temperature | `0` | Deterministic output |
| Seed | `17` | Reproducible |
| num-ctx | `2048` | Sufficient for short messages |
| num-predict | `64` | Caps output length |
| Glossary | Enabled (default) | Same configuration as baseline |

These settings must be identical between `original` and `human` arms.
Do not change them between runs of the same pilot cohort.

---

## 5. Exact commands

### Step 1 — Verify structural integrity (run any time)
```powershell
cd c:\Users\ryan1\kanglish-foss
python.exe -B scripts/representation_experiment.py validate
```
Expected: exit 0, "Schema/leakage checks passed."

### Step 2 — Verify readiness gate (run after all 20 rows are reviewed)
```powershell
python.exe -B scripts/representation_experiment.py validate --ready
```
Expected: exit 0. If exit 2, fix the listed fields before proceeding.

### Step 3 — Dry-run preflight (verifies Ollama connectivity, no inference)
```powershell
python.exe -B scripts/representation_experiment.py run `
    --split dev --model qwen2.5:3b `
    --representations original human `
    --temperature 0 --seed 17 --num-ctx 2048 --num-predict 64 `
    --dry-run
```
Expected: exit 0. Abort if exit 2 — check Ollama is running and model is pulled.

### Step 4 — Run the experiment (only after Steps 1–3 pass)
```powershell
python.exe -B scripts/representation_experiment.py run `
    --split dev --model qwen2.5:3b `
    --representations original human `
    --temperature 0 --seed 17 --num-ctx 2048 --num-predict 64
```
The script writes a timestamped run directory. Note it from the output.

### Step 5 — Summarize results (after human review of outputs)
```powershell
python.exe -B scripts/representation_experiment.py summarize results\<run-dir>
```

---

## 6. Human review of outputs (required before any conclusions)

After inference, two reviewers independently read each model output and fill
the review CSV produced in the run directory. For each output:

| Field | Options |
|---|---|
| `human_acceptance` | `accept` / `reject` |
| `meaning_error` | `yes` / `no` |
| `polarity_error` | `yes` / `no` |
| `person_error` | `yes` / `no` |
| `tense_error` | `yes` / `no` |
| `fluency_error` | `yes` / `no` |

Reviewers must not see which representation produced which output during rating
(blind review). Discuss disagreements; record the final decision.

---

## 7. Success criteria (pilot gate)

All three criteria must be met to consider the `human` hint beneficial:

| Criterion | Threshold | Measurement |
|---|---|---|
| **Net additional accepted translations** | ≥ 3 (≥ 15 pp) | `wins - losses` in paired analysis (original → human) |
| **No increase in error types** | 0 new errors in any of: meaning, polarity, person, tense | Compare error counts: human arm must not exceed original arm on any category |
| **Latency** | `human` arm p95 latency ≤ 2× `original` arm p95 | Measured by `representation_experiment.py` automatically |

**If the pilot fails the gate:**
- Keep Architecture A (direct Kanglish, no hint)
- Do not scale to the 80-message eval set
- Investigate whether the failures are due to hint quality, model behaviour,
  or category-specific issues

**If the pilot passes the gate:**
- Proceed to the 80-message locked eval cohort (requires a separate collection
  and review cycle — not started yet)
- Consider testing machine-generated hints (IndicXlit) in an isolated environment
  as a separate follow-up

---

## 8. What human input is still required

### Before the experiment can run

| # | Who | Task |
|---|---|---|
| 1 | **You (Ryan)** | Fill `original_kanglish` for all 20 slots in `dev_intake_blank.csv` |
| 2 | **You** | Fill `intended_english` (the reference translation) for all 20 |
| 3 | **You** | Fill `kannada_script` for any row where you know the Kannada rendering |
| 4 | **You** | Fill `ambiguity_notes` for any genuinely ambiguous input |
| 5 | **Reviewer 1** | Set `reviewer_1_decision` for all 20 rows |
| 6 | **Reviewer 2** (different person) | Set `reviewer_2_decision` for all 20 rows |
| 7 | **Kannada reviewer** | Set `kannada_review` + `kannada_reviewer_id` for rows with `kannada_script` |
| 8 | **Both reviewers** | Set `usage_permission=granted` and `privacy_review=pass` for each row |

### After inference runs

| # | Who | Task |
|---|---|---|
| 9 | **Reviewer 1** | Rate all 40 outputs (20 × 2 arms) — blind to representation |
| 10 | **Reviewer 2** | Same — independently |
| 11 | **Both** | Discuss disagreements; record final decision |

---

## 9. Files involved

| File | Role | Edit? |
|---|---|---|
| `data/representation_v1/dev_intake_blank.csv` | Template to fill in | **YES — fill and copy to dev.csv** |
| `data/representation_v1/dev.csv` | Active input for experiment | Replace with filled template |
| `data/representation_v1/CONTRIBUTOR_GUIDE.md` | Instructions for contributors | Read-only |
| `data/representation_v1/eval.locked.csv` | Locked eval — empty | **Do not touch** |
| `scripts/representation_experiment.py` | Experiment runner | **Do not modify** |
| `scripts/benchmark.py` | Locked benchmark | **Do not touch** |
| `data/benchmark_test_v1_draft.csv` | Locked evaluation set | **Do not touch** |

---

## 10. Structural test results (run 2026-10-18)

```
python.exe -B -m unittest discover -s tests -v
  Ran 32 tests in 2.746s — OK (exit 0)

python.exe -B scripts/transliterate_corpus.py --unit-test
  24 passed, 0 failed (exit 0)

python.exe -B scripts/representation_experiment.py validate
  dev: 0 records, 0 approved — Schema/leakage checks passed (exit 0)

python.exe -B scripts/representation_experiment.py validate --ready
  ERROR: dev: no reviewed records (exit 2) — CORRECT: blocks empty cohort

python.exe -B scripts/representation_experiment.py run ... --dry-run
  exit 2 — CORRECT: blocks missing reviewed records
```

All structural guards are working correctly. No inference has been run.
No model weights have been downloaded. No training has started.
