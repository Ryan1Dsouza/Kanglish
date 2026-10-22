"""
score.py – compare baseline vs glossary-augmented decoding over data/test.csv.

Usage:
    python scripts/score.py [model] [prompt_version]

Prompt versions available:
    v1_baseline       – original prompt & mandatory word meanings header
    v2_no_commentary  – "translate only, no commentary" with strict anti-hallucination rules
    v3_strong_rules   – explicit grammatical rules (subject person, question preservation)
    v4_clean_glossary – clean prompt + strip parenthetical glosses from injected entries
    v5_fewshot_aligned– conversational WhatsApp few-shots covering questions and adjectives

Appends results to results/log.csv.
"""

import csv, datetime, json, os, re, sys, urllib.request

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:3b"
PROMPT_VERSION = sys.argv[2] if len(sys.argv) > 2 else "v1_baseline"

# ── prompt variants ───────────────────────────────────────────────────────────

PROMPT_VARIANTS = {
    "v1_baseline": {
        "system": (
            "You decode Kanglish: Kannada written in English letters, mixed with English, "
            "as used in college WhatsApp group chats. Spelling varies a lot. "
            "Reply with ONLY the natural English meaning, in one line."
        ),
        "shots": (
            "Kanglish: eno maadtidya?\n"
            "English: What are you doing?\n\n"
            "Kanglish: nanna jothe bartiya?\n"
            "English: Will you come with me?\n\n"
            "Kanglish: oota aitha?\n"
            "English: Did you eat?\n\n"
        ),
        "glossary_header": "Word meanings (MANDATORY: use these exact meanings and do not drop any of them):\n",
        "clean_glossary": False,
    },
    "v2_no_commentary": {
        "system": (
            "You decode Kanglish: Kannada written in English letters, mixed with English, "
            "as used in college WhatsApp group chats. Reply with ONLY the natural English "
            "translation in one line. Do not output explanations, notes, or parenthetical commentary. "
            "Do not keep untranslated Kanglish words in your output."
        ),
        "shots": (
            "Kanglish: eno maadtidya?\n"
            "English: What are you doing?\n\n"
            "Kanglish: nanna jothe bartiya?\n"
            "English: Will you come with me?\n\n"
            "Kanglish: oota aitha?\n"
            "English: Did you eat?\n\n"
        ),
        "glossary_header": (
            "Word meanings (use these meanings in your translation; output ONLY the English translation, no notes):\n"
        ),
        "clean_glossary": True,
    },
    "v3_strong_rules": {
        "system": (
            "You are a Kanglish-to-English translator. Follow these strict rules:\n"
            "1. Translate to fluent, natural English on a single line.\n"
            "2. Preserve question forms (end with '?' if the input is a question).\n"
            "3. Preserve the grammatical subject (e.g. verbs ending in -ira or -iya refer to 'you', not 'I').\n"
            "4. Never include explanations, notes, or parentheses.\n"
            "5. Translate all words; do not leave Kanglish words untranslated."
        ),
        "shots": (
            "Kanglish: naale bidthira?\n"
            "English: Will you leave tomorrow?\n\n"
            "Kanglish: yenu guru samachara?\n"
            "English: What's the news bro?\n\n"
            "Kanglish: thumba chennagide\n"
            "English: It is very good.\n\n"
        ),
        "glossary_header": "Word meanings (substitute these into the translation):\n",
        "clean_glossary": True,
    },
    "v4_clean_glossary": {
        "system": (
            "Translate college Kanglish (Kannada in English script) to natural English. "
            "Output ONLY the English translation in one sentence. "
            "No notes, no commentary, no original Kanglish words."
        ),
        "shots": (
            "Kanglish: eno maadtidya?\n"
            "English: What are you doing?\n\n"
            "Kanglish: nanna jothe bartiya?\n"
            "English: Will you come with me?\n\n"
            "Kanglish: oota aitha?\n"
            "English: Did you eat?\n\n"
        ),
        "glossary_header": "Vocabulary reference:\n",
        "clean_glossary": True,
    },
    "v5_fewshot_aligned": {
        "system": (
            "You decode Kannada chat slang (Kanglish) into casual English. "
            "Output ONLY the translation. Never add explanations or parentheses."
        ),
        "shots": (
            "Kanglish: ivattu bartiya?\n"
            "English: Are you coming today?\n\n"
            "Kanglish: yenu maga plan?\n"
            "English: What's the plan dude?\n\n"
            "Kanglish: thumba chennagide\n"
            "English: It is very good.\n\n"
        ),
        "glossary_header": "Word meanings (translate using these English equivalents, output only English):\n",
        "clean_glossary": True,
    },
}

VARIANT_CONFIG = PROMPT_VARIANTS.get(PROMPT_VERSION, PROMPT_VARIANTS["v1_baseline"])

# ── glossary ──────────────────────────────────────────────────────────────────

def load_glossary(path="data/glossary.csv"):
    glossary = {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            glossary[row["kanglish"].strip().lower()] = row["english"].strip()
    return glossary

GLOSSARY = load_glossary()

def sanitize_meaning(meaning: str) -> str:
    """Strip parenthetical notes like '(slang)' or '(term of address)' from definitions."""
    cleaned = re.sub(r"\(.*?\)", "", meaning).strip()
    return re.sub(r"\s+", " ", cleaned)

def relevant_entries(text, clean=False):
    text_lower = text.lower()
    hits = []
    for word, meaning in GLOSSARY.items():
        if re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", text_lower):
            final_meaning = sanitize_meaning(meaning) if clean else meaning
            hits.append((word, final_meaning))
    return hits

# ── LLM call ─────────────────────────────────────────────────────────────────

def call_model(prompt):
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate", body,
        {"Content-Type": "application/json"}
    )
    return json.loads(urllib.request.urlopen(req).read())["response"].strip()

# ── prompt builders ───────────────────────────────────────────────────────────

def baseline_prompt(text, context, config=VARIANT_CONFIG):
    prompt = config["system"] + "\n\n" + config["shots"]
    if context:
        prompt += f"Previous message: {context}\n"
    prompt += f"Kanglish: {text}\nEnglish:"
    return prompt

def glossary_prompt(text, context, config=VARIANT_CONFIG):
    prompt = config["system"] + "\n\n" + config["shots"]
    hits = relevant_entries(text, clean=config.get("clean_glossary", False))
    if hits:
        prompt += config["glossary_header"]
        for word, meaning in hits:
            prompt += f"  {word} = {meaning}\n"
        prompt += "\n"
    if context:
        prompt += f"Previous message: {context}\n"
    prompt += f"Kanglish: {text}\nEnglish:"
    return prompt

# ── scoring ───────────────────────────────────────────────────────────────────

# Synonym clusters: every word in a cluster is treated as equivalent.
# "going", "coming", "go", "come", "goes", "comes" combined into one group.
_RAW_SYNONYMS = [
    {"bro", "dude", "guru", "man", "buddy", "mate"},
    {"awesome", "great", "amazing", "fantastic", "cool", "nice"},
    {"plan", "schedule", "plans"},
    {"tomorrow", "tmrw"},
    {"going", "coming", "go", "come", "goes", "comes"},
    {"today"},
]
SYNONYMS: dict[str, frozenset] = {}
for _cluster in _RAW_SYNONYMS:
    _fs = frozenset(_cluster)
    for _w in _cluster:
        SYNONYMS[_w] = _fs

def _stem(word: str) -> str:
    """Minimal suffix stripping for English content words."""
    for suffix in ("ning", "ing", "tion", "ed", "er", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word

def keywords(expected: str) -> list[str]:
    """
    Extract content keywords from the expected translation.
    Contractions ('s) and stop-words are filtered out.
    """
    STOP = {
        "a", "an", "the", "is", "it", "to", "in", "on", "of",
        "are", "be", "do", "did", "you", "i", "me", "my",
        "your", "he", "she", "we", "they", "what", "how",
        "and", "or", "not", "no", "s", "its", "has", "have",
        "will", "for", "at", "by", "with", "this", "that",
    }
    cleaned = re.sub(r"'s\b", "", expected.lower())
    words = re.findall(r"\b[a-z]+\b", cleaned)
    return [w for w in words if w not in STOP and len(w) > 2]

def _word_matches(kw: str, all_out_words: set[str]) -> bool:
    """
    Check whole-word match: candidate or its stem/synonym must be
    an exact word in the output word set.
    """
    candidates = {kw, _stem(kw)}
    for c in list(candidates):
        if c in SYNONYMS:
            candidates |= SYNONYMS[c]
    candidates |= {_stem(c) for c in candidates}
    return bool(candidates & all_out_words)

# Penalty applied when extra parenthetical or explanatory text is found
PENALTY_COMMENTARY = 0.35
HIT_THRESHOLD = 0.70  # pass if score after penalty >= 70%

def has_extra_commentary(output: str) -> tuple[bool, str]:
    """
    Detect extra parenthetical or explanatory text beyond the translation.
    Returns (is_penalized, reason_str).
    """
    # 1. Parenthetical or bracketed text
    if re.search(r"\(.*?\)|\[.*?\]", output):
        return True, "contains parenthetical/bracketed text"
    # 2. Explanatory headers or labels (e.g. Note:, Meaning:, Translation:)
    if re.search(r"(?i)\b(note|meaning|translation|explanation|literal|literally)\s*:", output):
        return True, "contains explanatory label"
    # 3. Conversational commentary phrases
    if re.search(r"(?i)\b(here is the translation|this translates to|this means|in english,?\s+this)\b", output):
        return True, "contains conversational commentary phrase"
    # 4. Multi-line commentary
    lines = [l.strip() for l in output.strip().splitlines() if l.strip()]
    if len(lines) > 1:
        return True, "output spans multiple lines with commentary"
    return False, ""

def evaluate_output(output: str, expected_keywords: list[str]) -> tuple[bool, float, list[str], str]:
    """
    Detailed evaluation:
    Returns (passed, score, matched_keywords, penalty_reason).
    """
    if not expected_keywords:
        return True, 1.0, [], ""

    out_lower = output.lower()
    cleaned_out = re.sub(r"'s\b", "", out_lower)
    out_words = set(re.findall(r"\b[a-z]+\b", cleaned_out))
    out_stemmed = {_stem(w) for w in out_words}
    all_out_words = out_words | out_stemmed

    matched = [kw for kw in expected_keywords if _word_matches(kw, all_out_words)]
    raw_ratio = len(matched) / len(expected_keywords)

    penalized, reason = has_extra_commentary(output)
    penalty = PENALTY_COMMENTARY if penalized else 0.0
    final_score = max(0.0, raw_ratio - penalty)

    passed = final_score >= HIT_THRESHOLD
    return passed, final_score, matched, reason

def hit(output: str, expected_keywords: list[str]) -> bool:
    """Pass when score after commentary penalty >= HIT_THRESHOLD (fuzzy whole-word)."""
    passed, _, _, _ = evaluate_output(output, expected_keywords)
    return passed

# ── logging ───────────────────────────────────────────────────────────────────

def log_result(model: str, prompt_version: str, baseline_score: str, glossary_score: str, timestamp: str = None):
    os.makedirs("results", exist_ok=True)
    log_path = os.path.join("results", "log.csv")
    write_header = not os.path.exists(log_path) or os.path.getsize(log_path) == 0
    if timestamp is None:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["model", "prompt_version", "baseline_score", "glossary_score", "timestamp"])
        writer.writerow([model, prompt_version, baseline_score, glossary_score, timestamp])

# ── main evaluation runner ────────────────────────────────────────────────────

def run_evaluation(model=MODEL, prompt_version=PROMPT_VERSION, log_to_csv=True):
    config = PROMPT_VARIANTS.get(prompt_version, PROMPT_VARIANTS["v1_baseline"])
    baseline_hits = 0
    glossary_hits = 0
    total = 0
    results_detail = []

    with open("data/test.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"=== Running evaluation: model={model}, prompt_version={prompt_version} ===")

    for row in rows:
        total += 1
        text = row["kanglish"]
        expected = row["english"]
        context = row.get("context", "")
        kws = keywords(expected)

        b_prompt = baseline_prompt(text, context, config)
        g_prompt = glossary_prompt(text, context, config)

        b_out = call_model(b_prompt)
        g_out = call_model(g_prompt)

        b_passed, b_score, b_matched, b_reason = evaluate_output(b_out, kws)
        g_passed, g_score, g_matched, g_reason = evaluate_output(g_out, kws)

        baseline_hits += int(b_passed)
        glossary_hits += int(g_passed)

        b_status = "[PASS]" if b_passed else f"[FAIL ({b_reason or 'missing keywords'})]"
        g_status = "[PASS]" if g_passed else f"[FAIL ({g_reason or 'missing keywords'})]"

        print(f"── Row {total} ─────────────────────────────")
        print(f"  IN      : {text}")
        print(f"  EXPECTED: {expected}")
        print(f"  KEYWORDS: {kws}")
        print(f"  BASELINE: {b_out}  -> {b_status} (score={b_score:.2f})")
        print(f"  GLOSSARY: {g_out}  -> {g_status} (score={g_score:.2f})")
        print()

        results_detail.append({
            "row": total,
            "text": text,
            "expected": expected,
            "keywords": kws,
            "baseline_out": b_out,
            "baseline_passed": b_passed,
            "baseline_score": b_score,
            "baseline_reason": b_reason,
            "glossary_out": g_out,
            "glossary_passed": g_passed,
            "glossary_score": g_score,
            "glossary_reason": g_reason,
        })

    b_score_str = f"{baseline_hits}/{total}"
    g_score_str = f"{glossary_hits}/{total}"

    print("════════════════════════════════════════")
    print(f"  Model           : {model}")
    print(f"  Prompt Version  : {prompt_version}")
    print(f"  Baseline Score  : {b_score_str}")
    print(f"  Glossary Score  : {g_score_str}")
    print("════════════════════════════════════════")

    if log_to_csv:
        log_result(model, prompt_version, b_score_str, g_score_str)

    return {
        "model": model,
        "prompt_version": prompt_version,
        "baseline_score": b_score_str,
        "glossary_score": g_score_str,
        "details": results_detail,
    }

if __name__ == "__main__":
    run_evaluation(MODEL, PROMPT_VERSION, log_to_csv=True)
