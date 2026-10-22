"""Mechanical fixtures only: no authentic messages or linguistic gold data.

All populated CSVs live in TemporaryDirectory. Ollama is mocked throughout.
"""

import argparse
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("representation", ROOT / "scripts" / "representation_experiment.py")
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def fixture(number=1, split="dev"):
    # Opaque tokens exercise structure, never plausible conversations/translations.
    token = hashlib.sha256(f"mechanical-fixture-{number}".encode()).hexdigest()[:32]
    row = dict.fromkeys(experiment.ANNOTATION_FIELDS, "")
    row.update(
        schema_version=experiment.VERSION, id=f"KGR1-{number:04d}", split=split,
        conversation_id=f"fixture-conversation-{number}", variant_group_id=f"fixture-variant-{number}",
        contributor_id=f"fixture-contributor-{number}", original_kanglish=token,
        intended_english=f"REFERENCE_SENTINEL_{number}", kannada_script="\u0c95" + token,
        source_type="purpose_written", source_provenance="unit-test-only; not linguistic data",
        usage_permission="granted", permission_scope="local_evaluation", permission_ref="fixture-consent",
        privacy_review="pass", reviewer_1_id="fixture-reviewer-1", reviewer_1_decision="accept",
        reviewer_2_id="fixture-reviewer-2", reviewer_2_decision="accept",
        kannada_reviewer_id="fixture-reviewer-2", kannada_review="accept",
        ambiguity_status="none", category="everyday",
    )
    return row


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        experiment.initialize(self.directory)

    def save(self, dev=(), evaluation=()):
        write_csv(self.directory / "dev.csv", experiment.ANNOTATION_FIELDS, dev)
        write_csv(self.directory / "eval.locked.csv", experiment.ANNOTATION_FIELDS, evaluation)

    def args(self, **changes):
        values = dict(data_dir=self.directory, split="dev", representations=["original", "human"],
                      indicxlit_csv=None, model="fixture-model:version", temperature=0.0, seed=17,
                      num_ctx=2048, num_predict=64, timeout=1, no_glossary=True, dry_run=False)
        values.update(changes)
        return argparse.Namespace(**values)

    def fake_api(self, endpoint, body=None, timeout=120):
        if endpoint == "/api/tags":
            return {"models": [{"name": "fixture-model:version", "digest": "fixture-digest"}]}
        if endpoint == "/api/ps":
            return {"models": [{"name": "fixture-model:version", "size": 1234, "size_vram": 0}]}
        if endpoint == "/api/generate":
            return {"response": "MODEL_OUTPUT_SENTINEL", "done": True, "load_duration": 1000000}
        raise AssertionError(f"unexpected endpoint: {endpoint}")

    def run_fake(self, api=None, **changes):
        with patch.object(experiment, "request_json", side_effect=api or self.fake_api) as mocked:
            with contextlib.redirect_stdout(io.StringIO()):
                experiment.run_experiment(self.args(**changes))
        return next((self.directory / "runs").iterdir()), mocked

    def rate(self, run, changes=None):
        rows, _ = experiment.read_csv(run / "human_reviews.csv", experiment.REVIEW_FIELDS)
        for row in rows:
            row.update(reviewer_1_id="judge-a", reviewer_2_id="judge-b", human_acceptance="accept")
            row.update({key: "no" for key in experiment.ERROR_FIELDS})
            if changes:
                changes(row)
        write_csv(run / "human_reviews.csv", experiment.REVIEW_FIELDS, rows)

    def test_templates_match_schema_and_have_no_examples_or_license_assignments(self):
        for name, fields in (("annotation_template.csv", experiment.ANNOTATION_FIELDS),
                             ("indicxlit_template.csv", experiment.INDICXLIT_FIELDS)):
            rows, _ = experiment.read_csv(ROOT / "data" / "representation_v1" / name, fields)
            self.assertEqual(rows, [])

    def test_empty_scaffold_is_structurally_valid_but_cannot_run_or_freeze(self):
        _, _, errors, warnings = experiment.load_dataset(self.directory)
        self.assertFalse(errors)
        self.assertTrue(any("0/80" in warning for warning in warnings))
        with patch.object(experiment, "request_json") as api:
            with self.assertRaisesRegex(ValueError, "no contributed"):
                experiment.run_experiment(self.args())
            api.assert_not_called()
        with self.assertRaisesRegex(ValueError, "exactly 80"):
            experiment.lock_evaluation(self.directory)
        self.assertFalse((self.directory / "eval.lock.json").exists())
        self.assertFalse((self.directory / "runs").exists())

    def test_initialize_preserves_existing_contributions(self):
        self.save([fixture()])
        before = (self.directory / "dev.csv").read_bytes()
        experiment.initialize(self.directory)
        self.assertEqual(before, (self.directory / "dev.csv").read_bytes())

    def test_bad_headers_and_extra_fields_are_rejected(self):
        path = self.directory / "dev.csv"
        path.write_text("id,original_kanglish\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "header"):
            experiment.load_dataset(self.directory)
        self.save([fixture()])
        with path.open("a", encoding="utf-8") as stream:
            stream.write("," * len(experiment.ANNOTATION_FIELDS) + "extra\n")
        with self.assertRaisesRegex(ValueError, "number of CSV fields"):
            experiment.load_dataset(self.directory)

    def test_missing_reference_and_unknown_schema_are_rejected(self):
        row = fixture()
        row.update(intended_english="", schema_version="future-unknown")
        errors, _ = experiment.validate_rows({"dev": [row], "eval": []})
        self.assertTrue(any("missing intended_english" in error for error in errors))
        self.assertTrue(any("unsupported schema" in error for error in errors))

    def test_duplicate_ids_and_duplicate_inputs_are_rejected(self):
        first, second = fixture(), fixture(2)
        second.update(id=first["id"], original_kanglish=first["original_kanglish"])
        errors, _ = experiment.validate_rows({"dev": [first, second], "eval": []})
        self.assertTrue(any("duplicate id" in error for error in errors))
        self.assertTrue(any("duplicate input/context" in error for error in errors))

    def test_normalized_and_fuzzy_overlap_across_splits_is_blocked(self):
        for text in ("mechanical toool probe", "mechanical tool probes"):
            with self.subTest(text=text):
                first, second = fixture(), fixture(2, "eval")
                first["original_kanglish"] = "mechanical tool probe"
                second["original_kanglish"] = text
                errors, _ = experiment.validate_rows({"dev": [first], "eval": [second]})
                self.assertTrue(any("cross-split overlap" in error for error in errors))

    def test_native_rendering_overlap_is_also_blocked_across_splits(self):
        first, second = fixture(), fixture(2, "eval")
        second["kannada_script"] = first["kannada_script"]
        errors, _ = experiment.validate_rows({"dev": [first], "eval": [second]})
        self.assertTrue(any("cross-split overlap" in error for error in errors))

    def test_conversation_variant_and_contributor_cannot_cross_splits(self):
        for field in ("conversation_id", "variant_group_id", "contributor_id"):
            with self.subTest(field=field):
                first, second = fixture(), fixture(2, "eval")
                second[field] = first[field].upper()
                errors, _ = experiment.validate_rows({"dev": [first], "eval": [second]})
                self.assertTrue(any(f"{field} crosses" in error for error in errors))

    def test_near_variants_can_remain_together_with_inspection_warning(self):
        first, second = fixture(), fixture(2)
        first["original_kanglish"] = "mechanical tool probe"
        second["original_kanglish"] = "mechanical tool probes"
        second["variant_group_id"] = first["variant_group_id"]
        second["conversation_id"] = first["conversation_id"]
        errors, warnings = experiment.validate_rows({"dev": [first, second], "eval": []})
        self.assertFalse(errors)
        self.assertTrue(any("inspect grouping" in warning for warning in warnings))

    def test_permission_privacy_and_human_review_gate_before_any_network_call(self):
        changes = [dict(usage_permission=value) for value in ("pending", "denied", "withdrawn")]
        changes += [dict(permission_scope="training"), dict(permission_ref=""),
                    dict(privacy_review="pending"), dict(reviewer_1_decision="pending"),
                    dict(reviewer_2_decision="reject"), dict(reviewer_2_id="fixture-reviewer-1"),
                    dict(ambiguity_status="unresolved", ambiguity_notes="still unresolved")]
        for change in changes:
            with self.subTest(change=change):
                row = fixture()
                row.update(change)
                self.save([row])
                with patch.object(experiment, "request_json") as api:
                    with self.assertRaises(ValueError):
                        experiment.run_experiment(self.args())
                    api.assert_not_called()

    def test_redistribution_license_needs_separate_explicit_permission(self):
        row = fixture()
        row["redistribution_license"] = "CC0-1.0"
        errors, _ = experiment.validate_rows({"dev": [row], "eval": []})
        self.assertTrue(any("separate explicit permission" in error for error in errors))
        row["redistribution_permission_ref"] = "fixture-license-consent"
        errors, _ = experiment.validate_rows({"dev": [row], "eval": []})
        self.assertFalse(errors)

    def test_optional_kannada_never_causes_silent_cohort_dropping(self):
        row = fixture()
        row.update(kannada_script="", kannada_review="not_provided", kannada_reviewer_id="")
        self.save([row])
        jobs, *_ = experiment.prepare(self.directory, "dev", ["original"])
        self.assertEqual(len(jobs), 1)
        with self.assertRaisesRegex(ValueError, "accepted Kannada rendering"):
            experiment.prepare(self.directory, "dev", ["original", "human"])
        row.update(kannada_script="\u0c95", kannada_review="pending")
        self.save([row])
        with self.assertRaisesRegex(ValueError, "accepted Kannada rendering"):
            experiment.prepare(self.directory, "dev", ["original", "human"])

    def test_eval_needs_freeze_and_any_frozen_edit_is_detected(self):
        dev = [fixture(i) for i in range(1, 21)]
        evaluation = [fixture(i, "eval") for i in range(21, 101)]
        self.save(dev, evaluation)
        with self.assertRaisesRegex(ValueError, "run lock-eval first"):
            experiment.prepare(self.directory, "eval", ["original", "human"])
        experiment.lock_evaluation(self.directory)
        jobs, *_ = experiment.prepare(self.directory, "eval", ["original", "human"])
        self.assertEqual(len(jobs), 160)
        with self.assertRaises(FileExistsError):
            experiment.lock_evaluation(self.directory)
        dev[0]["context"] = "EDITED AFTER FREEZE"
        self.save(dev, evaluation)
        with self.assertRaisesRegex(ValueError, "frozen dataset changed"):
            experiment.prepare(self.directory, "eval", ["original", "human"])

    def test_malformed_or_incomplete_evaluation_lock_is_rejected(self):
        lock_path = self.directory / "eval.lock.json"
        lock_path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "JSON object"):
            experiment.load_dataset(self.directory)
        self.save([fixture()], [fixture(2, "eval")])
        hashes = {split: experiment.sha256((self.directory / name).read_bytes())
                  for split, name in experiment.FILES.items()}
        lock_path.write_text(json.dumps({"schema_version": experiment.VERSION,
                                        "dataset_sha256": hashes, "counts": {"dev": 1, "eval": 1}}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lock counts"):
            experiment.prepare(self.directory, "eval", ["original", "human"])

    def test_indicxlit_requires_precomputed_provenance_and_exact_source(self):
        row = fixture()
        self.save([row])
        with self.assertRaisesRegex(ValueError, "precomputed"):
            experiment.prepare(self.directory, "dev", list(experiment.REPRESENTATIONS))
        sidecar = self.directory / "indicxlit.csv"
        item = dict(schema_version=experiment.VERSION, id=row["id"], source_kanglish=row["original_kanglish"],
                    indicxlit_output="MACHINE_RENDERING_SENTINEL", engine="IndicXlit",
                    model_revision="fixture-revision", generation_settings='{"beam": 4}')
        write_csv(sidecar, experiment.INDICXLIT_FIELDS, [item])
        jobs, *_ = experiment.prepare(self.directory, "dev", list(experiment.REPRESENTATIONS), sidecar)
        self.assertEqual(len(jobs), 3)
        item["source_kanglish"] = "STALE_SOURCE_SENTINEL"
        write_csv(sidecar, experiment.INDICXLIT_FIELDS, [item])
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            experiment.prepare(self.directory, "dev", list(experiment.REPRESENTATIONS), sidecar)

    def test_indicxlit_never_substitutes_dictionary_or_unversioned_data(self):
        row = fixture()
        sidecar = self.directory / "indicxlit.csv"
        item = dict(schema_version=experiment.VERSION, id=row["id"], source_kanglish=row["original_kanglish"],
                    indicxlit_output="MACHINE_RENDERING_SENTINEL", engine="dictionary",
                    model_revision="fixture-revision", generation_settings="{}")
        write_csv(sidecar, experiment.INDICXLIT_FIELDS, [item])
        with self.assertRaisesRegex(ValueError, "engine=IndicXlit"):
            experiment.load_indicxlit(sidecar, [row])

    def test_prompt_keeps_original_context_and_same_glossary_without_reference_leakage(self):
        row = fixture()
        row.update(original_kanglish="mechanical probe", context="CONTEXT_SENTINEL",
                   ambiguity_notes="ANNOTATION_SENTINEL", acceptable_alternatives="ALTERNATIVE_SENTINEL")
        glossary = [("probe", "GLOSSARY_SENTINEL")]
        original = json.loads(experiment.make_prompt(row, "", glossary))
        rendered = json.loads(experiment.make_prompt(row, row["kannada_script"], glossary))
        self.assertEqual(rendered.pop("optional_kannada_rendering"), row["kannada_script"])
        self.assertEqual(original, rendered)
        prompt = experiment.make_prompt(row, row["kannada_script"], glossary)
        for secret in (row["intended_english"], row["ambiguity_notes"], row["acceptable_alternatives"]):
            self.assertNotIn(secret, prompt)

    def test_dry_run_is_offline_and_writes_nothing(self):
        self.save([fixture()])
        with patch.object(experiment, "request_json") as api, contextlib.redirect_stdout(io.StringIO()):
            experiment.run_experiment(self.args(dry_run=True))
            api.assert_not_called()
        self.assertFalse((self.directory / "runs").exists())

    def test_runner_fixes_model_settings_and_leaves_every_human_rating_blank(self):
        self.save([fixture()])
        run, api = self.run_fake()
        calls = [call.args[1] for call in api.call_args_list if call.args[0] == "/api/generate"]
        self.assertEqual(len(calls), 2)
        for field in ("model", "system", "options", "think", "stream"):
            self.assertEqual(calls[0][field], calls[1][field])
        reviews, _ = experiment.read_csv(run / "human_reviews.csv", experiment.REVIEW_FIELDS)
        self.assertTrue(all(not row[field] for row in reviews for field in experiment.RATING_FIELDS))
        self.assertEqual({row["conversation_id"] for row in reviews}, {fixture()["conversation_id"]})
        report = experiment.summarize(run)
        self.assertIsNone(report["conditions"]["original"]["acceptance_rate"])
        self.assertEqual(report["conditions"]["human"]["pending"], 1)
        self.assertEqual(report["conditions"]["original"]["max_observed_ollama_model_bytes"], 1234)

    def test_human_summary_uses_consensus_and_paired_changes(self):
        self.save([fixture()])
        run, _ = self.run_fake()
        predictions, _ = experiment.read_csv(run / "predictions.csv", experiment.RESULT_FIELDS)
        baseline = next(row["case_id"] for row in predictions if row["representation"] == "original")
        def decisions(row):
            if row["case_id"] == baseline:
                row.update(human_acceptance="reject", meaning_error="yes", polarity_error="yes", notes="fixture disagreement in meaning")
        self.rate(run, decisions)
        report = experiment.summarize(run)
        self.assertEqual(report["conditions"]["original"]["acceptance_rate"], 0)
        self.assertEqual(report["conditions"]["human"]["acceptance_rate"], 1)
        self.assertEqual(report["conditions"]["original"]["human_error_counts"]["polarity_error"], 1)
        self.assertEqual(report["paired_against_original"]["human"]["wins"], 1)
        self.assertEqual(report["paired_against_original"]["human"]["acceptance_delta"], 1)

    def test_timeout_stays_in_denominator_and_unavailable_memory_is_not_zero(self):
        self.save([fixture()])
        def api(endpoint, body=None, timeout=120):
            if endpoint == "/api/generate":
                raise TimeoutError("mechanical test timeout")
            if endpoint == "/api/ps":
                raise urllib.error.URLError("unsupported")
            return self.fake_api(endpoint, body, timeout)
        run, _ = self.run_fake(api)
        result = experiment.summarize(run)["conditions"]["original"]
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["generation_failures"], 1)
        self.assertEqual(result["acceptance_rate"], 0)
        self.assertIsNone(result["max_observed_ollama_model_bytes"])

    def test_truncated_output_is_an_operational_failure(self):
        self.save([fixture()])
        def api(endpoint, body=None, timeout=120):
            reply = self.fake_api(endpoint, body, timeout)
            if endpoint == "/api/generate":
                reply["done_reason"] = "length"
            return reply
        run, _ = self.run_fake(api)
        self.assertEqual(experiment.summarize(run)["conditions"]["human"]["generation_failures"], 1)

    def test_missing_and_contradictory_human_ratings_are_rejected(self):
        self.save([fixture()])
        run, _ = self.run_fake()
        self.rate(run, lambda row: row.update(polarity_error="yes"))
        with self.assertRaisesRegex(ValueError, "contradicts"):
            experiment.summarize(run)
        self.rate(run, lambda row: row.update(reviewer_2_id="judge-a"))
        with self.assertRaisesRegex(ValueError, "distinct reviewers"):
            experiment.summarize(run)
        self.rate(run)
        rows, _ = experiment.read_csv(run / "human_reviews.csv", experiment.REVIEW_FIELDS)
        write_csv(run / "human_reviews.csv", experiment.REVIEW_FIELDS, rows[:1])
        with self.assertRaisesRegex(ValueError, "retain every planned case"):
            experiment.summarize(run)

    def test_changed_predictions_or_review_source_fields_are_rejected(self):
        self.save([fixture()])
        run, _ = self.run_fake()
        self.rate(run, lambda row: row.update(intended_english="ALTERED_REFERENCE"))
        with self.assertRaisesRegex(ValueError, "fixed source/output"):
            experiment.summarize(run)
        with (run / "predictions.csv").open("a", encoding="utf-8") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "frozen prediction data changed"):
            experiment.summarize(run)

    def test_malformed_run_manifest_is_rejected(self):
        (self.directory / "manifest.json").write_text("null", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "manifest schema"):
            experiment.summarize(self.directory)

    def test_model_change_invalidates_run(self):
        self.save([fixture()])
        tag_calls = 0
        def api(endpoint, body=None, timeout=120):
            nonlocal tag_calls
            reply = self.fake_api(endpoint, body, timeout)
            if endpoint == "/api/tags":
                tag_calls += 1
                reply["models"][0]["digest"] = f"changed-{tag_calls}"
            return reply
        with self.assertRaisesRegex(ValueError, "model digest changed"):
            self.run_fake(api)
        run = next((self.directory / "runs").iterdir())
        with self.assertRaisesRegex(ValueError, "incomplete"):
            experiment.summarize(run)

    def test_redirects_are_refused(self):
        with self.assertRaisesRegex(urllib.error.URLError, "redirect refused"):
            experiment.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://invalid.example")

    def test_request_transport_uses_loopback_and_disables_environment_proxies(self):
        class FakeOpener:
            def open(inner, request, timeout):
                self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/generate")
                self.assertEqual(json.loads(request.data), {"prompt": "TRANSPORT_FIXTURE"})
                self.assertEqual(timeout, 2)
                return io.BytesIO(b'{"done": true}')
        with patch.object(experiment.urllib.request, "build_opener", return_value=FakeOpener()) as build:
            self.assertEqual(experiment.request_json("/api/generate", {"prompt": "TRANSPORT_FIXTURE"}, 2), {"done": True})
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], experiment.NoRedirect)

    def test_uninstalled_model_is_rejected_without_generation_or_output_files(self):
        self.save([fixture()])
        with patch.object(experiment, "request_json", return_value={"models": []}) as api:
            with self.assertRaisesRegex(ValueError, "never downloads"):
                experiment.run_experiment(self.args())
        self.assertEqual([call.args[0] for call in api.call_args_list], ["/api/tags"])
        self.assertFalse((self.directory / "runs").exists())

    def test_all_three_arms_use_identical_decoder_configuration(self):
        row = fixture()
        self.save([row])
        sidecar = self.directory / "indicxlit.csv"
        write_csv(sidecar, experiment.INDICXLIT_FIELDS, [{
            "schema_version": experiment.VERSION, "id": row["id"], "source_kanglish": row["original_kanglish"],
            "indicxlit_output": "MACHINE_RENDERING_SENTINEL", "engine": "IndicXlit",
            "model_revision": "fixture-revision", "generation_settings": '{"beam":4}',
        }])
        run, api = self.run_fake(representations=list(experiment.REPRESENTATIONS), indicxlit_csv=sidecar)
        bodies = [call.args[1] for call in api.call_args_list if call.args[0] == "/api/generate"]
        self.assertEqual(len(bodies), 3)
        prompts = [json.loads(body["prompt"]) for body in bodies]
        self.assertEqual({prompt["original_kanglish"] for prompt in prompts}, {row["original_kanglish"]})
        self.assertEqual({prompt.get("optional_kannada_rendering", "") for prompt in prompts},
                         {"", row["kannada_script"], "MACHINE_RENDERING_SENTINEL"})
        fixed = [{key: value for key, value in body.items() if key != "prompt"} for body in bodies]
        self.assertEqual(fixed, [fixed[0]] * 3)
        self.rate(run)
        self.assertEqual(experiment.summarize(run)["paired_against_original"]["indicxlit"]["reviewed_pairs"], 1)

    def test_cli_returns_error_for_unready_data_and_invalid_options(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(experiment.main(["--data-dir", str(self.directory), "validate"]), 0)
            self.assertEqual(experiment.main(["--data-dir", str(self.directory), "validate", "--ready"]), 2)
            self.assertEqual(experiment.main(["--data-dir", str(self.directory), "run", "--split", "dev", "--model", "fixture", "--temperature", "nan"]), 2)


if __name__ == "__main__":
    unittest.main()
