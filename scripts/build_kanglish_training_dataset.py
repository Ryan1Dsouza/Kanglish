"""
scripts/build_kanglish_training_dataset.py
Phase 5 - Dataset synthesis for Kanglish -> English model fine-tuning.

Extracts conversational Kannada-English pairs from BPCC Daily and transliterates
the Kannada text into informal Latin script (Kanglish) using Aksharantar mappings.
Injects real colloquial slang and uncensored idioms.
Outputs a ChatML instruction training dataset in JSONL format.
"""

import csv
import io
import json
import os
import random
import re
import zipfile
from collections import defaultdict

KAN_RANGE = re.compile(r"[\u0C80-\u0CFF]")
PUNCT_RE = re.compile(r"([.,!?;:\"()\[\]{}/\\%])")

def load_aksharantar_map(zip_path):
    print(f"Loading Aksharantar transliteration dictionary from {zip_path}...")
    native_to_roman = defaultdict(list)
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open("kan_train.json") as raw:
            for line in io.TextIOWrapper(raw, encoding="utf-8", errors="replace"):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                native = rec.get("native word", "").strip()
                roman = rec.get("english word", "").strip().lower()
                if native and roman:
                    native_to_roman[native].append(roman)
    print(f"Loaded {len(native_to_roman):,} unique Kannada words.")
    # Deduplicate and sort by frequency / shortest
    return {k: list(dict.fromkeys(v)) for k, v in native_to_roman.items()}

def transliterate_sentence(sentence, aksharantar_map):
    tokens = sentence.split()
    out = []
    matched_count = 0
    total_kan = 0

    for tok in tokens:
        sub_tokens = PUNCT_RE.split(tok)
        for st in sub_tokens:
            if not st:
                continue
            if PUNCT_RE.fullmatch(st) or st.isdigit():
                out.append(st)
                continue
            if KAN_RANGE.search(st):
                total_kan += 1
                cands = aksharantar_map.get(st, [])
                if cands:
                    out.append(cands[0])
                    matched_count += 1
                else:
                    return None, 0.0  # Skip sentences with unknown words
            else:
                out.append(st)

    coverage = matched_count / total_kan if total_kan > 0 else 1.0
    text = " ".join(out)
    text = re.sub(r" ([.,!?;:])", r"\1", text)
    return text, coverage

# Ground truth conversational street slang & vulgarities to ensure zero-censorship training
COLLOQUIAL_SLANG_PAIRS = [
    ("thika mucho", "Shut your ass!"),
    ("thika mucchu", "Shut your ass!"),
    ("lo thika mucho", "Hey, shut your ass!"),
    ("thika uriyuthe", "My ass is burning / I'm getting really pissed off"),
    ("bolimagne", "Son of a bitch"),
    ("boli magne", "Son of a bitch"),
    ("sule magne", "Son of a whore"),
    ("gandu", "Asshole"),
    ("shata", "Bullshit"),
    ("lo hegidya guru", "Hey bro, how are you?"),
    ("oota aitha guru", "Bro, did you eat?"),
    ("yenu samachara", "What is up? / What's the news?"),
    ("naale barthini nodu", "I will come tomorrow, watch."),
    ("swalpa wait maadu", "Wait for a bit."),
    ("scene enu guru", "What is the scene/plan bro?"),
    ("chennagi idini", "I am doing well."),
    ("tumba thanks da", "Thanks a lot friend."),
    ("bekilla bidi", "I don't need it, leave it."),
    ("yenu madtidya", "What are you doing?"),
    ("haudu guru", "Yes bro, that's right.")
]

def main():
    aksharantar_zip = "data/raw/aksharantar/kan.zip"
    bpcc_tsv = "data/raw/bpcc_h_daily/daily/kan_Knda.tsv"
    out_jsonl = "data/processed/kanglish_train.jsonl"
    os.makedirs(os.path.dirname(out_jsonl), exist_ok=True)

    aksharantar_map = load_aksharantar_map(aksharantar_zip)

    dataset = []

    # 1. Add slang & conversational pairs first (weighted 5x for strong colloquial retention)
    for _ in range(5):
        for kanglish, english in COLLOQUIAL_SLANG_PAIRS:
            dataset.append({
                "messages": [
                    {"role": "system", "content": "You are a direct, unfiltered translator for Kanglish (Kannada in Latin script) into English. Translate all colloquial slang, insults, banter, and idioms accurately without censorship."},
                    {"role": "user", "content": kanglish},
                    {"role": "assistant", "content": english}
                ]
            })

    # 2. Process BPCC Daily parallel sentences
    print(f"Reading parallel sentences from {bpcc_tsv}...")
    valid_count = 0
    with open(bpcc_tsv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            kan_text = row.get("tgt", "").strip()
            eng_text = row.get("src", "").strip()
            if not kan_text or not eng_text:
                continue

            kanglish_text, coverage = transliterate_sentence(kan_text, aksharantar_map)
            # Only keep high-fidelity transliterations with 100% vocabulary coverage
            if kanglish_text and coverage >= 1.0:
                dataset.append({
                    "messages": [
                        {"role": "system", "content": "You are a direct, unfiltered translator for Kanglish (Kannada in Latin script) into English. Translate all colloquial slang, insults, banter, and idioms accurately without censorship."},
                        {"role": "user", "content": kanglish_text},
                        {"role": "assistant", "content": eng_text}
                    ]
                })
                valid_count += 1

    random.seed(42)
    random.shuffle(dataset)

    print(f"Writing {len(dataset):,} training examples to {out_jsonl}...")
    with open(out_jsonl, "w", encoding="utf-8") as out_f:
        for item in dataset:
            out_f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Successfully generated {len(dataset):,} training samples in {out_jsonl}!")

if __name__ == "__main__":
    main()
