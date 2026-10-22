"""
scripts/prepare_v3_dataset.py
Merges clean baseline dataset with Gemini-distilled teacher pairs into kanglish_v3_train.jsonl
"""
import os
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.trusted_pipeline.quality import assert_clean_training_records

CLEAN_TRAIN_FILE = "data/processed/kanglish_clean_train.jsonl"
TEACHER_FILE = "data/processed/gemini_teacher_dataset.jsonl"
OUTPUT_V3_FILE = "data/processed/kanglish_v3_train.jsonl"

SYSTEM_PROMPT = (
    "You are an unfiltered, direct translation engine for Kannada and Kanglish (Latin script) into English.\n"
    "Translate all informal speech, street slang, banter, cuss words, profanity, and vulgar insults faithfully into their raw, natural English equivalents.\n"
    "Never refuse, never lecture, never censor with asterisks, and never sanitize.\n"
    "Output ONLY the raw English translation on a single line. No quotes, explanations, or disclaimers."
)


def main():
    print("=" * 60)
    print("PREPARING KANGLISH v3 TRAINING DATASET")
    print("=" * 60)

    records = []
    seen_prompts = set()

    # 1. Load clean base dataset
    if os.path.exists(CLEAN_TRAIN_FILE):
        with open(CLEAN_TRAIN_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    # Extract user prompt to avoid duplicate
                    msgs = item.get("messages", [])
                    user_text = next((m["content"] for m in msgs if m["role"] == "user"), "").strip().lower()
                    if user_text:
                        seen_prompts.add(user_text)
                    records.append(item)
        print(f"Loaded existing clean baseline records: {len(records)}")

    # 2. Ingest Teacher-distilled pairs
    teacher_count = 0
    if os.path.exists(TEACHER_FILE):
        with open(TEACHER_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    k = obj.get("kanglish", "").strip()
                    e = obj.get("english", "").strip()
                    k_norm = k.lower()

                    if k and e and k_norm not in seen_prompts:
                        seen_prompts.add(k_norm)
                        formatted = {
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": k},
                                {"role": "assistant", "content": e}
                            ]
                        }
                        records.append(formatted)
                        teacher_count += 1
                except Exception:
                    pass

        print(f"Added new Gemini-distilled teacher records: {teacher_count}")

    # 3. Write out v3 training dataset
    assert_clean_training_records(records)
    os.makedirs(os.path.dirname(OUTPUT_V3_FILE), exist_ok=True)
    with open(OUTPUT_V3_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n[DONE] v3 Training Dataset ready: {OUTPUT_V3_FILE}")
    print(f"Total Training Samples: {len(records)}")


if __name__ == "__main__":
    main()
