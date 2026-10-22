# Representation experiment v1

This implements the conversation's architecture memo: compare original Kanglish
with the same original plus a human-checked or machine-produced Kannada hint.
It supplements `PHASE5_REPORT.md`; its proposal to use IN22-Conv as training input
is superseded. IN22-Conv, the 195 unreviewed candidates and the existing synthetic
benchmark draft are not sources of authentic messages for this experiment.
No model-quality result exists yet. This workflow uses Python's standard library.

## Contribute and review

`data/representation_v1/annotation_template.csv` defines the exact UTF-8 CSV header.
`dev.csv` and `eval.locked.csv` start with headers only, targeting 20 and 80 messages.
`init` recreates missing local files on a fresh checkout and never overwrites them.
No example text, translation, permission, review decision or dataset license is generated.

| Fields | Human input required |
|---|---|
| `schema_version`, `id`, `split` | `representation-v1`; stable IDs such as `KGR1-0001`; `dev` or `eval` matching the file. Never recycle IDs. |
| `conversation_id`, `variant_group_id`, `contributor_id` | Opaque aliases. All messages from a conversation, all spelling/meaning variants and each contributor must stay in one split. |
| `original_kanglish`, `context`, `intended_english`, `acceptable_alternatives` | Preserve the contributed spelling. A bilingual human supplies the English; context and alternate acceptable translations are optional. |
| `source_type`, `source_provenance` | `purpose_written` or `consented_chat`, plus a short non-identifying origin description. No AI-generated messages. |
| `usage_permission`, `permission_scope`, `permission_ref` | `pending`, `granted`, `denied` or `withdrawn`. Running requires `granted`, scope `local_evaluation` and an opaque reference to explicit consent covering the message and any context. |
| `redistribution_license`, `redistribution_permission_ref` | Leave both blank unless contributors explicitly authorized that particular license separately. Local evaluation consent does not authorize sharing or training. |
| `privacy_review` | `pending`, `pass`, `needs_redaction` or `reject`; running requires a human `pass`. |
| `reviewer_1_id/decision`, `reviewer_2_id/decision` | Two distinct bilingual reviewers familiar with Bangalore usage. Decisions: `pending`, `accept`, `revise`, `reject`. Both must accept before running. |
| `kannada_script`, `kannada_reviewer_id`, `kannada_review` | Optional faithful rendering preserving English spans, meaning and register. If absent, use `not_provided` and leave the reviewer blank; otherwise use the review decisions above. The human arm requires `accept`. |
| `ambiguity_status`, `ambiguity_notes` | `none`, `resolved_by_context`, `multiple_valid`, `unresolved`. Supply notes for every non-`none` case; unresolved cases cannot run. Record alternate readings, not guessed subjects or tense. |
| `category` | `everyday`, `slang`, `code_mixed`, `spelling_grammar`. Aim for 20 held-out messages per category; choose a primary category when they overlap. |

Get permission **before contributing personal messages**. Prefer purpose-written
examples; remove identifying details with the contributor's agreement. Use aliases,
not names, handles, phone numbers or email addresses. Keep consent records separately
under the ignored `consent/` directory or another private location. Human privacy
review is essential: the validator cannot prove consent or detect all identifying text.

Only the empty templates belong in Git. Local annotation files, consent records,
IndicXlit outputs, freezes and runs are ignored by the nested `.gitignore`.
Do not force-add or upload populated files without explicit sharing permission.
Gitignore is not access control. Withdrawn permission blocks new runs; previously
created local outputs also need a human retention/deletion decision.

## Validate, compare, judge

Validation detects missing fields, inconsistent approvals, duplicate IDs/inputs,
normalized/fuzzy overlap (threshold 0.85), identical Kannada renderings and group
leakage across splits. Same-split near matches require inspection; the heuristic
does not prove semantic independence. Keep real variants together and avoid reusing
old tests, examples or benchmark items. Do not alter spellings to evade checks.

Development can run on a smaller approved cohort. Missing human renderings or
IndicXlit entries block the entire requested comparison; rows are never silently
dropped. `lock-eval` requires exactly 20 approved dev and 80 approved eval records,
and approval of any supplied Kannada rendering. It creates `eval.lock.json` once,
freezing both files by SHA-256. Evaluation cannot run before this freeze. Subsequent
edits are rejected: preserve the frozen cohort and create a separate dataset revision.
Finish prompt/glossary/settings choices on development data before evaluating.

All arms use one local model, system prompt, context, glossary policy and decoding
configuration. Hints are matched against original Kanglish. English references and
annotation notes never enter model requests. The runner randomizes arm order with a
recorded seed, records model digests before/after, and only contacts loopback Ollama
with proxies and redirects disabled. It never installs, downloads, trains or pulls models.

Each run writes `manifest.json`, immutable `predictions.csv` and `human_reviews.csv`.
The review sheet hides representation labels and starts with all ratings blank.
Two reviewers enter an agreed `accept`/`reject`, their distinct aliases, and explicit
`yes`/`no` for meaning, polarity, person, tense and fluency errors. Reject decisions
need notes; leave disagreements pending until resolved. Accept only faithful, natural
English without correction; allow documented alternate readings. Unsupported facts,
entity corruption and intent changes count as meaning errors and belong in notes.
Edit only the rating columns. The summary reports pending reviews, human error counts,
category counts and paired wins/losses; rates remain null while applicable cases are
pending. Timeouts, missing outputs and truncations remain failures in the denominator.

Latency is request wall time, including loading; load time is recorded separately.
Memory is the optional `/api/ps` loaded-model/VRAM snapshot, **not** process RAM or a
measured peak. Unavailable values stay blank/null. Statistical confidence intervals,
peak-memory profiling and architecture acceptance gates remain later analysis; this
script does not claim the memo's quality thresholds have been met.

## Exact commands (from the repository root)

These work now; validation reports empty cohorts, not translation accuracy:

```powershell
python -B scripts/representation_experiment.py init
python -B scripts/representation_experiment.py validate
python -B -m unittest discover -s tests -p test_representation_experiment.py -v
```

After genuine contributions and human review (the run commands are blocked now):

```powershell
python -B scripts/representation_experiment.py validate --ready
python -B scripts/representation_experiment.py run --split dev --model qwen2.5:3b --representations original human --dry-run
python -B scripts/representation_experiment.py run --split dev --model qwen2.5:3b --representations original human
python -B scripts/representation_experiment.py lock-eval
python -B scripts/representation_experiment.py run --split eval --model qwen2.5:3b --representations original human
```

Use the printed run directory below after humans fill its review sheet:

```powershell
python -B scripts/representation_experiment.py summarize data/representation_v1/runs/ACTUAL_RUN_ID
```

The third arm is an **import interface only**. Leave `indicxlit_template.csv` empty
until an independently established IndicXlit worker produces real outputs. Its CSV
must retain each ID and exact original in `source_kanglish`, identify `engine=IndicXlit`,
and supply one pinned `model_revision` plus a JSON object in `generation_settings`.
Do not relabel dictionary output or human renderings as IndicXlit. Save genuine
outputs locally as `indicxlit.csv`, then use:

```powershell
python -B scripts/representation_experiment.py run --split dev --model qwen2.5:3b --representations original human indicxlit --indicxlit-csv data/representation_v1/indicxlit.csv --dry-run
```

Omit `--dry-run` only when ready to execute. Explicitly use the same `--temperature`
(default 0), `--seed` (17), `--num-ctx` (2048), `--num-predict` (64) and glossary policy
for comparisons; thinking is disabled. Qwen2.5:3b remains a research-license baseline,
not a newly approved redistributable default. Nothing here resolves fairseq compatibility.
