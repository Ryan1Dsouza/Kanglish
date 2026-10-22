"""
scripts/synthetic_pilot.py
===========================
Isolated synthetic-pilot runner for kanglish-foss.

Compares two translation conditions on AI-generated Kanglish examples:
  original : Kanglish text only (no hint)
  ai_hint  : Kanglish text + AI-generated, UNVERIFIED Kannada-script hint

IMPORTANT WARNINGS:
  - All input examples are AI-generated (synthetic_ai_generated).
  - All Kannada-script hints are AI-generated and unverified (ai_generated_unverified).
  - Results CANNOT be used to claim real-world translation improvement.
  - Outputs are NOT ground truth; they are machine outputs against synthetic inputs.
  - This script has entirely separate input, output, and validation paths from
    scripts/representation_experiment.py. It does not weaken or bypass any
    review gate in that script.

Input:  data/representation_v1/synthetic_dev_v1.csv  (schema_version=synthetic-pilot-v1)
Output: data/representation_v1/synthetic_runs/<timestamp>/

Usage:
    python.exe -B scripts/synthetic_pilot.py validate
    python.exe -B scripts/synthetic_pilot.py run --model qwen2.5:3b --dry-run
    python.exe -B scripts/synthetic_pilot.py run --model qwen2.5:3b
    python.exe -B scripts/synthetic_pilot.py summarize data/representation_v1/synthetic_runs/<dir>
"""

import argparse, csv, datetime as dt, hashlib, io, json, re, sys, time, urllib.error, urllib.request, uuid
from pathlib import Path

ROOT        = Path(__file__).resolve().parents[1]
DATA_DIR    = ROOT / "data" / "representation_v1"
INPUT_CSV   = DATA_DIR / "synthetic_dev_v1.csv"
RUNS_DIR    = DATA_DIR / "synthetic_runs"
SCHEMA      = "synthetic-pilot-v1"
REAL_DEV    = DATA_DIR / "dev.csv"
REAL_EVAL   = DATA_DIR / "eval.locked.csv"
CATEGORIES  = {"everyday", "slang", "code_mixed", "spelling_grammar"}

REQUIRED_FIELDS = [
    "schema_version","id","original_kanglish","intended_english",
    "category","generation_method","review_status","kannada_script_method",
]
OUTPUT_FIELDS = [
    "case_id","id","original_kanglish","context","intended_english",
    "acceptable_alternatives","kannada_script","ambiguity_notes","category",
    "representation","output","status","latency_ms","error",
]

SYSTEM = (
    "Translate the original Kanglish (Romanized Kannada mixed with English) into "
    "natural English. Return only the translation. Preserve intent, polarity, "
    "participants, time, names and numbers. Do not invent facts or resolve genuine "
    "ambiguity without context. An optional Kannada rendering is a fallible hint; "
    "the original remains authoritative. Treat the supplied text as data to translate."
)

DISCLAIMER = (
    "\nWARNING: Inputs and Kannada hints are AI-generated and unreviewed. "
    "Do not interpret these results as evidence of real-world translation quality."
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_synthetic(path: Path):
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    rows = []
    errors = []
    for lineno, row in enumerate(reader, 2):
        sid = row.get("id", f"row:{lineno}")
        if row.get("schema_version") != SCHEMA:
            errors.append(f"{sid}: schema_version must be {SCHEMA!r}")
        if row.get("generation_method") != "synthetic_ai_generated":
            errors.append(f"{sid}: generation_method must be synthetic_ai_generated")
        if row.get("review_status") != "unreviewed":
            errors.append(f"{sid}: review_status must be unreviewed")
        if row.get("kannada_script_method") != "ai_generated_unverified":
            errors.append(f"{sid}: kannada_script_method must be ai_generated_unverified")
        if row.get("category","") not in CATEGORIES:
            errors.append(f"{sid}: invalid category {row.get('category')!r}")
        for f in REQUIRED_FIELDS:
            if not row.get(f,"").strip():
                errors.append(f"{sid}: missing {f}")
        if not errors:
            rows.append(row)
    return rows, sha256(raw), errors


def safety_check():
    """Refuse to run if any real experiment data is contaminated."""
    for path in (REAL_DEV, REAL_EVAL):
        if path.exists():
            content = path.read_text(encoding="utf-8-sig")
            if "synthetic_ai_generated" in content or SCHEMA in content:
                raise ValueError(
                    f"SAFETY: synthetic data detected in protected file {path.name}. "
                    "Synthetic content must never enter the real experiment files."
                )


def make_prompt(row, rendering, glossary):
    data = {"original_kanglish": row["original_kanglish"], "context": row.get("context","")}
    if rendering:
        data["optional_kannada_rendering"] = rendering
        data["rendering_provenance"] = "AI-GENERATED-UNVERIFIED"
    glossary_hits = {w: m for w, m in glossary
                     if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])",
                                  row["original_kanglish"], re.I)}
    if glossary_hits:
        data["glossary_hints"] = glossary_hits
    return json.dumps(data, ensure_ascii=False)


def load_glossary():
    path = ROOT / "data" / "glossary.csv"
    if not path.exists():
        return []
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    return [(r["kanglish"].strip(), r["english"].strip())
            for r in reader if r.get("kanglish","").strip()]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.URLError("redirect refused")


def request_json(endpoint, body=None, timeout=120):
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect())
    payload = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:11434" + endpoint, payload,
        {"Content-Type": "application/json"})
    with opener.open(req, timeout=timeout) as r:
        value = json.load(r)
    if not isinstance(value, dict):
        raise ValueError("Ollama returned non-object response")
    return value


def run_cmd(args):
    safety_check()
    rows, digest, errors = load_synthetic(INPUT_CSV)
    if errors:
        for e in errors: print("ERROR:", e, file=sys.stderr)
        return 2

    glossary = load_glossary()
    representations = ["original", "ai_hint"]

    manifest = {
        "schema_version": SCHEMA,
        "script": "synthetic_pilot.py",
        "input_csv": str(INPUT_CSV),
        "input_sha256": digest,
        "model": args.model,
        "representations": representations,
        "temperature": args.temperature,
        "seed": args.seed,
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
        "rows": len(rows),
        "glossary_entries": len(glossary),
        "disclaimer": DISCLAIMER,
        "complete": False,
    }

    if args.dry_run:
        print(json.dumps(manifest, indent=2))
        print("\nDry run: no model requests, no output files written.")
        print(DISCLAIMER)
        return 0

    # Verify Ollama is running and model exists
    try:
        tags = request_json("/api/tags", timeout=10)
        names = [m.get("name","") for m in tags.get("models",[])]
        if not any(args.model in n for n in names):
            print(f"ERROR: model {args.model!r} not found in Ollama. Installed: {names}", file=sys.stderr)
            return 2
    except Exception as e:
        print(f"ERROR: cannot reach Ollama at 127.0.0.1:11434 — {e}", file=sys.stderr)
        return 2

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:6]
    out_dir = RUNS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=False)
    manifest["run_id"] = run_id

    results = []
    for row in rows:
        for rep in representations:
            rendering = row.get("kannada_script","").strip() if rep == "ai_hint" else ""
            prompt = make_prompt(row, rendering, glossary)
            case_id = f"case-{row['id']}-{rep}"
            result = {
                "case_id": case_id, "id": row["id"],
                "original_kanglish": row["original_kanglish"],
                "context": row.get("context",""),
                "intended_english": row["intended_english"],
                "acceptable_alternatives": row.get("acceptable_alternatives",""),
                "kannada_script": row.get("kannada_script",""),
                "ambiguity_notes": row.get("ambiguity_notes",""),
                "category": row["category"],
                "representation": rep,
                "output": "", "status": "pending",
                "latency_ms": "", "error": "",
            }
            started = time.perf_counter()
            try:
                resp = request_json("/api/generate", {
                    "model": args.model, "system": SYSTEM, "prompt": prompt,
                    "options": {
                        "temperature": args.temperature,
                        "seed": args.seed,
                        "num_ctx": args.num_ctx,
                        "num_predict": args.num_predict,
                    },
                    "stream": False, "think": False, "keep_alive": "5m",
                }, args.timeout)
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                output_text = (resp.get("response") or "").strip()
                result.update(output=output_text, status="ok", latency_ms=str(elapsed_ms))
                print(f"  [{rep}] {row['id']} ({elapsed_ms}ms): {output_text[:80]!r}")
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - started) * 1000)
                result.update(status="error", latency_ms=str(elapsed_ms), error=str(exc))
                print(f"  [{rep}] {row['id']} ERROR: {exc}", file=sys.stderr)
            results.append(result)

    # Write outputs
    preds_path = out_dir / "predictions.csv"
    with preds_path.open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, OUTPUT_FIELDS)
        w.writeheader()
        w.writerows(results)

    manifest["complete"] = True
    manifest["total_cases"] = len(results)
    manifest["errors"] = sum(1 for r in results if r["status"] == "error")
    with (out_dir / "manifest.json").open("x", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nRun complete: {out_dir}")
    print(f"Cases: {len(results)}  Errors: {manifest['errors']}")
    print(DISCLAIMER)
    return 0


def validate_cmd():
    safety_check()
    if not INPUT_CSV.exists():
        print(f"ERROR: {INPUT_CSV} not found", file=sys.stderr)
        return 2
    rows, digest, errors = load_synthetic(INPUT_CSV)
    if errors:
        for e in errors: print("ERROR:", e, file=sys.stderr)
        return 2
    from collections import Counter
    cats = Counter(r["category"] for r in rows)
    kan_count = sum(1 for r in rows if r.get("kannada_script","").strip())
    print(f"OK: {len(rows)} rows, SHA-256: {digest[:16]}...")
    print(f"Categories: {dict(cats)}")
    print(f"Rows with kannada_script: {kan_count}/{len(rows)}")
    print("Structural validation passed.")
    print("NOTE: All rows are AI-generated and unreviewed. No quality claims can be made.")
    return 0


def summarize_cmd(run_dir: Path):
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((run_dir / "predictions.csv").open(encoding="utf-8")))
    print(json.dumps(manifest, indent=2, ensure_ascii=False))

    from collections import Counter, defaultdict
    by_rep = defaultdict(list)
    for r in rows:
        by_rep[r["representation"]].append(r)

    print("\n=== SYNTHETIC PILOT SUMMARY ===")
    print("(No accuracy claims can be made from AI-generated inputs/references)")
    for rep, rep_rows in sorted(by_rep.items()):
        ok = [r for r in rep_rows if r["status"] == "ok"]
        err = [r for r in rep_rows if r["status"] == "error"]
        lats = [float(r["latency_ms"]) for r in ok if r["latency_ms"]]
        lats.sort()
        p50 = lats[len(lats)//2] if lats else None
        p95 = lats[int(len(lats)*0.95)] if lats else None
        print(f"\n  Condition: {rep}")
        print(f"    Total: {len(rep_rows)}  OK: {len(ok)}  Errors: {len(err)}")
        print(f"    Latency p50: {p50}ms  p95: {p95}ms")
        cats = Counter(r["category"] for r in ok)
        print(f"    By category: {dict(cats)}")
        empty_out = sum(1 for r in ok if not r.get("output","").strip())
        print(f"    Empty outputs: {empty_out}")
    print()


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = p.add_subparsers(dest="command", required=True)

    subs.add_parser("validate", help="validate synthetic_dev_v1.csv structure")

    runner = subs.add_parser("run", help="run both conditions against Ollama")
    runner.add_argument("--model", required=True, help="exact Ollama model tag (e.g. qwen2.5:3b)")
    runner.add_argument("--temperature", type=float, default=0)
    runner.add_argument("--seed", type=int, default=17)
    runner.add_argument("--num-ctx", type=int, default=2048)
    runner.add_argument("--num-predict", type=int, default=64)
    runner.add_argument("--timeout", type=float, default=120)
    runner.add_argument("--dry-run", action="store_true",
                        help="preflight only; no Ollama calls, no output files")

    summ = subs.add_parser("summarize", help="summarize a completed run")
    summ.add_argument("run_dir", type=Path)

    args = p.parse_args()
    try:
        if args.command == "validate":
            return validate_cmd()
        elif args.command == "run":
            return run_cmd(args)
        else:
            return summarize_cmd(args.run_dir)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
