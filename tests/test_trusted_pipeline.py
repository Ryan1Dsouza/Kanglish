"""
tests/test_trusted_pipeline.py
Automated tests validating rules for the Kanglish FOSS Trusted Data Pipeline.
Uses Python stdlib unittest so it runs in all environments.
"""

import unittest
import os
import hashlib
from scripts.trusted_pipeline.schema import (
    TrustedRecord,
    ReviewStatus,
    LicenseType,
    DataType,
    SlangProfanityLabel,
    DialectRegister,
    AmbiguityStatus
)
from scripts.trusted_pipeline.deduplicate import Deduplicator
from scripts.trusted_pipeline.pipeline import verify_protected_files, PROTECTED_FILES

class TestTrustedPipeline(unittest.TestCase):

    def test_protected_files_integrity(self):
        """Rule 9: Locked evaluation data and benchmark files must remain unchanged."""
        violations = verify_protected_files()
        self.assertEqual(len(violations), 0, f"Protected file check failed: {violations}")

    def test_schema_valid_record(self):
        """Valid record passes all validation checks."""
        rec = TrustedRecord(
            entry_id="TEST-001",
            original_kanglish="oota",
            kannada_script="ಊಟ",
            english_meaning="meal / food",
            context="daily_conversation",
            dialect_register=DialectRegister.STANDARD_COLLOQUIAL.value,
            slang_or_profanity_label=SlangProfanityLabel.CLEAN.value,
            source="alar_kannada_english_dict",
            license=LicenseType.ODC_ODBL_1_0.value,
            attribution="(c) V. Krishna / Alar",
            confidence=0.95,
            review_status=ReviewStatus.RAW.value,
            reviewers=[],
            ambiguity_status=AmbiguityStatus.NONE.value,
            data_type=DataType.LEXICON.value
        )
        errors = rec.validate()
        self.assertEqual(len(errors), 0, f"Expected 0 errors, got: {errors}")

    def test_rule8_ai_not_marked_human_verified(self):
        """Rule 8: Never mark an AI-generated meaning as human-verified."""
        rec = TrustedRecord(
            entry_id="TEST-AI-001",
            original_kanglish="test",
            kannada_script="ಟೆಸ್ಟ್",
            english_meaning="test meaning",
            context="testing",
            dialect_register=DialectRegister.STANDARD_COLLOQUIAL.value,
            slang_or_profanity_label=SlangProfanityLabel.CLEAN.value,
            source="synthetic_ai_generated_qwen",
            license=LicenseType.COMMUNITY_CURATED.value,
            attribution="AI generated",
            confidence=0.5,
            review_status=ReviewStatus.HUMAN_VERIFIED.value,  # VIOLATION!
            reviewers=["user1"],
            ambiguity_status=AmbiguityStatus.NONE.value,
            data_type=DataType.CONVERSATIONAL.value
        )
        errors = rec.validate()
        self.assertTrue(any("Rule 8 Violation" in e for e in errors), f"Expected Rule 8 error, got: {errors}")

    def test_rule8_slang_requires_dual_reviewers(self):
        """Rule 8: Slang/profanity requires >= 2 independent reviewers for human-verified status."""
        # Single reviewer -> FAIL
        rec_single = TrustedRecord(
            entry_id="TEST-SLANG-001",
            original_kanglish="thika mucho",
            kannada_script="ತಿಕ ಮುಚ್ಚು",
            english_meaning="Shut your ass!",
            context="street_slang",
            dialect_register=DialectRegister.STREET_SLANG.value,
            slang_or_profanity_label=SlangProfanityLabel.PROFANITY.value,
            source="curated_slang",
            license=LicenseType.COMMUNITY_CURATED.value,
            attribution="Community",
            confidence=1.0,
            review_status=ReviewStatus.HUMAN_VERIFIED.value,
            reviewers=["reviewer1"],  # ONLY 1 REVIEWER
            ambiguity_status=AmbiguityStatus.NONE.value,
            data_type=DataType.SLANG_PROFANITY.value
        )
        errors_single = rec_single.validate()
        self.assertTrue(any("Rule 8 Violation" in e and ">= 2 independent" in e for e in errors_single))

        # Dual reviewers -> PASS
        rec_dual = TrustedRecord(
            entry_id="TEST-SLANG-002",
            original_kanglish="thika mucho",
            kannada_script="ತಿಕ ಮುಚ್ಚು",
            english_meaning="Shut your ass!",
            context="street_slang",
            dialect_register=DialectRegister.STREET_SLANG.value,
            slang_or_profanity_label=SlangProfanityLabel.PROFANITY.value,
            source="curated_slang",
            license=LicenseType.COMMUNITY_CURATED.value,
            attribution="Community",
            confidence=1.0,
            review_status=ReviewStatus.HUMAN_VERIFIED.value,
            reviewers=["reviewer1", "reviewer2"],  # 2 REVIEWERS
            ambiguity_status=AmbiguityStatus.NONE.value,
            data_type=DataType.SLANG_PROFANITY.value
        )
        errors_dual = rec_dual.validate()
        self.assertEqual(len(errors_dual), 0)

    def test_rule4_transliteration_no_asserted_meaning(self):
        """Rule 4: Treat Romanized-to-Kannada mappings as transliteration data, not proof of English meaning."""
        rec_invalid = TrustedRecord(
            entry_id="TEST-TRANS-001",
            original_kanglish="namaskara",
            kannada_script="ನಮಸ್ಕಾರ",
            english_meaning="hello and welcome",  # VIOLATION
            context="transliteration",
            dialect_register=DialectRegister.STANDARD_COLLOQUIAL.value,
            slang_or_profanity_label=SlangProfanityLabel.CLEAN.value,
            source="aksharantar",
            license=LicenseType.CC0_1_0.value,
            attribution="AI4Bharat",
            confidence=0.9,
            review_status=ReviewStatus.RAW.value,
            reviewers=[],
            ambiguity_status=AmbiguityStatus.NONE.value,
            data_type=DataType.TRANSLITERATION.value
        )
        errors = rec_invalid.validate()
        self.assertTrue(any("Rule 4 Violation" in e for e in errors))

        # Valid transliteration record with empty english_meaning
        rec_valid = TrustedRecord(
            entry_id="TEST-TRANS-002",
            original_kanglish="namaskara",
            kannada_script="ನಮಸ್ಕಾರ",
            english_meaning="",  # Correct
            context="transliteration",
            dialect_register=DialectRegister.STANDARD_COLLOQUIAL.value,
            slang_or_profanity_label=SlangProfanityLabel.CLEAN.value,
            source="aksharantar",
            license=LicenseType.CC0_1_0.value,
            attribution="AI4Bharat",
            confidence=0.9,
            review_status=ReviewStatus.RAW.value,
            reviewers=[],
            ambiguity_status=AmbiguityStatus.NONE.value,
            data_type=DataType.TRANSLITERATION.value
        )
        self.assertEqual(len(rec_valid.validate()), 0)

    def test_deduplication_engine(self):
        """Deduplicator removes duplicates and tracks statistics."""
        dedup = Deduplicator()
        rec1 = TrustedRecord(
            entry_id="REC-1",
            original_kanglish="oota",
            kannada_script="ಊಟ",
            english_meaning="meal",
            context="c1",
            dialect_register=DialectRegister.STANDARD_COLLOQUIAL.value,
            slang_or_profanity_label=SlangProfanityLabel.CLEAN.value,
            source="src",
            license=LicenseType.ODC_ODBL_1_0.value,
            attribution="attr",
            confidence=0.8,
            review_status=ReviewStatus.RAW.value,
            data_type=DataType.LEXICON.value
        )
        rec2 = TrustedRecord(
            entry_id="REC-2",
            original_kanglish="oota",
            kannada_script="ಊಟ",
            english_meaning="meal",
            context="c2",
            dialect_register=DialectRegister.STANDARD_COLLOQUIAL.value,
            slang_or_profanity_label=SlangProfanityLabel.CLEAN.value,
            source="src",
            license=LicenseType.ODC_ODBL_1_0.value,
            attribution="attr",
            confidence=0.95,
            review_status=ReviewStatus.HUMAN_VERIFIED.value,
            data_type=DataType.LEXICON.value
        )

        is_new_1 = dedup.add(rec1)
        is_new_2 = dedup.add(rec2)

        self.assertTrue(is_new_1)
        self.assertFalse(is_new_2)
        stats = dedup.get_stats()
        self.assertEqual(stats["total_processed"], 2)
        self.assertEqual(stats["unique_retained"], 1)
        self.assertEqual(stats["duplicates_removed"], 1)
        self.assertEqual(dedup.get_unique_records()[0].confidence, 0.95)

if __name__ == "__main__":
    unittest.main()
