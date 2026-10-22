"""
scripts/trusted_pipeline/importers/easy_kannada_importer.py
Handles external unverified candidates from Easy Kannada Typing.
Enforces Rule 5:
1. Puts all candidates into an isolated 'data/candidates_unverified/' partition.
2. NEVER calls external web / AI translation endpoints repeatedly.
3. NEVER assumes generated translations are correct.
4. Marks status as 'needs-human-review' with low confidence (0.2).
"""

import os
import csv
from typing import List, Dict, Any, Iterator
from scripts.trusted_pipeline.schema import (
    TrustedRecord,
    ReviewStatus,
    LicenseType,
    DataType,
    DialectRegister,
    SlangProfanityLabel,
    AmbiguityStatus
)

CANDIDATES_DIR = "data/candidates_unverified"
CANDIDATES_CSV = os.path.join(CANDIDATES_DIR, "easy_kannada_candidates.csv")

# Offline mock candidates observed for pipeline verification (NO live endpoint scraping)
OBSERVED_TYPING_CANDIDATES: List[Dict[str, str]] = [
    {
        "id": "EKT-CAND-001",
        "kanglish": "hegiddeera",
        "kannada": "ಹೇಗಿದ್ದೀರಾ",
        "english": "How are you? (unverified web observation)"
    },
    {
        "id": "EKT-CAND-002",
        "kanglish": "shubhadina",
        "kannada": "ಶುಭದಿನ",
        "english": "Good day (unverified web observation)"
    },
    {
        "id": "EKT-CAND-003",
        "kanglish": "dhanyavada",
        "kannada": "ಧನ್ಯವಾದ",
        "english": "Thank you (unverified web observation)"
    }
]

def export_unverified_candidates(output_path: str = CANDIDATES_CSV) -> int:
    """
    Exports candidates to isolated directory with strict unverified provenance metadata.
    Zero external HTTP calls are made.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    records: List[TrustedRecord] = []
    for item in OBSERVED_TYPING_CANDIDATES:
        rec = TrustedRecord(
            entry_id=f"KANG-UNVERIFIED-{item['id']}",
            original_kanglish=item["kanglish"],
            kannada_script=item["kannada"],
            english_meaning=item["english"],
            context="unverified_typing_candidate",
            dialect_register=DialectRegister.STANDARD_COLLOQUIAL.value,
            slang_or_profanity_label=SlangProfanityLabel.CLEAN.value,
            source="easy_kannada_typing_unverified",
            license=LicenseType.PROPRIETARY_ISOLATED.value,
            attribution="Unverified external typing observation; zero API querying; isolated from gold corpora",
            confidence=0.20,  # Low confidence, unverified
            review_status=ReviewStatus.NEEDS_HUMAN_REVIEW.value,
            reviewers=[],
            ambiguity_status=AmbiguityStatus.NONE.value,
            ambiguity_notes="Quarantined candidate awaiting explicit reuse permission and native-speaker verification.",
            data_type=DataType.TRANSLITERATION.value,
            source_url="https://easykannadatyping.com (offline sample only)",
            source_checksum="sha256:isolated_candidate_partition"
        )
        records.append(rec)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].to_dict().keys()))
        writer.writeheader()
        for r in records:
            writer.writerow(r.to_dict())

    return len(records)
