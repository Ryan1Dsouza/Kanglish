"""Regression tests use structural sentinels, not invented Kannada gold labels."""

from collections import Counter
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import prepare_quality_dataset as prepare
from scripts.trusted_pipeline.importers.alar_importer import _create_record, stream_alar_records
from scripts.trusted_pipeline.importers.slang_importer import stream_slang_records
from scripts.trusted_pipeline.quality import (
    assert_clean_training_records, balanced_lexicon_sample, english_target_issue,
    grouped_split, training_pair, variant_key,
)


def record(source, target, group=None):
    return {"id": source, "group_id": group or source, "provenance": [{"fixture": source}],
            "messages": [{"role": "system", "content": "STRUCTURAL_FIXTURE"},
                         {"role": "user", "content": source},
                         {"role": "assistant", "content": target}]}


def lexical(source, target, identifier):
    return {"entry_id": identifier, "original_kanglish": source, "kannada_script": "",
            "english_meaning": target, "source": "FIXTURE_SOURCE", "license": "FIXTURE_LICENSE",
            "attribution": "FIXTURE_ATTRIBUTION", "source_url": "local://fixture", "source_checksum": "a" * 64,
            "review_status": "raw", "data_type": "lexicon"}


class TrainingQualityTests(unittest.TestCase):
    def test_dictionary_pointers_and_full_kannada_range_are_rejected(self):
        for value in ("= WORD_FIXTURE", "= ಅಚ್ಚರಿಗೊಳ್ಳು.", "→ WORD_FIXTURE", "English plus ಕ", "ಅ", "", None, 42):
            self.assertIsNotNone(english_target_issue(value), repr(value))
        self.assertIsNone(english_target_issue("ENGLISH_DEFINITION_SENTINEL"))

    def test_importer_does_not_restore_a_pointer_as_its_fallback_definition(self):
        base = {"id": 1, "entry": "HEADWORD_FIXTURE", "phone": "phonefixture"}
        self.assertIsNone(_create_record(dict(base, defs=["= ಕ."])))
        result = _create_record(dict(base, defs=["= ಕ.", "DEFINITION_SENTINEL"]))
        self.assertEqual(result.english_meaning, "DEFINITION_SENTINEL")

    def test_streaming_importer_skips_cross_reference_only_records(self):
        text = ("- id: 1\n  entry: HEAD_A\n  phone: phonea\n  defs:\n"
                "    - id: 1\n      entry: = ಕ.\n"
                "- id: 2\n  entry: HEAD_B\n  phone: phoneb\n  defs:\n"
                "    - id: 2\n      entry: DEFINITION_SENTINEL\n")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.yml"
            path.write_text(text, encoding="utf-8")
            rows = list(stream_alar_records(str(path)))
        self.assertEqual([row.entry_id for row in rows], ["KANG-ALAR-000002"])

    def test_sampling_covers_late_dictionary_letters_and_is_deterministic(self):
        rows = [lexical(initial + suffix, "DEFINITION_" + initial + suffix, initial + suffix)
                for initial in "abmnz" for suffix in ("first", "second", "third")]
        sample = balanced_lexicon_sample(rows, limit=10, seed=7)
        self.assertEqual(Counter(row["original_kanglish"][0] for row in sample), {c: 2 for c in "abmnz"})
        self.assertEqual(sample, balanced_lexicon_sample(list(reversed(rows)), limit=10, seed=7))

    def test_sampling_excludes_conflicting_meanings_and_invalid_targets(self):
        rows = [lexical("ambiguous", "MEANING_ONE", "1"), lexical("ambiguous", "MEANING_TWO", "2"),
                lexical("badlabel", "= POINTER", "3"), lexical("safeinput", "DEFINITION_SENTINEL", "4")]
        self.assertEqual([r["original_kanglish"] for r in balanced_lexicon_sample(rows)], ["safeinput"])

    def test_training_guard_rejects_old_bad_labels_and_empty_data(self):
        with self.assertRaisesRegex(ValueError, "1 invalid rows"):
            assert_clean_training_records([record("SOURCE_FIXTURE", "= POINTER")])
        with self.assertRaisesRegex(ValueError, "empty"):
            assert_clean_training_records([])
        assert_clean_training_records([record("SOURCE_FIXTURE", "DEFINITION_SENTINEL")])

    def test_split_keeps_spelling_source_and_answer_siblings_together(self):
        rows = [record(f"input {index}", f"answer {index}") for index in range(80)]
        rows += [record("vaariant?", "ANSWER_A", "paired-source"),
                 record("variant", "ANSWER_B", "another-source"),
                 record("NATIVE_SOURCE_FIXTURE", "ANSWER_C", "paired-source"),
                 record("separate input", "ANSWER_B", "third-source")]
        training, validation = grouped_split(rows, validation_fraction=0.2, seed=9)
        train_keys = {variant_key(training_pair(r)[0]) for r in training}
        validation_keys = {variant_key(training_pair(r)[0]) for r in validation}
        self.assertFalse(train_keys & validation_keys)
        self.assertFalse({r["group_id"] for r in training} & {r["group_id"] for r in validation})
        self.assertFalse({variant_key(training_pair(r)[1]) for r in training} &
                         {variant_key(training_pair(r)[1]) for r in validation})
        siblings = {"vaariant?", "variant", "NATIVE_SOURCE_FIXTURE", "separate input"}
        self.assertIn(len(siblings & {r["id"] for r in training}), (0, len(siblings)))
        second_train, _ = grouped_split(list(reversed(rows)), validation_fraction=0.2, seed=9)
        self.assertEqual({r["id"] for r in training}, {r["id"] for r in second_train})

    def test_conflicting_targets_are_quarantined_instead_of_arbitrarily_selected(self):
        review = []
        kept = prepare.remove_conflicts([record("same", "ONE"), record("SAME", "TWO"), record("other", "THREE")], review)
        self.assertEqual([r["id"] for r in kept], ["other"])
        self.assertEqual(len(review), 2)

    def test_seed_reviewer_names_cannot_create_human_verified_slang(self):
        rows = list(stream_slang_records())
        self.assertEqual(len(rows), 11)
        self.assertTrue(all(r.review_status == "needs-human-review" and not r.reviewers for r in rows))
        self.assertTrue(all(len(r.source_checksum) == 64 for r in rows))
        row = rows[0]
        row.review_status = "human-verified"
        row.reviewers = ["reviewer_kannada_1", "reviewer_kannada_2"]
        self.assertTrue(any("placeholder" in error for error in row.validate()))

    def test_candidate_export_uses_sources_and_leaves_teacher_references_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def save_csv(name, rows):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
            def save_jsonl(name, rows):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            lexicon = [lexical(c + "word", "LEXICAL_SENTINEL_" + c, "LEX_" + c) for c in "abcdefghijklmnopqrstuvwxyz"]
            conversations = []
            for c in "abcdefghijklmnopqrstuvwxyz":
                row = lexical("", "CONVERSATION_SENTINEL_" + c, "CONV_" + c)
                row.update(kannada_script="NATIVE_FIXTURE_" + c, data_type="conversational")
                conversations.append(row)
            save_csv("data/trusted/lexicon_alar.csv", lexicon)
            save_csv("data/trusted/conversational_bpcc.csv", conversations)
            save_csv("data/reserved_fixture.csv", [{"input": "awooord?"}])
            save_jsonl("data/processed/kanglish_v3_train.jsonl", [
                record("bad", "= POINTER"), record("TEACHER_INPUT", "TEACHER_OUTPUT"),
                record("UNTRACED_INPUT", "UNTRACED_OUTPUT"), record("NATIVE_FIXTURE_a", "CONVERSATION_SENTINEL_a")])
            save_jsonl("data/processed/gemini_teacher_dataset.jsonl", [{"kanglish": "TEACHER_INPUT", "english": "TEACHER_OUTPUT"}])
            with patch.object(prepare, "RESERVED_FILES", {"data/reserved_fixture.csv": "input"}):
                training, validation, review, report = prepare.build(root, 26, 26, seed=42)
            self.assertTrue(training and validation)
            self.assertIsNone(report["human_accuracy"])
            self.assertTrue(all(r["review_status"] == "raw" and r["provenance"] for r in training + validation))
            self.assertNotIn("aword", {training_pair(r)[0] for r in training + validation})
            reasons = {r["reason"] for r in review}
            self.assertIn("unresolved_dictionary_reference", reasons)
            self.assertIn("teacher_pair_needs_semantic_review", reasons)
            self.assertIn("legacy_pair_without_traceable_semantic_source", reasons)
            self.assertTrue(all(english_target_issue(training_pair(r)[1]) is None for r in training + validation))


if __name__ == "__main__":
    unittest.main()
