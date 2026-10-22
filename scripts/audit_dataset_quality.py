"""Read-only dataset audit; writes diagnostics only to a new results directory.

Uses existing source references, never creates gold translations or changes data.
Run: python -B scripts/audit_dataset_quality.py --out results/audit_YYYYMMDD
"""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.trusted_pipeline.schema import TrustedRecord


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def punctuation_normalized(value):
    return " ".join(re.sub(r"[^\w\s]", " ", normalized(value)).split())


def checksum(path):
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def jsonl(path):
    with path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def pair(row):
    if "messages" not in row:
        return row.get("kanglish", ""), row.get("english", "")
    return tuple(next((m["content"] for m in row["messages"] if m["role"] == role), "")
                 for role in ("user", "assistant"))


def audit():
    protected = ["data/test.csv", "data/dev.csv", "data/glossary.csv",
                 "data/benchmark_test_v1_draft.csv", "data/representation_v1/dev.csv",
                 "data/representation_v1/eval.locked.csv"]
    report = {"created_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Structural audit and diagnostic sampling, not an accuracy benchmark.",
              "normalization": "NFKC, casefold, whitespace collapse; loose overlap additionally removes punctuation.",
              "protected_sha256": {p: checksum(ROOT / p) for p in protected},
              "processed": {}}
    datasets = {}
    for path in sorted((ROOT / "data/processed").glob("*.jsonl")):
        records = list(jsonl(path))  # A malformed line fails the audit visibly.
        pairs = [pair(row) for row in records]
        datasets[path.name] = pairs
        targets = defaultdict(set)
        for source, target in pairs:
            targets[normalized(source)].add(normalized(target))
        conflicting = {k: sorted(v) for k, v in targets.items() if len(v) > 1}
        report["processed"][path.name] = {
            "sha256": checksum(path), "rows": len(records),
            "unique_normalized_inputs": len(targets),
            "duplicate_input_extras": len(pairs) - len(targets),
            "duplicate_pair_extras": len(pairs) - len({(normalized(k), normalized(e)) for k, e in pairs}),
            "multiple_target_inputs": len(conflicting),
            "multiple_target_examples": list(conflicting.items())[:10],
            "empty_pair_rows": sum(not k.strip() or not e.strip() for k, e in pairs),
            "input_contains_kannada": sum(bool(re.search("[\u0c80-\u0cff]", k)) for k, e in pairs),
            "target_contains_kannada": sum(bool(re.search("[\u0c80-\u0cff]", e)) for k, e in pairs),
            "target_is_cross_reference": sum(e.lstrip().startswith("=") for k, e in pairs),
            "non_english_target_examples": [(k, e) for k, e in pairs if re.search("[\u0c80-\u0cff]", e)][:5],
            "input_contains_non_ascii_latin": sum(any(ord(c) > 127 and "LATIN" in unicodedata.name(c, "") for c in k) for k, e in pairs),
            "top_level_keys": dict(Counter(k for row in records for k in row)),
        }

    training = datasets["kanglish_v3_train.jsonl"]
    train_inputs = {normalized(k) for k, e in training}
    loose_inputs = {punctuation_normalized(k) for k, e in training}
    vocab = {normalized(token) for k, e in training for token in re.split(r"[\s()!?.,/;:\[\]{}]+", k)}
    base = datasets["kanglish_clean_train.jsonl"]
    split = int(len(training) * 0.98)
    train_prefix = {normalized(k) for k, e in training[:split]}
    loose_prefix = {punctuation_normalized(k) for k, e in training[:split]}
    teacher_rows = list(jsonl(ROOT / "data/processed/gemini_teacher_dataset.jsonl"))
    report["v3_composition"] = {
        "clean_base_is_prefix": training[:len(base)] == base,
        "base_rows": len(base), "appended_teacher_rows": len(training) - len(base),
        "teacher_models": dict(Counter(r.get("teacher", r.get("source", "missing")) for r in teacher_rows)),
        "teacher_review_statuses": dict(Counter(r.get("review_status", "missing") for r in teacher_rows)),
        "sequential_split_train_rows": split, "sequential_split_validation_rows": len(training) - split,
        "validation_is_all_appended_teacher": split >= len(base),
        "validation_exact_input_overlap": sum(normalized(k) in train_prefix for k, e in training[split:]),
        "validation_punctuation_normalized_overlap": sum(punctuation_normalized(k) in loose_prefix for k, e in training[split:]),
    }

    report["evaluation"] = {}
    evaluation_files = [("data/test.csv", "kanglish"),
                        ("data/benchmark_test_v1_draft.csv", "kanglish_input"),
                        ("data/representation_v1/dev.csv", "original_kanglish"),
                        ("data/representation_v1/eval.locked.csv", "original_kanglish"),
                        ("data/representation_v1/synthetic_dev_v1.csv", "original_kanglish")]
    for filename, field in evaluation_files:
        records = csv_rows(ROOT / filename)
        report["evaluation"][filename] = {
            "rows": len(records),
            "review_statuses": dict(Counter(r.get("review_status", "not_recorded") for r in records)),
            "exact_v3_overlap": [r[field] for r in records if normalized(r[field]) in train_inputs],
            "punctuation_normalized_v3_overlap": [r[field] for r in records if punctuation_normalized(r[field]) in loose_inputs],
        }

    counts, status, sources, schema_errors, provenance_gaps = (Counter() for _ in range(5))
    headwords = Counter()
    candidates = []
    reviewer_labels = Counter()
    lexicon_quality = Counter()
    for row in jsonl(ROOT / "data/trusted/trusted_master.jsonl"):
        counts[row["data_type"]] += 1
        status[row["review_status"]] += 1
        sources[row["source"]] += 1
        schema_errors.update(TrustedRecord.from_dict(row).validate())
        if not row.get("source_url"):
            provenance_gaps["missing_source_url"] += 1
        if not re.fullmatch(r"(?:sha256:)?[0-9a-fA-F]{64}", row.get("source_checksum", "")):
            provenance_gaps["non_sha256_source_checksum"] += 1
        if row["review_status"] == "human-verified":
            reviewer_labels.update(row.get("reviewers", "").split("|"))
        if row["data_type"] == "lexicon":
            source, native, target = row["original_kanglish"], row["kannada_script"], row["english_meaning"]
            lexicon_quality["target_contains_kannada"] += bool(re.search("[\u0c80-\u0cff]", target))
            lexicon_quality["target_is_cross_reference"] += target.lstrip().startswith("=")
            headwords[normalized(source)] += 1
            if (re.fullmatch(r"[A-Za-z]{3,20}", source) and len(target) <= 70 and ";" not in target
                    and not re.search("[\u0c80-\u0cff]", target) and re.search("[A-Za-z]", target)
                    and not target.lstrip().startswith("=")
                    and normalized(source) not in vocab and normalized(source) not in train_inputs
                    and normalized(native) not in vocab and normalized(native) not in train_inputs):
                candidates.append(row)
    report["trusted_catalog"] = {
        "rows": sum(counts.values()), "data_types": dict(counts), "review_statuses": dict(status),
        "sources": dict(sources), "schema_errors": dict(schema_errors),
        "provenance_gaps": dict(provenance_gaps), "human_verified_reviewer_labels": dict(reviewer_labels),
        "lexicon_content_flags": dict(lexicon_quality),
        "note": "Schema success cannot authenticate reviewer identities or translation correctness.",
    }
    eligible = sorted((r for r in candidates if headwords[normalized(r["original_kanglish"])] == 1), key=lambda r: r["entry_id"])
    selected = random.Random(20261019).sample(eligible, min(8, len(eligible)))
    report["heldout_dictionary_sampling"] = {
        "seed": 20261019, "eligible_rows": len(eligible),
        "method": "One catalogue entry per ASCII headword, 3-20 letters, definition <=70 characters without semicolon, Kannada or cross-reference; exact headword/native form absent from v3 examples and whitespace/punctuation vocabulary. Does not establish absence from model pretraining or related word families.",
    }
    cases = []
    for row in csv_rows(ROOT / "data/test.csv"):
        cases.append({"group": "existing_owner_test", "input": row["kanglish"],
                      "reference": row["english"], "reference_path": "data/test.csv"})
    for row in random.Random(20261019).sample(csv_rows(ROOT / "data/benchmark_test_v1_draft.csv"), 6):
        cases.append({"group": "unreviewed_synthetic_draft", "input": row["kanglish_input"],
                      "reference": row["primary_reference"], "reference_id": row["id"],
                      "reference_path": "data/benchmark_test_v1_draft.csv", "review_status": row["review_status"]})
    for row in selected:
        for field in ("original_kanglish", "kannada_script"):
            cases.append({"group": "heldout_dictionary_" + field, "input": row[field],
                          "reference": row["english_meaning"], "reference_id": row["entry_id"],
                          "reference_path": "data/trusted/trusted_master.jsonl", "review_status": row["review_status"]})
    for source in ("zqxvpl", "blorptaka", "zzkrrmppo", "qzxv nplk"):
        cases.append({"group": "artificial_unknown_input", "input": source, "reference": None,
                      "note": "Artificial negative control; no gold translation asserted."})
    for i, case in enumerate(cases, 1):
        case["case_id"] = f"diagnostic-{i:02d}"
        case["exact_v3_input_seen"] = normalized(case["input"]) in train_inputs
    report["probe_cases"] = cases
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    destination = args.out.resolve()
    if not destination.is_relative_to((ROOT / "results").resolve()):
        parser.error("Output must be inside this repository's results directory.")
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "dataset_audit.json"
    if output.exists():
        parser.error("Choose a new directory; existing audit evidence is never overwritten.")
    report = audit()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Audited {len(report['processed'])} processed files and {report['trusted_catalog']['rows']} trusted records.")
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
