# Kanglish Representation Experiment — Contributor Guide

**Project:** `kanglish-foss`
**File to fill in:** `data/representation_v1/dev_intake_blank.csv`
**Target:** 20 messages, 5 per category, reviewed by 2 people each

---

## What we are collecting

We need **20 genuine Kanglish messages** — the informal, Romanized, code-mixed
way Kannada speakers text each other in English. Examples include everyday chat,
Bangalore slang, English-mixed sentences, and tricky grammar.

**We are not collecting:**
- Private messages without the sender's explicit permission
- AI-generated or invented examples that will be labelled as real
- Formal or news-style Kannada (we already have that data)

---

## The 20 slots by category

| IDs | Category | What to write |
|---|---|---|
| KGR1-0001 to KGR1-0005 | `everyday` | Ordinary conversation, greetings, requests, family, food |
| KGR1-0006 to KGR1-0010 | `slang` | Bangalore/Karnataka slang, informal expressions, exclamations |
| KGR1-0011 to KGR1-0015 | `code_mixed` | Sentences mixing Kanglish with English words mid-sentence |
| KGR1-0016 to KGR1-0020 | `spelling_grammar` | Varied Kanglish spellings of the same word, or dropped grammar markers |

Aim for variety: include at least one question, one negation, one past-tense,
one first-person and one third-person statement across the 20 messages.

---

## How to fill the CSV (open in VS Code or Excel with UTF-8 encoding)

### Fields you MUST fill in

| Field | What to put |
|---|---|
| `original_kanglish` | The Kanglish message, **verbatim**. Preserve original spelling, capitalisation and spacing exactly. Do not correct it. |
| `intended_english` | The single most natural English translation. This is the reference for scoring. |
| `contributor_id` | Your name or agreed pseudonym (e.g. `ryan`, `contributor_a`). Keep consistent across your rows. |

### Fields to fill when applicable

| Field | When to fill | What to put |
|---|---|---|
| `context` | If the message only makes sense in context | Briefly describe the setting (e.g. "texting a friend about dinner") |
| `acceptable_alternatives` | If more than one English translation is equally valid | List them pipe-separated: `"She's tired\|She's exhausted"` |
| `kannada_script` | If you know the Kannada-script rendering of the message | Write it in native Kannada script (ಕನ್ನಡ). Leave blank if unsure. |
| `ambiguity_notes` | If the message is genuinely ambiguous | Explain what the two readings are |
| `ambiguity_status` | One of: `none`, `resolved_by_context`, `multiple_valid`, `unresolved` | |

### Fields you MUST NOT change

The following fields are pre-filled and must stay exactly as they are:

`schema_version`, `id`, `split`, `source_type`, `source_provenance`,
`usage_permission`, `privacy_review`, `variant_group_id`

---

## If you are contributing a message someone else wrote

You need their **explicit permission** for local research use before adding it.

1. Ask them: *"Can I use this message for a local, offline translation research project? It won't be published or shared publicly."*
2. Record their agreement (a WhatsApp "yes" screenshot is fine).
3. Fill these fields:
   - `source_type` → `consented_chat` (not `purpose_written`)
   - `usage_permission` → `granted`
   - `permission_scope` → `local_evaluation`
   - `permission_ref` → a reference to where you recorded consent (e.g. `whatsapp_ryan_2026-10-18`)
4. Leave `redistribution_license` and `redistribution_permission_ref` **blank** unless the contributor explicitly said you can redistribute.

If someone says no, or you are unsure — **leave the row blank**. Do not use the message.

---

## Privacy checklist (fill `privacy_review` field)

Before submitting, check each row:

- [ ] Does the message contain a real person's full name, phone number, address, or photo caption? → **needs_redaction**
- [ ] Does it reveal something sensitive (health, relationship, finance)? → **reject**
- [ ] Is it clearly about generic everyday topics? → **pass**

Set `privacy_review` to `pass`, `needs_redaction`, or `reject` accordingly.
Leave as `pending` if you want the second reviewer to check.

---

## Example of a complete row

```
original_kanglish  : nange coffee beku, ella readya?
context            : (blank — self-explanatory)
intended_english   : I want coffee, is everything ready?
acceptable_alternatives: I need coffee, is everything ready?
kannada_script     : ನನಗೆ ಕಾಫಿ ಬೇಕು, ಎಲ್ಲಾ ರೆಡಿಯಾ?
source_type        : purpose_written
source_provenance  : self-authored
usage_permission   : granted
permission_scope   : local_evaluation
permission_ref     : self
privacy_review     : pass
ambiguity_status   : none
category           : everyday
```

---

## Reviewer instructions (two reviewers required per row)

**Reviewer 1 and Reviewer 2 must be different people.**
At least one reviewer should be a fluent Kannada speaker.

For each row, set your decision in `reviewer_1_decision` (or `reviewer_2_decision`):

| Decision | Meaning |
|---|---|
| `accept` | The `original_kanglish` is genuine, the `intended_english` is the correct natural translation, consent and privacy are satisfied |
| `revise` | The row has fixable problems — note them in `ambiguity_notes` |
| `reject` | The message is fabricated, the translation is wrong, consent is absent, or it reveals private information |

If `kannada_script` is provided, the Kannada reviewer sets `kannada_review` to
`accept`/`revise`/`reject` and fills `kannada_reviewer_id`.

---

## Structural check (run before submitting)

After filling the CSV, **copy** it over `data/representation_v1/dev.csv` and run:

```powershell
cd c:\Users\ryan1\kanglish-foss
python.exe -B scripts/representation_experiment.py validate
```

This checks field names, ID formats, enum values, and duplicate detection.
It does **not** check whether translations are correct — that is the reviewers' job.

If you see errors, fix them and run again. A clean run prints:
```
dev: 20 records, N approved for original-input evaluation
Schema/leakage checks passed.
```

---

## What happens after review

When all 20 rows have `reviewer_1_decision=accept`, `reviewer_2_decision=accept`,
`usage_permission=granted`, and `privacy_review=pass`, run the dry-run preflight:

```powershell
python.exe -B scripts/representation_experiment.py run \
    --split dev --model qwen2.5:3b \
    --representations original human \
    --temperature 0 --seed 17 --num-ctx 2048 --num-predict 64 \
    --dry-run
```

If preflight passes (exit 0), run without `--dry-run`. Do not run without
Ollama installed and the model pulled locally first.

---

## What we are NOT doing

- Not fine-tuning any model
- Not downloading IndicXlit or other tools
- Not using any of these 20 messages in the locked evaluation set (`eval.locked.csv`)
- Not claiming machine output is authentic Kanglish
