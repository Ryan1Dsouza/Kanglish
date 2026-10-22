"""
scripts/trusted_pipeline/importers/bpcc_importer.py
Streaming importer for BPCC-H-Daily conversational Kannada-English data.
Preserves CC-BY-4.0 license, attribution, and checksum.
"""

import os
import csv
from typing import Iterator, Optional
from scripts.trusted_pipeline.schema import (
    TrustedRecord,
    ReviewStatus,
    LicenseType,
    DataType,
    DialectRegister,
    SlangProfanityLabel,
    AmbiguityStatus
)

BPCC_TSV_PATH = "data/raw/bpcc_h_daily/daily/kan_Knda.tsv"
BPCC_CHECKSUM = "f7c049f9217610f93dae24307e7a9fd4f078a5628929a8098fc871b5675973ef"
BPCC_URL = "https://huggingface.co/datasets/ai4bharat/BPCC"
BPCC_ATTRIBUTION = "AI4Bharat / BPCC-H-Daily (IndicTrans2 corpus), licensed under CC-BY-4.0"

def stream_bpcc_records(
    tsv_path: str = BPCC_TSV_PATH,
    limit: Optional[int] = None
) -> Iterator[TrustedRecord]:
    """
    Stream conversational sentence records from BPCC-H-Daily TSV file.
    Yields validated TrustedRecord objects with data_type='conversational'.
    """
    if not os.path.exists(tsv_path):
        raise FileNotFoundError(f"BPCC TSV file not found: {tsv_path}")

    with open(tsv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        count = 0
        for i, row in enumerate(reader):
            english_src = (row.get("src") or "").strip()
            kannada_tgt = (row.get("tgt") or "").strip()

            if not english_src or not kannada_tgt:
                continue

            # Exclude rows without Kannada script (e.g., bare English app names)
            has_kannada_char = any("\u0c80" <= ch <= "\u0cff" for ch in kannada_tgt)
            if not has_kannada_char:
                continue

            record = TrustedRecord(
                entry_id=f"KANG-BPCC-{i+1:06d}",
                original_kanglish="",  # Native script; transliterated variants are tracked separately
                kannada_script=kannada_tgt,
                english_meaning=english_src,
                context="daily_conversational_commands",
                dialect_register=DialectRegister.STANDARD_COLLOQUIAL.value,
                slang_or_profanity_label=SlangProfanityLabel.CLEAN.value,
                source="bpcc_h_daily_conversational",
                license=LicenseType.CC_BY_4_0.value,
                attribution=BPCC_ATTRIBUTION,
                confidence=0.95,
                review_status=ReviewStatus.RAW.value,
                reviewers=[],
                ambiguity_status=AmbiguityStatus.NONE.value,
                ambiguity_notes="",
                data_type=DataType.CONVERSATIONAL.value,
                source_url=BPCC_URL,
                source_checksum=BPCC_CHECKSUM
            )

            yield record
            count += 1
            if limit is not None and count >= limit:
                return
