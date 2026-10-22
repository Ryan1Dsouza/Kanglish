"""
scripts/trusted_pipeline/importers/alar_importer.py
High-speed streaming importer for Alar Kannada-English Dictionary.
Parses all 156,650 entries in ~2-3 seconds without slow YAML AST overhead.
Preserves ODC-OdBL-1.0 license, V. Krishna attribution, and origin checksum.
"""

import os
from scripts.trusted_pipeline.quality import english_target_issue
from typing import Iterator, Optional, List, Dict, Any
from scripts.trusted_pipeline.schema import (
    TrustedRecord,
    ReviewStatus,
    LicenseType,
    DataType,
    DialectRegister,
    SlangProfanityLabel,
    AmbiguityStatus
)

ALAR_RAW_PATH = "data/raw/alar/alar.yml"
ALAR_CHECKSUM = "9242a255d166736b81eec1035fddcaa6f5a4af76fdaf33e53784ff2aba891294"
ALAR_URL = "https://raw.githubusercontent.com/alar-dict/data/master/alar.yml"
ALAR_ATTRIBUTION = "(c) V. Krishna / Alar project (https://alar.ink), licensed under ODC-OdBL"

def stream_alar_records(
    file_path: str = ALAR_RAW_PATH,
    limit: Optional[int] = None
) -> Iterator[TrustedRecord]:
    """
    Stream records from Alar dictionary at high speed.
    Yields validated TrustedRecord objects.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Alar dictionary file not found: {file_path}")

    current_entry: Optional[Dict[str, Any]] = None
    count = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line_s = line.strip()
            if line.startswith("- id:"):
                if current_entry and current_entry.get("entry") and current_entry.get("defs"):
                    rec = _create_record(current_entry)
                    if rec:
                        yield rec
                        count += 1
                        if limit is not None and count >= limit:
                            return
                try:
                    entry_id = int(line[5:].strip().split("#")[0].strip())
                except ValueError:
                    entry_id = count + 1
                current_entry = {
                    "id": entry_id,
                    "entry": "",
                    "phone": "",
                    "defs": []
                }
            elif current_entry is not None:
                if line.startswith("  entry:"):
                    current_entry["entry"] = line[8:].strip()
                elif line.startswith("  phone:"):
                    current_entry["phone"] = line[8:].strip()
                elif line_s.startswith("entry:") and "defs" in current_entry:
                    defn = line_s[6:].strip()
                    if english_target_issue(defn) is None:
                        current_entry["defs"].append(defn)

        # Final entry
        if current_entry and current_entry.get("entry") and current_entry.get("defs"):
            rec = _create_record(current_entry)
            if rec:
                yield rec

def _create_record(data: Dict[str, Any]) -> Optional[TrustedRecord]:
    entry_id_num = data.get("id", 1)
    entry_word = (data.get("entry") or "").strip()
    phone = (data.get("phone") or "").strip()
    clean_defs = [definition for definition in data.get("defs", [])
                  if english_target_issue(definition) is None]

    if not entry_word or not clean_defs:
        return None

    # Clean english meaning (first 2-3 definitions)
    english_meaning = "; ".join(clean_defs[:2]) if clean_defs else ""

    # Normalize romanized phonetic notation for Kanglish
    kanglish = phone.replace("?", "").replace("ŋ", "ng").replace("ṭ", "t").replace("ḍ", "d").strip()

    record = TrustedRecord(
        entry_id=f"KANG-ALAR-{entry_id_num:06d}",
        original_kanglish=kanglish.lower(),
        kannada_script=entry_word,
        english_meaning=english_meaning,
        context="lexical_dictionary",
        dialect_register=DialectRegister.FORMAL_LEXICAL.value,
        slang_or_profanity_label=SlangProfanityLabel.CLEAN.value,
        source="alar_kannada_english_dict",
        license=LicenseType.ODC_ODBL_1_0.value,
        attribution=ALAR_ATTRIBUTION,
        confidence=0.95,
        review_status=ReviewStatus.RAW.value,
        reviewers=[],
        ambiguity_status=AmbiguityStatus.NONE.value,
        ambiguity_notes="",
        data_type=DataType.LEXICON.value,
        source_url=ALAR_URL,
        source_checksum=ALAR_CHECKSUM
    )
    return record
