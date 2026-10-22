"""
scripts/trusted_pipeline/importers/aksharantar_importer.py
Streaming importer for Aksharantar transliteration data.
Preserves CC0-1.0 / CC-BY-4.0 license, attribution, and checksum.
Enforces Rule 4: Romanized-to-Kannada mappings are strictly transliteration, NOT English meanings.
"""

import os
import json
import zipfile
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

AKSHARANTAR_ZIP_PATH = "data/raw/aksharantar/kan.zip"
AKSHARANTAR_CHECKSUM = "a0c18fa0a8bf06b34d413b09c3e7b9505b74ba3f7f1fa2ae724793fc3fc7d650"
AKSHARANTAR_URL = "https://huggingface.co/datasets/ai4bharat/Aksharantar"
AKSHARANTAR_ATTRIBUTION = "AI4Bharat / Aksharantar (CC0-1.0 mined / CC-BY-4.0 benchmark)"

def stream_aksharantar_records(
    zip_path: str = AKSHARANTAR_ZIP_PATH,
    split: str = "kan_valid.json",
    limit: Optional[int] = None
) -> Iterator[TrustedRecord]:
    """
    Stream word-level transliteration records from Aksharantar zip file.
    Yields validated TrustedRecord objects with data_type='transliteration' and empty english_meaning.
    """
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"Aksharantar zip file not found: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as z:
        if split not in z.namelist():
            raise ValueError(f"Split {split} not found in {zip_path}. Available: {z.namelist()}")

        count = 0
        with z.open(split) as f:
            for line_bytes in f:
                line_str = line_bytes.decode("utf-8").strip()
                if not line_str:
                    continue

                try:
                    obj = json.loads(line_str)
                    uid = obj.get("unique_identifier", f"kan_{count}")
                    native_word = (obj.get("native word") or "").strip()
                    roman_word = (obj.get("english word") or "").strip()
                    source_str = obj.get("source", "Mined")
                    score_val = obj.get("score")

                    if not native_word or not roman_word:
                        continue

                    # Determine license based on split/source
                    rec_license = LicenseType.CC_BY_4_0.value if "valid" in split or "test" in split else LicenseType.CC0_1_0.value

                    # Normalize confidence
                    confidence = 0.90
                    if score_val and score_val != "None":
                        try:
                            score_f = float(score_val)
                            confidence = min(max(score_f, 0.5), 1.0)
                        except ValueError:
                            pass

                    record = TrustedRecord(
                        entry_id=f"KANG-AKSH-{uid}",
                        original_kanglish=roman_word.lower(),
                        kannada_script=native_word,
                        english_meaning="",  # Rule 4: Transliteration only, NOT proof of English meaning!
                        context="word_transliteration",
                        dialect_register=DialectRegister.STANDARD_COLLOQUIAL.value,
                        slang_or_profanity_label=SlangProfanityLabel.CLEAN.value,
                        source="aksharantar_transliteration",
                        license=rec_license,
                        attribution=AKSHARANTAR_ATTRIBUTION,
                        confidence=confidence,
                        review_status=ReviewStatus.RAW.value,
                        reviewers=[],
                        ambiguity_status=AmbiguityStatus.NONE.value,
                        ambiguity_notes="",
                        data_type=DataType.TRANSLITERATION.value,
                        source_url=AKSHARANTAR_URL,
                        source_checksum=AKSHARANTAR_CHECKSUM
                    )

                    yield record
                    count += 1
                    if limit is not None and count >= limit:
                        return

                except Exception:
                    continue
