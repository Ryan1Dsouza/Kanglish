"""
benchmark.py - Reproducible, safety-gated benchmark runner for kanglish-foss.

IMPORTANT: This script refuses to run formal scoring unless ALL benchmark rows
have review_status != 'unreviewed'. Use --smoke-test to test connectivity only.

Usage:
    python scripts/benchmark.py --smoke-test
        (Tests Ollama connectivity; does NOT claim translation accuracy)

    python scripts/benchmark.py --validate
        (Validates the benchmark CSV; checks for structural issues and near-duplicates
        against the leakage blacklist. Prints a report but does not call the model.)

    python scripts/benchmark.py --models qwen2.5:3b --prompt v1_baseline
        (Full run — blocked if any row has review_status=unreviewed)

    python scripts/benchmark.py --models qwen2.5:3b --row-limit 10 --smoke-test
        (Connectivity + output sanity on first 10 rows; no accuracy claimed)

Writes:
    results/benchmark_run_MODEL_PROMPT_MODE_TIMESTAMP.csv
    results/benchmark_summary_MODEL_PROMPT_MODE_TIMESTAMP.md
"""

import argparse, csv, datetime, difflib, json, math, os, re, sys, urllib.request

# ── UTF-8 on Windows ──────────────────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── CLI ───────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Kanglish benchmark runner")
parser.add_argument("--models", nargs="+", default=["qwen2.5:3b"],
                    help="Ollama model tag(s) to evaluate")
parser.add_argument("--prompt", default="v1_baseline",
                    help="Prompt variant name. Must be a known variant (no silent fallback).")
parser.add_argument("--benchmark", default="data/benchmark_test_v1_draft.csv",
                    help="Path to benchmark CSV")
parser.add_argument("--temperature", type=float, default=0.0)
parser.add_argument("--row-limit", type=int, default=None,
                    help="Evaluate only the first N rows (useful for debugging)")
parser.add_argument("--smoke-test", action="store_true",
                    help="Test connectivity and output format only. Does NOT report accuracy.")
parser.add_argument("--validate", action="store_true",
                    help="Validate benchmark CSV structure and contamination. No model calls.")
parser.add_argument("--blacklist", default="data/corpus/leakage_blacklist.txt",
                    help="Path to leakage blacklist file")
args = parser.parse_args()

MODELS = args.models
PROMPT_VERSION = args.prompt
BENCHMARK_PATH = args.benchmark
TEMPERATURE = args.temperature
ROW_LIMIT = args.row_limit
SMOKE_TEST = args.smoke_test
VALIDATE_ONLY = args.validate
BLACKLIST_PATH = args.blacklist
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# ── Prompt variants ───────────────────────────────────────────────────────────
PROMPT_VARIANTS = {
    "v1_baseline": {
        "system": (
            "You decode Kanglish: Kannada written in English letters, mixed with English, "
            "as used in college WhatsApp group chats. Spelling varies a lot. "
            "Reply with ONLY the natural English meaning, in one line."
        ),
        "shots": (
            "Kanglish: eno maadtidya?\nEnglish: What are you doing?\n\n"
            "Kanglish: nanna jothe bartiya?\nEnglish: Will you come with me?\n\n"
            "Kanglish: oota aitha?\nEnglish: Did you eat?\n\n"
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
            "Kanglish: eno maadtidya?\nEnglish: What are you doing?\n\n"
            "Kanglish: nanna jothe bartiya?\nEnglish: Will you come with me?\n\n"
            "Kanglish: oota aitha?\nEnglish: Did you eat?\n\n"
        ),
        "glossary_header": "Word meanings (use these meanings; output ONLY the English translation, no notes):\n",
        "clean_glossary": True,
    },
    "v3_strong_rules": {
        "system": (
            "You are a Kanglish-to-English translator. Follow these strict rules:\n"
            "1. Translate to fluent, natural English on a single line.\n"
            "2. Preserve question forms (end with ? if the input is a question).\n"
            "3. Preserve the grammatical subject.\n"
            "4. Never include explanations, notes, or parentheses.\n"
            "5. Translate all words; do not leave Kanglish words untranslated."
        ),
        "shots": (
            "Kanglish: naale bidthira?\nEnglish: Will you leave tomorrow?\n\n"
            "Kanglish: yenu guru samachara?\nEnglish: What is the news bro?\n\n"
            "Kanglish: thumba chennagide\nEnglish: It is very good.\n\n"
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
            "Kanglish: eno maadtidya?\nEnglish: What are you doing?\n\n"
            "Kanglish: nanna jothe bartiya?\nEnglish: Will you come with me?\n\n"
            "Kanglish: oota aitha?\nEnglish: Did you eat?\n\n"
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
            "Kanglish: ivattu bartiya?\nEnglish: Are you coming today?\n\n"
            "Kanglish: yenu maga plan?\nEnglish: What is the plan dude?\n\n"
            "Kanglish: thumba chennagide\nEnglish: It is very good.\n\n"
        ),
        "glossary_header": "Word meanings (translate using these, output only English):\n",
        "clean_glossary": True,
    },
}

# Strict: reject unknown prompt versions instead of silently falling back
if PROMPT_VERSION not in PROMPT_VARIANTS:
    known = ", ".join(sorted(PROMPT_VARIANTS))
    sys.exit(
        f"ERROR: Unknown prompt version '{PROMPT_VERSION}'.\n"
        f"Known versions: {known}\n"
        f"Refusing to run with an unintended prompt."
    )
VARIANT_CONFIG = PROMPT_VARIANTS[PROMPT_VERSION]

# ── Glossary ──────────────────────────────────────────────────────────────────
def load_glossary(path="data/glossary.csv"):
    g = {}
    try:
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                g[row["kanglish"].strip().lower()] = row["english"].strip()
    except FileNotFoundError:
        print(f"WARNING: Glossary not found at {path}; glossary mode will inject nothing.")
    return g

GLOSSARY = load_glossary()

def sanitize_meaning(m):
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", m)).strip()

def relevant_entries(text, clean=False):
    tl = text.lower()
    return [
        (w, sanitize_meaning(m) if clean else m)
        for w, m in GLOSSARY.items()
        if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", tl)
    ]

# ── Scoring (mirrors score.py; directional synonyms NOT merged) ───────────────
# NOTE: "going" and "coming" are intentionally in SEPARATE clusters.
# Merging them would treat directional opposites as equivalent, which is wrong
# for sentences like "Are you going?" vs "Are you coming?".
_RAW_SYNONYMS = [
    {"bro", "dude", "guru", "man", "buddy", "mate"},
    {"awesome", "great", "amazing", "fantastic", "cool", "nice"},
    {"plan", "schedule", "plans"},
    {"tomorrow", "tmrw"},
    {"go", "going", "goes"},      # departure direction only
    {"come", "coming", "comes"},  # arrival direction only
    {"today"},
]
SYNONYMS: dict = {}
for _cl in _RAW_SYNONYMS:
    _fs = frozenset(_cl)
    for _w in _cl:
        SYNONYMS[_w] = _fs

_STOP = {
    "a", "an", "the", "is", "it", "in", "on", "of", "to", "and", "or",
    "you", "i", "we", "they", "he", "she", "me", "my", "your", "our",
    "be", "do", "did", "was", "are", "were", "been", "has", "have",
    "will", "for", "at", "by", "with", "its", "this", "that", "what",
    "how", "who", "why", "when", "where", "please", "just", "not", "no",
}

def _stem(w):
    """Minimal suffix stripping. Handles double-consonant collapse (cancelled→cancel)."""
    for sfx in ("ning", "ing", "tion", "ed", "er", "es", "s"):
        if w.endswith(sfx) and len(w) - len(sfx) >= 3:
            stem = w[:-len(sfx)]
            # Collapse double trailing consonant after stripping (e.g. cancell→cancel)
            if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
                stem = stem[:-1]
            return stem
    return w

def _candidates(kw):
    sk = _stem(kw)
    syns = SYNONYMS.get(kw, frozenset()) | SYNONYMS.get(sk, frozenset())
    result = {kw, sk}
    for s in syns:
        result.add(s)
        result.add(_stem(s))
    return frozenset(result)

def _extract_output_words(out_lower):
    """Extract all words from output, add their stems.
    Uses set intersection instead of regex \b matching (matching score.py approach)."""
    raw_words = set(re.findall(r"[a-z]+", re.sub(r"'s\b", "", out_lower)))
    return raw_words | {_stem(w) for w in raw_words}

def _word_matches(kw, out_lower, _out_word_cache={}):
    """Check if keyword (or any of its candidates) appears in the output word set."""
    # Cache the output word set per out_lower to avoid recomputing per keyword
    if out_lower not in _out_word_cache:
        _out_word_cache[out_lower] = _extract_output_words(out_lower)
        # Keep cache bounded
        if len(_out_word_cache) > 500:
            _out_word_cache.clear()
            _out_word_cache[out_lower] = _extract_output_words(out_lower)
    out_words = _out_word_cache[out_lower]
    return bool(_candidates(kw) & out_words)

def keywords(ref):
    tokens = re.findall(r"[a-z]+", re.sub(r"'s\b", "", ref.lower()))
    return [t for t in tokens if t not in _STOP and len(t) > 2]

def semantic_pass(ref, output):
    kws = keywords(ref)
    if not kws:
        return True, 1.0, 0, 0
    out_lower = output.lower()
    matched = sum(1 for kw in kws if _word_matches(kw, out_lower))
    ratio = matched / len(kws)
    return ratio >= 0.70, round(ratio, 3), matched, len(kws)

_COMMENTARY_RE = re.compile(
    r"\(.*?\)|Translation\s*:|Note\s*:|Meaning\s*:|Here\s+is\s+the"
    r"|The\s+English\s+(translation|meaning)"
    r"|\bthis\s+(translates|means)\b",
    re.IGNORECASE,
)
_NEG_OUTPUT = re.compile(
    r"\b(not|no|don'?t|cannot|can'?t|won'?t|didn'?t|isn'?t|haven'?t|never|without)\b",
    re.IGNORECASE,
)
_NEG_KANGLISH = re.compile(
    r"\b(illa|beda|alla|aagalla|baralla|madalla|gottilla|bekagilla|barthilla|heltilla|nodalla)\b",
    re.IGNORECASE,
)

def intent_pass(kanglish, output):
    reasons = []
    is_q = kanglish.strip().endswith("?") or bool(
        re.search(
            r"\b(yaake|yaavaga|yenu|yaaru|yelli|yeshtu|hege|heege|illva|illvaa)\b",
            kanglish, re.IGNORECASE,
        )
    )
    if is_q and not output.strip().endswith("?"):
        reasons.append("question_not_preserved")
    if _NEG_KANGLISH.search(kanglish) and not _NEG_OUTPUT.search(output):
        reasons.append("negation_dropped")
    return (False, "|".join(reasons)) if reasons else (True, "ok")

def commentary_ok(output):
    return not bool(_COMMENTARY_RE.search(output))

# ── Error detection ───────────────────────────────────────────────────────────
_ERROR_PREFIX = re.compile(r"^\[ERROR:", re.IGNORECASE)

def is_error_response(output):
    """Return True if output is an error string, not a real translation."""
    return bool(_ERROR_PREFIX.match(output.strip()))

# ── Ollama call ───────────────────────────────────────────────────────────────
def call_model(model, prompt, temperature=0.0):
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
        "options": {"temperature": temperature},
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate", body,
        {"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60).read()
        return json.loads(resp)["response"].strip()
    except urllib.error.URLError as exc:
        return f"[ERROR: Ollama not reachable — {exc}]"
    except Exception as exc:
        return f"[ERROR: {exc}]"

def check_ollama(model):
    """Return (ok: bool, message: str)."""
    try:
        body = json.dumps({"model": model, "prompt": "ping", "stream": False}).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/generate", body,
            {"Content-Type": "application/json"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
        if "response" in resp:
            return True, "Ollama reachable and model responded"
        return False, f"Unexpected Ollama response: {resp}"
    except urllib.error.URLError as exc:
        return False, f"Ollama not reachable: {exc}"
    except Exception as exc:
        return False, f"Ollama error: {exc}"

# ── Prompt builders ───────────────────────────────────────────────────────────
def baseline_prompt(text, config):
    return config["system"] + "\n\n" + config["shots"] + f"Kanglish: {text}\nEnglish:"

def glossary_prompt_fn(text, config):
    prompt = config["system"] + "\n\n" + config["shots"]
    hits = relevant_entries(text, clean=config.get("clean_glossary", False))
    if hits:
        prompt += config["glossary_header"]
        for word, meaning in hits:
            prompt += f"  {word} = {meaning}\n"
        prompt += "\n"
    return prompt + f"Kanglish: {text}\nEnglish:"

# ── Benchmark CSV loading & validation ────────────────────────────────────────
REQUIRED_COLUMNS = [
    "id", "category", "kanglish_input", "primary_reference",
    "acceptable_alternatives", "disallowed_traps",
    "provenance", "source_url", "license", "review_status",
]
VALID_CATEGORIES = {
    "everyday_conversation", "bangalore_slang", "code_mixed",
    "questions", "grammatical_person", "tense_aspect",
    "negation", "ambiguous",
}

def _normalize(text):
    """Phonetic normalization for near-duplicate detection."""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    # collapse common spelling variants
    for a, b in [("ee", "i"), ("oo", "u"), ("th", "t"), ("dh", "d"),
                 ("aa", "a"), ("ii", "i"), ("nn", "n"), ("kk", "k")]:
        t = t.replace(a, b)
    return t

def load_blacklist(path):
    if not os.path.exists(path):
        print(f"WARNING: Blacklist not found at {path}")
        return []
    lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#"):
                lines.append(s)
    return lines

def validate_benchmark(rows, blacklist_sentences):
    """Check structural integrity and contamination. Returns list of issue strings."""
    issues = []
    seen_ids = {}
    seen_normalized = {}

    for i, r in enumerate(rows):
        row_label = r.get("id", f"row {i+2}")

        # Required columns present and non-empty
        for col in REQUIRED_COLUMNS:
            if col not in r:
                issues.append(f"{row_label}: missing column '{col}'")
            elif not r[col].strip() and col not in ("source_url", "acceptable_alternatives", "disallowed_traps"):
                issues.append(f"{row_label}: column '{col}' is empty")

        kinput = r.get("kanglish_input", "").strip()
        if not kinput:
            issues.append(f"{row_label}: empty kanglish_input")
            continue

        # Duplicate IDs
        rid = r.get("id", "")
        if rid in seen_ids:
            issues.append(f"{row_label}: duplicate ID (first at row {seen_ids[rid]+2})")
        seen_ids[rid] = i

        # Duplicate normalized inputs
        norm = _normalize(kinput)
        if norm in seen_normalized:
            issues.append(
                f"{row_label}: near-duplicate kanglish_input with {seen_normalized[norm]} "
                f"(normalized: '{norm}')"
            )
        seen_normalized[norm] = row_label

        # Valid category
        cat = r.get("category", "")
        if cat not in VALID_CATEGORIES:
            issues.append(f"{row_label}: unknown category '{cat}'")

        # Flagged references
        ref = r.get("primary_reference", "")
        if ref.startswith("[FLAGGED:"):
            issues.append(f"{row_label}: primary_reference is flagged — requires native speaker review before use")

        # Contamination: exact match against blacklist
        kinput_lower = kinput.lower()
        norm_input = _normalize(kinput)
        for bl_sentence in blacklist_sentences:
            if bl_sentence.lower() in kinput_lower:
                issues.append(f"{row_label}: EXACT contamination — input contains blacklisted phrase '{bl_sentence}'")
            else:
                # Near-duplicate check: similarity > 0.8 with any blacklist entry
                similarity = difflib.SequenceMatcher(
                    None, _normalize(bl_sentence), norm_input
                ).ratio()
                if similarity >= 0.80:
                    issues.append(
                        f"{row_label}: NEAR-DUPLICATE of blacklisted '{bl_sentence}' "
                        f"(similarity={similarity:.2f}) — manual inspection required"
                    )

    return issues

def load_benchmark(path, row_limit=None):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if row_limit:
        rows = rows[:row_limit]
    return rows

# ── Wilson CI ─────────────────────────────────────────────────────────────────
def wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z ** 2 / n
    c = (p + z ** 2 / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / d
    return max(0.0, round(c - m, 3)), min(1.0, round(c + m, 3))

# ── Main ──────────────────────────────────────────────────────────────────────
os.makedirs("results", exist_ok=True)

print(f"Loading benchmark: {BENCHMARK_PATH}")
benchmark = load_benchmark(BENCHMARK_PATH, ROW_LIMIT)
print(f"  {len(benchmark)} rows loaded (row_limit={ROW_LIMIT})")

blacklist = load_blacklist(BLACKLIST_PATH)
print(f"  {len(blacklist)} blacklist entries loaded from {BLACKLIST_PATH}")

# ── Validate mode ─────────────────────────────────────────────────────────────
print(f"\nRunning pre-flight validation...")
val_issues = validate_benchmark(benchmark, blacklist)
if val_issues:
    print(f"  VALIDATION ISSUES ({len(val_issues)}):")
    for issue in val_issues:
        print(f"    - {issue}")
else:
    print("  Validation: PASSED — no structural or contamination issues found")

if VALIDATE_ONLY:
    print("\n--validate flag set. Stopping after validation. No model calls made.")
    sys.exit(0)

# ── Review status gate ────────────────────────────────────────────────────────
unreviewed = [r["id"] for r in benchmark if r.get("review_status", "unreviewed") == "unreviewed"]
if unreviewed and not SMOKE_TEST:
    print(
        f"\nERROR: {len(unreviewed)} of {len(benchmark)} rows have review_status=unreviewed.\n"
        f"Formal benchmark scoring is BLOCKED until all rows are reviewed by a native speaker.\n\n"
        f"Options:\n"
        f"  1. Use --smoke-test to test connectivity only (no accuracy claimed).\n"
        f"  2. Review rows in data/benchmark_test_v1_draft.csv and update review_status.\n"
        f"  3. See research/BENCHMARK_REVIEW_ISSUES.md for known issues per row.\n\n"
        f"First 5 unreviewed IDs: {unreviewed[:5]}"
    )
    sys.exit(1)

if SMOKE_TEST:
    print(f"\n{'='*60}")
    print(f"SMOKE TEST MODE — connectivity and output format only.")
    print(f"No accuracy or translation quality is claimed.")
    print(f"{'='*60}")

# ── Check Ollama connectivity ─────────────────────────────────────────────────
for model in MODELS:
    ok, msg = check_ollama(model)
    print(f"Ollama [{model}]: {'OK' if ok else 'FAIL'} — {msg}")
    if not ok:
        sys.exit(f"ERROR: Cannot reach Ollama for model '{model}'. Aborting.")

# ── Evaluation loop ───────────────────────────────────────────────────────────
RUN_FIELDS = [
    "model", "prompt_version", "mode", "glossary_mode",
    "id", "category", "kanglish_input", "primary_reference",
    "review_status", "model_output", "is_error_response",
    "semantic_pass", "semantic_ratio", "matched_kws", "total_kws",
    "intent_pass", "intent_reason", "commentary_ok", "item_score",
    "timestamp",
]

all_results = []
run_label = f"{'smoke' if SMOKE_TEST else 'eval'}_{TIMESTAMP}"

for model in MODELS:
    print(f"\n{'='*60}\nModel: {model}  |  Prompt: {PROMPT_VERSION}\n{'='*60}")

    for mode_name, prompt_fn in [("baseline", baseline_prompt), ("glossary", glossary_prompt_fn)]:
        print(f"\n  Mode: {mode_name}")
        n_pass = n_error = n_skip = 0

        for i, row in enumerate(benchmark):
            row_ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            kanglish = row["kanglish_input"]
            reference = row.get("primary_reference", "")
            row_review = row.get("review_status", "unreviewed")

            prompt = prompt_fn(kanglish, VARIANT_CONFIG)
            output = call_model(model, prompt, TEMPERATURE)

            is_err = is_error_response(output)
            if is_err:
                n_error += 1
                sem_ok, sem_ratio, matched, total = False, 0.0, 0, 0
                int_ok, int_reason = False, "error_response"
                comm_ok = False
                score = False
                print(f"    [{i+1:3d}/{len(benchmark)}] ERROR {row['id']} — {output[:70]}")
            elif SMOKE_TEST:
                # In smoke test mode: check structure but do not claim accuracy
                sem_ok, sem_ratio, matched, total = False, 0.0, 0, 0
                int_ok, int_reason = False, "smoke_test_no_score"
                comm_ok = commentary_ok(output)
                score = False
                n_skip += 1
                print(f"    [{i+1:3d}/{len(benchmark)}] SMOKE {row['id']} — {output[:60]!r}")
            else:
                sem_ok, sem_ratio, matched, total = semantic_pass(reference, output)
                int_ok, int_reason = intent_pass(kanglish, output)
                comm_ok = commentary_ok(output)
                score = sem_ok and int_ok and comm_ok
                if score:
                    n_pass += 1
                status = "pass" if score else "FAIL"
                print(f"    [{i+1:3d}/{len(benchmark)}] {status} {row['id']} "
                      f"sem={sem_ratio:.2f}  {output[:55]!r}")

            all_results.append({
                "model": model,
                "prompt_version": PROMPT_VERSION,
                "mode": mode_name,
                "glossary_mode": "yes" if mode_name == "glossary" else "no",
                "id": row.get("id", ""),
                "category": row.get("category", ""),
                "kanglish_input": kanglish,
                "primary_reference": reference,
                "review_status": row_review,
                "model_output": output,
                "is_error_response": int(is_err),
                "semantic_pass": int(sem_ok) if not SMOKE_TEST and not is_err else "N/A",
                "semantic_ratio": sem_ratio if not SMOKE_TEST and not is_err else "N/A",
                "matched_kws": matched if not SMOKE_TEST and not is_err else "N/A",
                "total_kws": total if not SMOKE_TEST and not is_err else "N/A",
                "intent_pass": int(int_ok) if not SMOKE_TEST and not is_err else "N/A",
                "intent_reason": int_reason,
                "commentary_ok": int(comm_ok),
                "item_score": int(score) if not SMOKE_TEST and not is_err else "N/A",
                "timestamp": row_ts,
            })

        if not SMOKE_TEST:
            n_valid = len(benchmark) - n_error
            if n_valid > 0:
                lo, hi = wilson_ci(n_pass, n_valid)
                pct = 100 * n_pass / n_valid
                print(f"\n  {mode_name.upper()} TOTAL: {n_pass}/{n_valid} valid = {pct:.1f}%  "
                      f"[95% CI: {lo:.3f}-{hi:.3f}]"
                      f"  ({n_error} error responses excluded from score)")
            else:
                print(f"\n  {mode_name.upper()}: All {n_error} responses were errors.")
        else:
            print(f"\n  SMOKE TEST complete: {n_skip} outputs sampled, {n_error} errors. "
                  f"No accuracy figures claimed.")

# ── Write results CSV ─────────────────────────────────────────────────────────
safe_model = MODELS[0].replace(":", "_").replace("/", "_")
run_csv = f"results/benchmark_run_{safe_model}_{PROMPT_VERSION}_{run_label}.csv"
with open(run_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=RUN_FIELDS, quoting=csv.QUOTE_ALL)
    w.writeheader()
    w.writerows(all_results)
print(f"\nResults CSV: {run_csv}")

# ── Write summary markdown ────────────────────────────────────────────────────
summary_md = f"results/benchmark_summary_{safe_model}_{PROMPT_VERSION}_{run_label}.md"
groups: dict = {}
for r in all_results:
    groups.setdefault((r["model"], r["mode"]), []).append(r)

lines = [
    "# Kanglish Benchmark Summary", "",
    f"**Run type:** {'SMOKE TEST — no accuracy claimed' if SMOKE_TEST else 'FORMAL EVALUATION'}",
    f"**Timestamp:** {TIMESTAMP}",
    f"**Prompt:** {PROMPT_VERSION}",
    f"**Benchmark:** {BENCHMARK_PATH}",
    f"**Items evaluated:** {len(benchmark)}",
    f"**Models:** {', '.join(MODELS)}",
    "",
]

if SMOKE_TEST:
    lines += [
        "> [!WARNING]",
        "> This is a **smoke test** run only. Scores are not computed.",
        "> No translation accuracy is reported.",
        "",
    ]
elif unreviewed:
    lines += [
        "> [!CAUTION]",
        "> Some benchmark rows were `unreviewed` at evaluation time.",
        "> Scores should NOT be reported as final accuracy figures.",
        "",
    ]

lines += ["---", ""]

for (model, mode), rows in sorted(groups.items()):
    lines.append(f"## {model} — {mode}")
    lines.append("")

    if SMOKE_TEST:
        n_err = sum(r["is_error_response"] for r in rows)
        lines.append(f"Rows sampled: {len(rows)}, Error responses: {n_err}")
    else:
        n_valid = sum(1 for r in rows if not r["is_error_response"] and r["item_score"] != "N/A")
        n_pass = sum(1 for r in rows if r["item_score"] == 1)
        n_err = sum(r["is_error_response"] for r in rows)
        if n_valid > 0:
            lo, hi = wilson_ci(n_pass, n_valid)
            lines.append(f"**Overall:** {n_pass}/{n_valid} = {100*n_pass/n_valid:.1f}%  "
                         f"[95% CI: {lo:.3f}–{hi:.3f}]  ({n_err} errors excluded)")
        else:
            lines.append(f"**Overall:** All {n_err} responses were errors — no score computed.")
        lines.append("")

        cats: dict = {}
        for r in rows:
            cats.setdefault(r["category"], []).append(r)
        lines += [
            "### By Category", "",
            "| Category | Pass | Valid | % | CI 95% |",
            "|---|---|---|---|---|",
        ]
        for cat, cr in sorted(cats.items()):
            cv = sum(1 for x in cr if not x["is_error_response"] and x["item_score"] != "N/A")
            cp = sum(1 for x in cr if x["item_score"] == 1)
            clo, chi = wilson_ci(cp, cv) if cv > 0 else (0.0, 0.0)
            pct_s = f"{100*cp/cv:.1f}%" if cv > 0 else "N/A"
            lines.append(f"| {cat} | {cp} | {cv} | {pct_s} | [{clo:.3f}–{chi:.3f}] |")

        failing = [r for r in rows if r["item_score"] == 0 and not r["is_error_response"]]
        if failing:
            lines += [
                "", f"### Failing Examples ({len(failing)} items)", "",
                "| ID | Category | Kanglish | Output | Sem | Int | Comm |",
                "|---|---|---|---|---|---|---|",
            ]
            for r in failing[:30]:
                lines.append(
                    f"| {r['id']} | {r['category']} | {r['kanglish_input'][:38]} "
                    f"| {r['model_output'][:48]} "
                    f"| {r['semantic_pass']} | {r['intent_pass']} | {r['commentary_ok']} |"
                )
            if len(failing) > 30:
                lines.append(f"_... and {len(failing)-30} more — see {run_csv}_")
    lines += ["", "---", ""]

with open(summary_md, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Summary MD: {summary_md}")
