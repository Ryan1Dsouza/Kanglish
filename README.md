# kanglish-foss
Offline Kanglish (Kannada in English letters) to English decoder.

Rules for AI agents:
- NEVER create or edit data/test.csv. Only the owner writes test data.
- Do not invent "expected" translations.
- Keep scripts dependency-free (Python stdlib only) unless told otherwise.
- Models run via Ollama at http://localhost:11434.
- Never create, edit, or generate rows in data/test.csv or data/dev.csv.
- Never edit data/glossary.csv. Propose additions in data/glossary_candidates.csv with a confidence note; a human reviews them.
- Never change the scorer in a way that makes past results incomparable without logging it.
- Stop after 60 minutes or 10 experiments, whichever comes first.