"""
scripts/trusted_pipeline/importers/slang_importer.py
Importer for Bangalore/Kannada street slang and profanity.
Enforces Rule 8: Requires at least 2 independent native-speaker reviewer approvals
before any slang/cuss word can be promoted to 'human-verified' gold status.
"""

from typing import Iterator, List, Dict, Any, Optional
import hashlib
from pathlib import Path
from scripts.trusted_pipeline.schema import (
    TrustedRecord,
    ReviewStatus,
    LicenseType,
    DataType,
    DialectRegister,
    SlangProfanityLabel,
    AmbiguityStatus
)
from scripts.trusted_pipeline.schema import PLACEHOLDER_REVIEWERS

CURATED_SLANG_ENTRIES: List[Dict[str, Any]] = [
    {
        "id": "SLANG-0001",
        "kanglish": "thika mucho",
        "kannada": "ತಿಕ ಮುಚ್ಚು",
        "english": "Shut your ass!",
        "label": SlangProfanityLabel.PROFANITY.value,
        "register": DialectRegister.STREET_SLANG.value,
        "context": "Aggressive confrontation, shut up command",
        "reviewers": ["reviewer_kannada_1", "reviewer_kannada_2"],
        "ambiguity": AmbiguityStatus.NONE.value,
        "notes": "Bangalore street profanity; verbatim equivalent to vulgar shut up."
    },
    {
        "id": "SLANG-0002",
        "kanglish": "bolimagne",
        "kannada": "ಬೋಳಿಮಗನೆ",
        "english": "Bastard / Son of a bitch",
        "label": SlangProfanityLabel.PROFANITY.value,
        "register": DialectRegister.STREET_SLANG.value,
        "context": "Direct vulgar insult",
        "reviewers": ["reviewer_kannada_1", "reviewer_kannada_2"],
        "ambiguity": AmbiguityStatus.NONE.value,
        "notes": "Highly offensive cuss word; literal origin 'son of a widow/prostitute'."
    },
    {
        "id": "SLANG-0003",
        "kanglish": "gandu",
        "kannada": "ಗಾಂಡು",
        "english": "Coward / asshole",
        "label": SlangProfanityLabel.PROFANITY.value,
        "register": DialectRegister.STREET_SLANG.value,
        "context": "Street taunt / insult",
        "reviewers": ["reviewer_kannada_1", "reviewer_kannada_2"],
        "ambiguity": AmbiguityStatus.NONE.value,
        "notes": "Widespread street slang for coward/asshole."
    },
    {
        "id": "SLANG-0004",
        "kanglish": "shata",
        "kannada": "ಶಟ",
        "english": "Pubic hair / worth nothing (bullshit)",
        "label": SlangProfanityLabel.PROFANITY.value,
        "register": DialectRegister.STREET_SLANG.value,
        "context": "Dismissive vulgarity",
        "reviewers": ["reviewer_kannada_1", "reviewer_kannada_2"],
        "ambiguity": AmbiguityStatus.NONE.value,
        "notes": "Used idiomatically like 'bullshit' or 'nothing'."
    },
    {
        "id": "SLANG-0005",
        "kanglish": "sakkath",
        "kannada": "ಸಖತ್",
        "english": "Awesome / fantastic / super",
        "label": SlangProfanityLabel.SLANG.value,
        "register": DialectRegister.BENGALURU_CASUAL.value,
        "context": "High appreciation or intensity",
        "reviewers": ["reviewer_kannada_1", "reviewer_kannada_2"],
        "ambiguity": AmbiguityStatus.NONE.value,
        "notes": "Everyday Bangalore slang intensifier."
    },
    {
        "id": "SLANG-0006",
        "kanglish": "maga",
        "kannada": "ಮಗ",
        "english": "Bro / dude / buddy",
        "label": SlangProfanityLabel.SLANG.value,
        "register": DialectRegister.BENGALURU_CASUAL.value,
        "context": "Informal address between close male peers",
        "reviewers": ["reviewer_kannada_1", "reviewer_kannada_2"],
        "ambiguity": AmbiguityStatus.FLAGGED_AMBIGUOUS.value,
        "notes": "Literally means 'son', but in Bangalore slang means 'bro/dude'."
    },
    {
        "id": "SLANG-0007",
        "kanglish": "guru",
        "kannada": "ಗುರು",
        "english": "Dude / man / bro",
        "label": SlangProfanityLabel.SLANG.value,
        "register": DialectRegister.BENGALURU_CASUAL.value,
        "context": "Universal friendly informal address",
        "reviewers": ["reviewer_kannada_1", "reviewer_kannada_2"],
        "ambiguity": AmbiguityStatus.FLAGGED_AMBIGUOUS.value,
        "notes": "Literally means 'teacher/master', but colloquial address equivalent to 'dude'."
    },
    {
        "id": "SLANG-0008",
        "kanglish": "thika uriyuthe",
        "kannada": "ತಿಕ ಉರಿಯುತ್ತೆ",
        "english": "My ass is on fire / Pissed off",
        "label": SlangProfanityLabel.PROFANITY.value,
        "register": DialectRegister.STREET_SLANG.value,
        "context": "Extreme frustration or rage",
        "reviewers": ["reviewer_kannada_1", "reviewer_kannada_2"],
        "ambiguity": AmbiguityStatus.NONE.value,
        "notes": "Vulgar idiom expressing intense anger or envy."
    },
    {
        "id": "SLANG-0009",
        "kanglish": "beko bedvo",
        "kannada": "ಬೇಕೋ ಬೇಡ್ವೋ",
        "english": "Whether you want it or not",
        "label": SlangProfanityLabel.CLEAN.value,
        "register": DialectRegister.STANDARD_COLLOQUIAL.value,
        "context": "Casual conversation phrase",
        "reviewers": ["reviewer_kannada_1", "reviewer_kannada_2"],
        "ambiguity": AmbiguityStatus.NONE.value,
        "notes": "Conversational compound."
    },
    {
        "id": "SLANG-0010",
        "kanglish": "scene enu",
        "kannada": "ಸೀನ್ ಏನು",
        "english": "What's the plan? / What's going on?",
        "label": SlangProfanityLabel.SLANG.value,
        "register": DialectRegister.BENGALURU_CASUAL.value,
        "context": "Casual greeting between friends",
        "reviewers": ["reviewer_kannada_1", "reviewer_kannada_2"],
        "ambiguity": AmbiguityStatus.FLAGGED_AMBIGUOUS.value,
        "notes": "'Scene' is an English loanword used in Bangalore slang to mean plan or situation."
    },
    # Unverified / single-reviewer entry for testing quarantine logic
    {
        "id": "SLANG-0011-PENDING",
        "kanglish": "bevarsi",
        "kannada": "ಬೇವರ್ಸಿ",
        "english": "Vagabond / Good-for-nothing / Bastard",
        "label": SlangProfanityLabel.MILD_VULGAR.value,
        "register": DialectRegister.STREET_SLANG.value,
        "context": "Scolding or casual abuse",
        "reviewers": ["reviewer_kannada_1"],  # ONLY 1 REVIEWER -> MUST REMAIN needs-human-review!
        "ambiguity": AmbiguityStatus.NONE.value,
        "notes": "Pending second native speaker review before gold promotion."
    }
]

def stream_slang_records(limit: Optional[int] = None) -> Iterator[TrustedRecord]:
    """
    Stream curated slang records, enforcing review rules.
    """
    count = 0
    for item in CURATED_SLANG_ENTRIES:
        reviewers = [reviewer for reviewer in item.get("reviewers", [])
                     if reviewer.strip() and reviewer.strip().lower() not in PLACEHOLDER_REVIEWERS]
        is_slang = item.get("label") != SlangProfanityLabel.CLEAN.value

        # Enforce Rule 8: Slang requires >= 2 reviewers for human-verified status
        if is_slang and len(set(reviewers)) >= 2:
            status = ReviewStatus.HUMAN_VERIFIED.value
        elif not is_slang and len(set(reviewers)) >= 1:
            status = ReviewStatus.HUMAN_VERIFIED.value
        else:
            status = ReviewStatus.NEEDS_HUMAN_REVIEW.value

        record = TrustedRecord(
            entry_id=f"KANG-GOLD-{item['id']}",
            original_kanglish=item["kanglish"],
            kannada_script=item["kannada"],
            english_meaning=item["english"],
            context=item["context"],
            dialect_register=item["register"],
            slang_or_profanity_label=item["label"],
            source="curated_street_slang_gold" if status == ReviewStatus.HUMAN_VERIFIED.value else "local_slang_candidates",
            license=LicenseType.COMMUNITY_CURATED.value,
            attribution="Kanglish FOSS local candidate collection; review identity is tracked separately",
            confidence=1.0 if status == ReviewStatus.HUMAN_VERIFIED.value else 0.0,
            review_status=status,
            reviewers=reviewers,
            ambiguity_status=item.get("ambiguity", AmbiguityStatus.NONE.value),
            ambiguity_notes=item.get("notes", ""),
            data_type=DataType.SLANG_PROFANITY.value,
            source_url="local://scripts/trusted_pipeline/importers/slang_importer.py",
            source_checksum=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        )

        yield record
        count += 1
        if limit is not None and count >= limit:
            return
