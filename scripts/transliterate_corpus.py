"""
scripts/transliterate_corpus.py
Phase 5 - Dictionary-based transliteration baseline.

Loads Aksharantar Kannada word pairs as a lookup table, then converts
Kannada-script training sentences into Romanized Latin (Kanglish-like) forms.

IMPORTANT CAVEATS:
  - Word-level dictionary lookup only. Inflected/compound/colloquial forms
    not in Aksharantar will be marked <<UNK>> -- never silently guessed.
  - Output labelled machine_transliterated, review_status=unreviewed.
  - Do NOT treat output as authentic Kanglish or verified training data.
  - Never mix output into the locked evaluation benchmark.

Usage:
    python.exe scripts/transliterate_corpus.py --unit-test
    python.exe scripts/transliterate_corpus.py --limit 200
    python.exe scripts/transliterate_corpus.py --limit 1000 --out data/processed/kanglish_candidates_v1.csv
"""

import argparse, csv, io, json, os, re, sys, zipfile
from collections import Counter, defaultdict
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8","utf-8-sig"):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

_KAN_RANGE = re.compile(r"[\u0C80-\u0CFF]")
UNK_MARKER = "<<UNK>>"
AMB_MARKER = "<<AMB>>"

def is_kannada_token(tok):
    return bool(_KAN_RANGE.search(tok))

def is_latin_token(tok):
    return bool(re.match(r"^[A-Za-z0-9\'\-]+$", tok))

def load_aksharantar(zip_path, split="train", verbose=True):
    """Load Aksharantar JSONL. Returns (native_to_roman dict, roman_to_native dict)."""
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Aksharantar zip not found: {zip_path}")
    member_map = {"train":"kan_train.json","valid":"kan_valid.json","test":"kan_test.json"}
    member = member_map.get(split, "kan_train.json")
    if verbose:
        print(f"Loading Aksharantar '{split}' from {zip_path}...")
    native_to_roman = defaultdict(list)
    roman_to_native = defaultdict(list)
    total = 0; skipped = 0
    with zipfile.ZipFile(zip_path,"r") as zf:
        with zf.open(member) as raw:
            for line in io.TextIOWrapper(raw, encoding="utf-8", errors="replace"):
                line = line.strip()
                if not line: continue
                try: rec = json.loads(line)
                except json.JSONDecodeError: skipped += 1; continue
                native = rec.get("native word","").strip()
                roman  = rec.get("english word","").strip().lower()
                if native and roman:
                    native_to_roman[native].append(roman)
                    roman_to_native[roman].append(native)
                    total += 1
                else: skipped += 1
    if verbose:
        print(f"  Loaded {total:,} pairs. Unique native: {len(native_to_roman):,}. "
              f"Unique roman: {len(roman_to_native):,}. Skipped: {skipped}.")
    native_to_roman = {k: list(dict.fromkeys(v)) for k,v in native_to_roman.items()}
    roman_to_native = {k: list(dict.fromkeys(v)) for k,v in roman_to_native.items()}
    return native_to_roman, roman_to_native

_PUNCT_RE = re.compile(r"([.,!?;:\"()\[\]{}/\\%])")

def tokenize(sentence):
    """Tokenize preserving punctuation as separate elements."""
    tokens = []
    for raw_tok in sentence.split():
        parts = _PUNCT_RE.split(raw_tok)
        for p in parts:
            if p: tokens.append((p, bool(_PUNCT_RE.fullmatch(p))))
    return tokens

def transliterate_sentence(sentence, native_to_roman):
    """Convert Kannada sentence word-by-word. Returns (romanized, stats, details)."""
    tokens = tokenize(sentence)
    out_parts = []; details = []
    c = Counter()
    for tok, is_p in tokens:
        if is_p:
            out_parts.append(tok); c["n_punct"]+=1
            details.append({"token":tok,"type":"punct","output":tok,"candidates":[]})
            continue
        if re.match(r"^[\d.,]+$", tok) and not is_kannada_token(tok):
            out_parts.append(tok); c["n_numeric"]+=1
            details.append({"token":tok,"type":"numeric","output":tok,"candidates":[]})
            continue
        if is_latin_token(tok) and not is_kannada_token(tok):
            out_parts.append(tok); c["n_latin"]+=1
            details.append({"token":tok,"type":"latin_preserved","output":tok,"candidates":[]})
            continue
        if is_kannada_token(tok):
            c["n_kannada"]+=1
            cands = native_to_roman.get(tok,[])
            if not cands:
                out_parts.append(UNK_MARKER); c["n_unmatched"]+=1
                details.append({"token":tok,"type":"kannada_unknown","output":UNK_MARKER,"candidates":[]})
            elif len(cands)==1:
                out_parts.append(cands[0]); c["n_matched"]+=1
                details.append({"token":tok,"type":"kannada_matched","output":cands[0],"candidates":cands})
            else:
                out_parts.append(AMB_MARKER+cands[0]); c["n_matched"]+=1; c["n_ambiguous"]+=1
                details.append({"token":tok,"type":"kannada_ambiguous","output":cands[0],"candidates":cands[:3]})
        else:
            out_parts.append(UNK_MARKER); c["n_unmatched"]+=1
            details.append({"token":tok,"type":"other_unknown","output":UNK_MARKER,"candidates":[]})
    romanized = " ".join(out_parts)
    romanized = re.sub(r" ([.,!?;:])",r"\1",romanized)
    nk = c["n_kannada"]
    stats = {
        "n_kannada": nk,
        "n_matched":   c["n_matched"],
        "n_unmatched": c["n_unmatched"],
        "n_ambiguous": c["n_ambiguous"],
        "n_latin":     c["n_latin"],
        "n_punct":     c["n_punct"],
        "n_numeric":   c["n_numeric"],
        "coverage": round(c["n_matched"]/nk,4) if nk>0 else 1.0,
        "has_unk":  c["n_unmatched"]>0,
        "has_amb":  c["n_ambiguous"]>0,
    }
    return romanized, stats, details

def load_training_corpus(parquet_path, limit=None, verbose=True):
    """Load english_sentences/kannada_sentences from parquet. Safety-blocks eval file."""
    import pyarrow.parquet as pq
    canonical = os.path.normcase(os.path.abspath(parquet_path))
    eval_path = os.path.normcase(os.path.abspath(
        "data/raw/in22_conv/in22_conv_mteb_default_test.parquet"))
    if canonical == eval_path:
        raise ValueError(
            "SAFETY BLOCK: Attempted to load IN22-Conv evaluation file as training data. "
            "This file is evaluation-only. Use a different source.")
    if verbose: print(f"Loading corpus from {parquet_path}...")
    table = pq.read_table(parquet_path)
    eng_col = table.column("english_sentences").to_pylist()
    kan_col = table.column("kannada_sentences").to_pylist()
    rows = []
    for i,(e,k) in enumerate(zip(eng_col,kan_col)):
        if e and k and e.strip() and k.strip():
            rows.append((i, e.strip(), k.strip()))
        if limit and len(rows)>=limit: break
    if verbose: print(f"  Loaded {len(rows):,} rows (limit={limit}).")
    return rows

def run_pipeline(args):
    TS = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    native_to_roman, _ = load_aksharantar(args.aksharantar_zip, split="train", verbose=True)
    corpus = load_training_corpus(args.training_parquet, limit=args.limit, verbose=True)
    print(f"\nTransliterating {len(corpus)} sentences...")

    candidates = []
    agg = Counter()
    failures = []
    THRESH = 0.50

    for seq_i,(row_idx,english,kannada) in enumerate(corpus):
        romanized, stats, details = transliterate_sentence(kannada, native_to_roman)
        agg["total"]+=1
        for k,v in stats.items():
            if isinstance(v,(int,float)) and k!="coverage": agg[k]+=v
        if stats["coverage"]<THRESH and stats["n_kannada"]>0:
            agg["low_coverage"]+=1
            if len(failures)<20:
                failures.append({"row_idx":row_idx,"kan":kannada,"rom":romanized,"cov":stats["coverage"]})
        if stats["n_matched"]==0 and stats["n_kannada"]>0:
            continue  # zero coverage - skip
        candidates.append({
            "id": f"KANG-CAND-{seq_i+1:05d}",
            "romanized_input": romanized,
            "original_kannada": kannada,
            "english_reference": english,
            "source_dataset": "ramachandrajoshi/english-kannada-cleaned",
            "source_split": "train",
            "source_row_index": row_idx,
            "source_url": "https://huggingface.co/datasets/ramachandrajoshi/english-kannada-cleaned",
            "license": "Apache-2.0",
            "upstream_provenance": "damerajee/en-kannada (cleaned by ramachandrajoshi)",
            "transliteration_method": "aksharantar_dictionary_v1",
            "aksharantar_source": "ai4bharat/Aksharantar train (CC0/CC-BY-4.0)",
            "coverage_score": stats["coverage"],
            "n_kannada_tokens": stats["n_kannada"],
            "n_matched": stats["n_matched"],
            "n_unmatched": stats["n_unmatched"],
            "n_ambiguous": stats["n_ambiguous"],
            "has_unk_tokens": stats["has_unk"],
            "has_ambiguous_tokens": stats["has_amb"],
            "generation_method": "machine_transliterated",
            "review_status": "unreviewed",
            "generated_at": TS,
            "notes": (
                "AUTO-GENERATED by Aksharantar dictionary lookup. NOT authentic Kanglish. "
                "Requires native speaker review. UNK=word absent from dictionary."
            ),
        })

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    if candidates:
        with open(args.out,"w",newline="",encoding="utf-8-sig") as f:
            w = csv.DictWriter(f,fieldnames=list(candidates[0].keys()),quoting=csv.QUOTE_ALL)
            w.writeheader(); w.writerows(candidates)

    total = agg["total"]; total_kan = agg["n_kannada"]
    print(f"\n{'='*60}")
    print(f"COVERAGE REPORT")
    print(f"{'='*60}")
    print(f"  Sentences processed    : {total:,}")
    print(f"  Candidates written     : {len(candidates):,}")
    print(f"  Total Kannada tokens   : {total_kan:,}")
    m = agg["n_matched"]; u = agg["n_unmatched"]; mb = agg["n_ambiguous"]
    print(f"  Tokens matched         : {m:,} ({100*m/max(total_kan,1):.1f}%)")
    print(f"  Tokens unmatched (UNK) : {u:,} ({100*u/max(total_kan,1):.1f}%)")
    print(f"  Tokens ambiguous (AMB) : {mb:,} ({100*mb/max(total_kan,1):.1f}%)")
    print(f"  Sentences with UNK     : {agg['has_unk']:,} ({100*agg['has_unk']/max(total,1):.1f}%)")
    print(f"  Low-coverage (<50%)    : {agg['low_coverage']:,} ({100*agg['low_coverage']/max(total,1):.1f}%)")
    print(f"\n  Output: {args.out}")

    if failures:
        print(f"\n  Sample failures (coverage<{THRESH}):")
        for ex in failures[:8]:
            print(f"    [{ex['cov']:.2f}] {ex['kan'][:55]!r}")
            print(f"           -> {ex['rom'][:70]!r}")

    if total_kan>0 and u/total_kan > 0.40:
        print(f"\n  WARNING: {100*u/total_kan:.0f}% of Kannada tokens unmatched.")
        print(f"  Dictionary baseline is insufficient for this corpus.")
        print(f"  RECOMMENDATION: Evaluate ai4bharat/IndicXlit (sequence-to-sequence)")
        print(f"  as a replacement transliterator for unknown token recovery.")

    return candidates, agg, failures

def run_unit_tests():
    print("=== Unit Tests: transliterate_corpus.py ===\n")
    P=[0]; F=[0]
    def ok(name, cond, detail=""):
        if cond: print(f"  PASS: {name}"); P[0]+=1
        else:    print(f"  FAIL: {name}"+(f"  ({detail})" if detail else "")); F[0]+=1

    mock = {
        "ನಾಳೆ":   ["naale"],
        "ಹೋಗಣ":   ["hogana"],
        "ಸಿನ್ಮಾ": ["sinema","cinema"],
        "ರಜೆ":    ["raje"],
    }

    print("--- Punctuation preservation ---")
    r,s,_ = transliterate_sentence("ನಾಳೆ ಹೋಗಣ.", mock)
    ok("trailing period preserved", r.endswith("."), repr(r))
    ok("no space before period", " ." not in r, repr(r))

    print("\n--- Latin token preservation ---")
    r,s,d = transliterate_sentence("Hello ನಾಳೆ", mock)
    ok("Hello preserved", "Hello" in r, repr(r))
    ok("latin_preserved type", any(x["type"]=="latin_preserved" for x in d))

    print("\n--- Unknown token handling ---")
    r,s,d = transliterate_sentence("ಅಮ್ಮಾ ನಾಳೆ", mock)
    ok("UNK marker present", UNK_MARKER in r, repr(r))
    ok("has_unk=True", s["has_unk"])
    ok("n_unmatched=1", s["n_unmatched"]==1, str(s["n_unmatched"]))
    ok("kannada_unknown type logged", any(x["type"]=="kannada_unknown" for x in d))

    print("\n--- Ambiguous entry ---")
    r,s,d = transliterate_sentence("ಸಿನ್ಮಾ", mock)
    ok("AMB marker in output", AMB_MARKER in r, repr(r))
    ok("has_amb=True", s["has_amb"])
    ok("n_ambiguous=1", s["n_ambiguous"]==1, str(s["n_ambiguous"]))
    ok("2 candidates stored", len(d[0]["candidates"])==2)

    print("\n--- Repeated word ---")
    r,s,_ = transliterate_sentence("ನಾಳೆ ನಾಳೆ ನಾಳೆ", mock)
    ok("all 3 matched", s["n_matched"]==3, str(s["n_matched"]))
    ok("no UNK", UNK_MARKER not in r, repr(r))

    print("\n--- Pure English (code-mixed) ---")
    r,s,_ = transliterate_sentence("Hello world, how are you?", mock)
    ok("no Kannada tokens", s["n_kannada"]==0)
    ok("coverage=1.0", s["coverage"]==1.0)
    ok("English words preserved", "Hello" in r and "world" in r)

    print("\n--- Coverage score ---")
    r,s,_ = transliterate_sentence("ನಾಳೆ ಅಮ್ಮಾ", mock)
    ok("coverage=0.5", s["coverage"]==0.5, str(s["coverage"]))

    print("\n--- Deterministic output ---")
    r1,_,_ = transliterate_sentence("ನಾಳೆ ಸಿನ್ಮಾ", mock)
    r2,_,_ = transliterate_sentence("ನಾಳೆ ಸಿನ್ಮಾ", mock)
    ok("deterministic", r1==r2)

    print("\n--- Safety block: eval file rejected ---")
    try:
        load_training_corpus("data/raw/in22_conv/in22_conv_mteb_default_test.parquet",
                             limit=1, verbose=False)
        ok("eval blocked", False, "ValueError NOT raised!")
    except ValueError as e:
        ok("eval blocked", "SAFETY BLOCK" in str(e))
    except Exception as e:
        ok("eval blocked", False, f"wrong exception: {e}")

    print("\n--- Numeric token handling ---")
    r,s,d = transliterate_sentence("90% ರಜೆ", mock)
    ok("numeric preserved", "90" in r or "%" in r, repr(r))
    ok("raje matched", "raje" in r, repr(r))

    print("\n--- Question mark preserved ---")
    r,s,_ = transliterate_sentence("ನಾಳೆ ಹೋಗಣ?", mock)
    ok("question mark at end", r.strip().endswith("?"), repr(r))
    ok("no space before ?", " ?" not in r, repr(r))

    print(f"\n=== Results: {P[0]} passed, {F[0]} failed ===")
    return F[0]==0

def main():
    p = argparse.ArgumentParser(description="Phase 5 transliteration pipeline")
    p.add_argument("--aksharantar-zip",  default="data/raw/aksharantar/kan.zip")
    p.add_argument("--training-parquet", default="data/raw/en_kan_cleaned/train_0000.parquet")
    p.add_argument("--out", default="data/processed/kanglish_candidates_v1.csv")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--unit-test", action="store_true")
    args = p.parse_args()
    if args.unit_test:
        sys.exit(0 if run_unit_tests() else 1)
    run_pipeline(args)

if __name__=="__main__":
    main()
