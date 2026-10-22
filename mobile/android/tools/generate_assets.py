import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GLOSSARY_CSV = ROOT / "data" / "glossary.csv"
ASSETS_DIR = ROOT / "mobile" / "android" / "app" / "src" / "main" / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

entries = []
if GLOSSARY_CSV.exists():
    with GLOSSARY_CSV.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            k = row.get("kanglish", "").strip()
            e = row.get("english", "").strip()
            if k and e:
                entries.append({"kanglish": k, "english": e})

with (ASSETS_DIR / "glossary.json").open("w", encoding="utf-8") as f:
    json.dump(entries, f, indent=2, ensure_ascii=False)

sample_chat = """18/10/2026, 10:15 - Ramesh: Hey guru scene enu ivattu?
18/10/2026, 10:16 - You: oota aaytha modlu?
18/10/2026, 10:17 - Ramesh: houdu aaitu, swalpa kelsa ide
18/10/2026, 10:18 - Ramesh: naale movie hogtiya?
18/10/2026, 10:20 - You: bekagilla bro, tumba busy idini
18/10/2026, 10:21 - Ramesh: swalpa wait maadu, avru bartheeni andidare
"""

(ASSETS_DIR / "sample_chat.txt").write_text(sample_chat, encoding="utf-8")
print(f"Generated {len(entries)} glossary entries and sample_chat.txt in {ASSETS_DIR}")
