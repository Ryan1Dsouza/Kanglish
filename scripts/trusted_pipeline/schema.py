"""
scripts/trusted_pipeline/schema.py
Canonical Data Schema and Validation Rules for Kanglish FOSS Trusted Data Pipeline.

Enforces:
1. Review status lifecycle: raw, machine-derived, needs-human-review, human-verified, rejected.
2. AI-generated meaning cannot be marked human-verified.
3. Dual-native-speaker requirement (>= 2 reviewers) for human-verified slang / profanity.
4. Separation of transliteration (phonetic mapping) from semantic English translation.
5. Strict provenance tracking: source, license, attribution, download URL, and checksum.
6. Polysemy / Ambiguity detection and flagging.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any
import re
import datetime

class ReviewStatus(str, Enum):
    RAW = "raw"
    MACHINE_DERIVED = "machine-derived"
    NEEDS_HUMAN_REVIEW = "needs-human-review"
    HUMAN_VERIFIED = "human-verified"
    REJECTED = "rejected"

class LicenseType(str, Enum):
    ODC_ODBL_1_0 = "ODC-OdBL-1.0"
    CC_BY_4_0 = "CC-BY-4.0"
    CC0_1_0 = "CC0-1.0"
    PROPRIETARY_ISOLATED = "Proprietary-Isolated"
    COMMUNITY_CURATED = "Community-Curated"

class DataType(str, Enum):
    LEXICON = "lexicon"
    TRANSLITERATION = "transliteration"
    CONVERSATIONAL = "conversational"
    SLANG_PROFANITY = "slang_profanity"

class SlangProfanityLabel(str, Enum):
    CLEAN = "clean"
    SLANG = "slang"
    PROFANITY = "profanity"
    MILD_VULGAR = "mild_vulgar"

class DialectRegister(str, Enum):
    BENGALURU_CASUAL = "bengaluru_casual"
    STANDARD_COLLOQUIAL = "standard_colloquial"
    FORMAL_LEXICAL = "formal_lexical"
    STREET_SLANG = "street_slang"
    CODE_MIXED = "code_mixed"

class AmbiguityStatus(str, Enum):
    NONE = "none"
    FLAGGED_AMBIGUOUS = "flagged_ambiguous"
    MULTIPLE_VALID = "multiple_valid"
    UNRESOLVED = "unresolved"

# Known ambiguous / polysemous Kannada words that require context
AMBIGUOUS_KANNADA_TERMS = {
    "ide": "Can mean 'there is / present', or the English loanword 'idea'.",
    "scene": "Can mean 'what's the situation / plan', or a literal movie/drama scene.",
    "aaytha": "Can mean 'done / happened', or an interrogative 'is it over?'.",
    "baa": "Can mean the imperative verb 'come', or sound/echo.",
    "hallu": "Can mean 'tooth' (ಹಲ್ಲು) or loanword 'hall' (ಹಾಲ್).",
    "kodu": "Can mean 'give' (ಕೊಡು) or 'horn' / 'branch' (ಕೋಡು / ಕೊಂಬು).",
    "hotte": "Can mean 'stomach' / 'belly', or metaphor for jealousy ('hotte uri').",
    "thika": "Vulgar slang for 'ass / buttocks', or contextual colloquial intensifier.",
    "maga": "Slang address 'bro / dude / buddy', or literal 'son' (ಮಗ).",
    "guru": "Slang address 'dude / bro', or literal 'teacher / master' (ಗುರು).",
    "kelsa": "Work / job / task, or contextual 'business / affair'.",
}

# These were seed placeholders, not recorded review identities.
PLACEHOLDER_REVIEWERS = {"reviewer_kannada_1", "reviewer_kannada_2"}

@dataclass
class TrustedRecord:
    entry_id: str
    original_kanglish: str
    kannada_script: str
    english_meaning: str
    context: str
    dialect_register: str
    slang_or_profanity_label: str
    source: str
    license: str
    attribution: str
    confidence: float
    review_status: str
    reviewers: List[str] = field(default_factory=list)
    ambiguity_status: str = AmbiguityStatus.NONE.value
    ambiguity_notes: str = ""
    data_type: str = DataType.LEXICON.value
    source_url: str = ""
    source_checksum: str = ""
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def validate(self) -> List[str]:
        """Validate record against pipeline integrity rules. Returns list of errors."""
        errors = []

        # 1. Review status validation
        valid_statuses = [s.value for s in ReviewStatus]
        if self.review_status not in valid_statuses:
            errors.append(f"Invalid review_status '{self.review_status}'. Must be one of {valid_statuses}")

        # 2. Rule 8: Never mark an AI-generated meaning as human-verified
        ai_markers = ["ai_generated", "synthetic", "machine-derived", "gpt", "qwen"]
        if self.review_status == ReviewStatus.HUMAN_VERIFIED.value:
            if any(marker in self.source.lower() for marker in ai_markers):
                errors.append("Rule 8 Violation: AI-generated source cannot be marked 'human-verified'.")
            if any(not reviewer.strip() or reviewer.strip().lower() in PLACEHOLDER_REVIEWERS for reviewer in self.reviewers):
                errors.append("Rule 8 Violation: Blank or placeholder reviewer identities cannot establish human verification.")

        # 3. Rule 8: Dual independent native-speaker review required for slang/profanity promotion
        if self.slang_or_profanity_label in [SlangProfanityLabel.SLANG.value, SlangProfanityLabel.PROFANITY.value, SlangProfanityLabel.MILD_VULGAR.value]:
            if self.review_status == ReviewStatus.HUMAN_VERIFIED.value:
                if len(set(self.reviewers)) < 2:
                    errors.append(f"Rule 8 Violation: Slang/profanity entry '{self.entry_id}' requires >= 2 independent native-speaker reviewers for 'human-verified' status. Found {len(set(self.reviewers))}.")

        # 4. Rule 4: Transliteration mappings must not be treated as proof of English meaning
        if self.data_type == DataType.TRANSLITERATION.value:
            if self.english_meaning and self.english_meaning.strip() not in ["", "[transliteration_only]"]:
                errors.append(f"Rule 4 Violation: Transliteration entry '{self.entry_id}' contains semantic English meaning '{self.english_meaning}'. Transliteration must not assert English meaning without lexical proof.")

        # 5. Provenance checks: source, license, and attribution must be populated
        if not self.source.strip():
            errors.append("Missing source identifier.")
        if not self.license.strip():
            errors.append("Missing license identifier.")
        if not self.attribution.strip():
            errors.append("Missing attribution.")

        # 6. Confidence range check
        if not (0.0 <= self.confidence <= 1.0):
            errors.append(f"Confidence {self.confidence} out of range [0.0, 1.0].")

        # 7. Ambiguity check: auto-flag ambiguous words if not already handled
        lower_kanglish = self.original_kanglish.strip().lower()
        for ambig_term, explanation in AMBIGUOUS_KANNADA_TERMS.items():
            if ambig_term in lower_kanglish.split():
                if self.ambiguity_status == AmbiguityStatus.NONE.value and not self.ambiguity_notes:
                    self.ambiguity_status = AmbiguityStatus.FLAGGED_AMBIGUOUS.value
                    self.ambiguity_notes = explanation

        return errors

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["reviewers"] = "|".join(self.reviewers) if isinstance(self.reviewers, list) else str(self.reviewers)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrustedRecord":
        d_copy = dict(d)
        if isinstance(d_copy.get("reviewers"), str):
            rev_str = d_copy["reviewers"].strip()
            d_copy["reviewers"] = [r.strip() for r in rev_str.split("|") if r.strip()] if rev_str else []
        if isinstance(d_copy.get("confidence"), str):
            d_copy["confidence"] = float(d_copy["confidence"])
        return cls(**d_copy)
