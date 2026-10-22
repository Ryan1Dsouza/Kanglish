import json
import hashlib
from pathlib import Path

SYSTEM_INSTRUCTION = (
    "You are an expert translator for Coastal Karnataka languages (Kannada, Tulu, Konkani, Kanglish). "
    "Translate the user's Romanized input into natural, accurate English. Output only the English translation."
)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def build_qwen_chatml_record(entry: dict) -> dict:
    src = entry["source"].strip()
    tgt = entry["translation"].strip()
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": src},
            {"role": "assistant", "content": tgt}
        ],
        "text": (
            f"<|im_start|>system\n{SYSTEM_INSTRUCTION}<|im_end|>\n"
            f"<|im_start|>user\n{src}<|im_end|>\n"
            f"<|im_start|>assistant\n{tgt}<|im_end|>\n"
        ),
        "metadata": {
            "language": entry.get("language", "unknown"),
            "literal": entry.get("literal", ""),
            "notes": entry.get("notes", "")
        }
    }

def build_quality_v1_candidate(idx: int, entry: dict, corpus_hash: str) -> dict:
    src = entry["source"].strip()
    tgt = entry["translation"].strip()
    entry_id = f"MANG-CHAT-{idx:06d}"
    return {
        "id": f"{entry_id}:latin",
        "group_id": entry_id,
        "review_status": "verified",
        "source_type": "conversational",
        "provenance": [{
            "entry_id": entry_id,
            "source": "mangalore_chat_corpus",
            "license": "CC0-1.0",
            "attribution": "Mangalorean Trilingual Chat Corpus",
            "source_url": "data/corpus/mangalore_chat_corpus.jsonl",
            "source_checksum": corpus_hash,
            "review_status": "verified",
            "catalog_path": "data/corpus/mangalore_chat_corpus.jsonl"
        }],
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": src},
            {"role": "assistant", "content": tgt}
        ]
    }

def build_student_gate_a_candidate(idx: int, entry: dict, corpus_hash: str) -> dict:
    src = entry["source"].strip()
    tgt = entry["translation"].strip()
    entry_id = f"MANG-CHAT-{idx:06d}"
    return {
        "id": f"{entry_id}:0",
        "source_group": entry_id,
        "category": "conversation",
        "romanized_input": src,
        "english": tgt,
        "original_kannada": "",
        "source": "mangalore_chat_corpus",
        "license": "CC0-1.0",
        "provenance": {
            "entry_id": entry_id,
            "source": "mangalore_chat_corpus",
            "license": "CC0-1.0",
            "attribution": "Mangalorean Trilingual Chat Corpus",
            "source_url": "data/corpus/mangalore_chat_corpus.jsonl",
            "source_checksum": corpus_hash
        },
        "reference_authority": "mangalorean_chat_corpus",
        "review_status": "approved",
        "source_review_status": "verified",
        "variant": "base",
        "transliteration_method": "native_informal_romanized",
        "also_in_quality_v1": True,
        "names": [],
        "latin_spans": [],
        "split_group": f"mangalore_{idx:06d}",
        "split": "train",
        "parent_input": src,
        "prompt": (
            f"<|im_start|>system\n{SYSTEM_INSTRUCTION}<|im_end|>\n"
            f"<|im_start|>user\n{src}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        ),
        "glossary_hints": [],
        "would_use_exact_glossary": False
    }

def main():
    repo_root = Path(__file__).resolve().parent.parent
    corpus_path = repo_root / "data" / "corpus" / "mangalore_chat_corpus.jsonl"
    blacklist_path = repo_root / "data" / "corpus" / "leakage_blacklist.txt"
    quality_dir = repo_root / "data" / "processed" / "quality_v1"
    gate_a_dir = repo_root / "data" / "processed" / "student_gate_a_v1"

    quality_dir.mkdir(parents=True, exist_ok=True)
    gate_a_dir.mkdir(parents=True, exist_ok=True)

    blacklist = set()
    if blacklist_path.exists():
        blacklist = {
            line.strip().lower()
            for line in blacklist_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }

    raw_items = []
    with corpus_path.open("r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            item = json.loads(line_str)
            if item["source"].strip().lower() in blacklist:
                continue
            raw_items.append(item)

    corpus_hash = sha256_file(corpus_path)

    # 1. Export Qwen ChatML training examples
    qwen_records = [build_qwen_chatml_record(item) for item in raw_items]
    out_qwen_quality = quality_dir / "mangalore_trilingual_qwen_sft.jsonl"
    with out_qwen_quality.open("w", encoding="utf-8") as f:
        for rec in qwen_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Exported {len(qwen_records)} Qwen ChatML training examples to {out_qwen_quality}")

    out_qwen_gate_a = gate_a_dir / "mangalore_trilingual_qwen_sft.jsonl"
    with out_qwen_gate_a.open("w", encoding="utf-8") as f:
        for rec in qwen_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 2. Merge into quality_v1/train_candidates.jsonl
    q1_train_path = quality_dir / "train_candidates.jsonl"
    existing_q1_lines = []
    existing_q1_ids = set()
    if q1_train_path.exists():
        with q1_train_path.open("r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                record = json.loads(line_str)
                existing_q1_ids.add(record.get("id"))
                existing_q1_lines.append(record)

    added_q1 = 0
    for idx, item in enumerate(raw_items, start=1):
        cand = build_quality_v1_candidate(idx, item, corpus_hash)
        if cand["id"] not in existing_q1_ids:
            existing_q1_lines.append(cand)
            existing_q1_ids.add(cand["id"])
            added_q1 += 1

    with q1_train_path.open("w", encoding="utf-8") as f:
        for rec in existing_q1_lines:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Merged {added_q1} records into {q1_train_path} (total: {len(existing_q1_lines)})")

    # 3. Update quality_v1 manifest
    q1_manifest_path = quality_dir / "manifest.json"
    if q1_manifest_path.exists():
        q1_manifest = json.loads(q1_manifest_path.read_text(encoding="utf-8"))
        if "output_sha256" in q1_manifest:
            q1_manifest["output_sha256"]["train_candidates.jsonl"] = sha256_file(q1_train_path)
            q1_manifest["output_sha256"]["mangalore_trilingual_qwen_sft.jsonl"] = sha256_file(out_qwen_quality)
        if "counts" in q1_manifest:
            q1_manifest["counts"]["train"] = len(existing_q1_lines)
            if "train_source_types" in q1_manifest["counts"]:
                q1_manifest["counts"]["train_source_types"]["mangalore_chat"] = len(raw_items)
        if "input_sha256" in q1_manifest:
            q1_manifest["input_sha256"]["data/corpus/mangalore_chat_corpus.jsonl"] = corpus_hash
        q1_manifest_path.write_text(json.dumps(q1_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Updated {q1_manifest_path}")

    # 4. Merge into student_gate_a_v1/train_candidates.jsonl
    ga_train_path = gate_a_dir / "train_candidates.jsonl"
    existing_ga_lines = []
    existing_ga_ids = set()
    if ga_train_path.exists():
        with ga_train_path.open("r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                record = json.loads(line_str)
                existing_ga_ids.add(record.get("id"))
                existing_ga_lines.append(record)

    added_ga = 0
    for idx, item in enumerate(raw_items, start=1):
        cand = build_student_gate_a_candidate(idx, item, corpus_hash)
        if cand["id"] not in existing_ga_ids:
            existing_ga_lines.append(cand)
            existing_ga_ids.add(cand["id"])
            added_ga += 1

    with ga_train_path.open("w", encoding="utf-8") as f:
        for rec in existing_ga_lines:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Merged {added_ga} records into {ga_train_path} (total: {len(existing_ga_lines)})")

    # 5. Update student_gate_a_v1 manifest
    ga_manifest_path = gate_a_dir / "manifest.json"
    if ga_manifest_path.exists():
        ga_manifest = json.loads(ga_manifest_path.read_text(encoding="utf-8"))
        ga_manifest["train_rows"] = len(existing_ga_lines)
        if "output_sha256" in ga_manifest:
            ga_manifest["output_sha256"]["train_candidates.jsonl"] = sha256_file(ga_train_path)
            ga_manifest["output_sha256"]["mangalore_trilingual_qwen_sft.jsonl"] = sha256_file(out_qwen_gate_a)
        if "train_by_source" in ga_manifest:
            ga_manifest["train_by_source"]["mangalore_chat_corpus"] = len(raw_items)
        ga_manifest_path.write_text(json.dumps(ga_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Updated {ga_manifest_path}")

if __name__ == "__main__":
    main()
