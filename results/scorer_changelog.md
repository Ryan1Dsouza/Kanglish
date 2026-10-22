# Scorer Changelog

Per repository guidelines (`README.md`):
> *"Never change the scorer in a way that makes past results incomparable without logging it."*

This document tracks all modifications to `scripts/score.py` scoring criteria, matching rules, keyword extraction, and penalties.

---

## [2026-10-18] Scorer Revision 2.0: Whole-Word Matching, Unified Directional Synonyms & Commentary Penalty

### 1. Unified Movement Synonyms
- **Change**: Merged separate `"coming"` and `"going"` synonym sets into a single unified group:
  `{"going", "coming", "go", "come", "goes", "comes"}`.
- **Rationale**: In conversational Kanglish chats, directionality verbs often translate interchangeably depending on speaker perspective (e.g. `naale college ge barthira?` can naturally be answered or rendered as "Are you coming..." or "Are you going...").
- **Impact on past scores**: Outputs using "going" for expected "coming" now match the directional movement keyword.

### 2. Whole-Word Token Set Matching
- **Change**: Replaced substring and partial regex matching with strict token-level word matching.
  - Words in outputs are tokenized as individual alphabetic words (`\b[a-z]+\b`).
  - Contractions (`'s`) are normalized so `"what's"` -> `"what"` and `"it's"` -> `"it"` without leaving apostrophe remnants.
  - Candidate keywords and their stems/synonyms are compared against the set of extracted output words and their stems via set intersection (`candidates & all_out_words`).
- **Rationale**: Eliminates false substring matches (e.g., `go` in `mango`, `me` in `meeting`) and avoids regex word boundary edge-cases with apostrophes.
- **Impact on past scores**: Prevents spurious keyword hits on substrings inside unrelated words.

### 3. Commentary & Parenthetical Penalty
- **Change**: Introduced `PENALTY_COMMENTARY = 0.35` deducted from the keyword match ratio before comparing to `HIT_THRESHOLD = 0.70`.
  - Triggered by parenthetical or bracketed text (`(...)`, `[...]`).
  - Triggered by explanatory labels (`Note:`, `Meaning:`, `Translation:`, `Literal:`).
  - Triggered by conversational meta-phrases (`"here is the translation"`, `"this means"`).
  - Triggered by multi-line commentary.
- **Rationale**: The decoder's specification requires producing ONLY the natural English translation. Explanatory fluff and meta-commentary degrade user experience in downstream integrations.
- **Impact on past scores**: Outputs that included unsolicited explanations or bracketed notes now fail to pass even if they contained the relevant keywords.

### 4. Stop-Word and Keyword Refinement
- **Change**: Added contractions and function words (`this`, `that`, `'s`) to the stop-word filtering set in `keywords()`.
- **Impact on past scores**: Test cases like `"What's the plan today bro?"` focus evaluation strictly on content words (`plan`, `today`, `bro`) rather than penalizing on contraction tokens.
