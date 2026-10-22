"""
scripts/trusted_pipeline/deduplicate.py
Deduplication engine for trusted Kanglish FOSS pipeline.
Tracks duplicate statistics, keeps provenance intact, and resolves conflicts by confidence.
"""

from typing import List, Dict, Tuple, Set
from scripts.trusted_pipeline.schema import TrustedRecord

class Deduplicator:
    def __init__(self):
        self.seen_keys: Dict[str, TrustedRecord] = {}
        self.duplicate_counts: Dict[str, int] = {}
        self.total_processed = 0
        self.total_duplicates = 0

    def get_dedup_key(self, record: TrustedRecord) -> str:
        """
        Derive canonical deduplication key based on data type.
        """
        norm_kanglish = record.original_kanglish.strip().lower()
        norm_kannada = record.kannada_script.strip()
        norm_english = record.english_meaning.strip().lower()

        if record.data_type == "transliteration":
            return f"TRANS::{norm_kanglish}::{norm_kannada}"
        elif record.data_type == "lexicon":
            return f"LEX::{norm_kannada}::{norm_english}"
        elif record.data_type == "conversational":
            return f"CONV::{norm_kannada}::{norm_english}"
        elif record.data_type == "slang_profanity":
            return f"SLANG::{norm_kanglish}::{norm_kannada}"
        else:
            return f"GEN::{norm_kanglish}::{norm_kannada}::{norm_english}"

    def add(self, record: TrustedRecord) -> bool:
        """
        Add record to deduplicator.
        Returns True if record is newly added, False if duplicate.
        """
        self.total_processed += 1
        key = self.get_dedup_key(record)

        if key in self.seen_keys:
            self.total_duplicates += 1
            self.duplicate_counts[key] = self.duplicate_counts.get(key, 1) + 1
            existing = self.seen_keys[key]

            # If incoming record has higher confidence or human verification, upgrade it
            if record.confidence > existing.confidence:
                self.seen_keys[key] = record
            elif record.review_status == "human-verified" and existing.review_status != "human-verified":
                self.seen_keys[key] = record

            return False
        else:
            self.seen_keys[key] = record
            self.duplicate_counts[key] = 1
            return True

    def get_unique_records(self) -> List[TrustedRecord]:
        return list(self.seen_keys.values())

    def get_stats(self) -> Dict[str, int]:
        return {
            "total_processed": self.total_processed,
            "unique_retained": len(self.seen_keys),
            "duplicates_removed": self.total_duplicates
        }
