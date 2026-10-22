"""Build the Gate A report from saved evidence; never run inference or training."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import statistics

from .contract import ROOT, read_jsonl, sha, write_json
from .checks import chrf_score, chrf_stats, metric_summary


RUN = ROOT / 'results/student_gate_a_20261019'
DATA = ROOT / 'data/processed/student_gate_a_v1'
REPORT = ROOT / 'research/STUDENT_GATE_A_REPORT_2026-10-19.md'
SUITES = [('Draft benchmark', 'baseline_benchmark_current'),
          ('IN22-Conv Romanized', 'baseline_in22'),
          ('Dictionary holdout', 'baseline_dictionary'),
          ('Controls and known failures', 'baseline_controls')]


def cell(value):
    return str(value).replace('|', '\\|').replace('\r', ' ').replace('\n', ' ')


def ratio(m, numerator, denominator):
    a, b = m[numerator], m[denominator]
    return f'{a}/{b} ({100*a/b:.1f}%)' if b else 'N/A'


def main():
    manifest = json.loads((DATA / 'manifest.json').read_text())
    config = json.loads((DATA / 'config.json').read_text())
    verification_path = RUN / 'dataset_verification.json'
    verification = json.loads(verification_path.read_text()) if verification_path.exists() else None
    verification_state = 'PASS' if verification and verification['passed'] else ('FAILED' if verification else 'NOT FINISHED')
    rows = []
    summaries = []
    for title, folder in SUITES:
        out = RUN / folder
        if not (out / 'metrics.json').exists():
            summaries.append((title, folder, None))
            continue
        raw_summary = json.loads((out / 'metrics.json').read_text())
        raw_rows = read_jsonl(out / 'predictions.jsonl')
        visible_rows = [dict(r, raw_candidate_output=r.get('output', ''),
                             output=r.get('output', '') if r['status'] == 'ok' else '') for r in raw_rows]
        summary = dict(raw_summary, overall=metric_summary(visible_rows),
                       by_suite={suite: metric_summary([r for r in visible_rows if r['suite'] == suite])
                                 for suite in sorted({r['suite'] for r in visible_rows})},
                       scoring_policy='Failed generations are empty translations because Android rejects partial output.',
                       raw_candidate_chrf2=raw_summary['overall']['chrf2'])
        write_json(out / 'app_visible_metrics.json', summary)
        summaries.append((title, folder, summary))
        rows.extend(visible_rows)
        saved_config = json.loads((out / 'config.json').read_text())
        snapshot = out / 'source_snapshot'
        snapshot.mkdir(exist_ok=True)
        for name, key in [('contract.py', 'contract'), ('evaluate.py', 'evaluator'), ('checks.py', None)]:
            source = Path(__file__).with_name(name)
            if key and sha(source) != saved_config['input_sha256'][key]:
                raise ValueError('Cannot snapshot changed baseline code: ' + name)
            shutil.copy2(source, snapshot / name)
        write_json(snapshot / 'sha256.json', {p.name: sha(p) for p in snapshot.glob('*.py')})
    scored = [dict(r, sentence_chrf2=chrf_score(chrf_stats(r.get('output', ''), r['english'])))
              for r in rows if r.get('english') and r['category'] != 'abstention']
    worst = sorted(scored, key=lambda r: (r['sentence_chrf2'], r['id']))[:30]
    write_json(RUN / 'baseline_worst_30.json', worst)
    write_json(RUN / 'baseline_summary.json', {
        title: summary for title, folder, summary in summaries})
    negative = [r for r in rows if r['category'] == 'abstention']
    real = [r for r in rows if r['category'] != 'abstention']
    abstained = sum(r.get('output', '').strip() == '[unclear]' for r in negative)
    false_abstained = sum('[unclear]' in r.get('output', '').lower() for r in real)
    complete = all(s and s['complete'] for _, _, s in summaries)
    lines = [
        '# Kanglish student repair: Gate A report', '',
        f'Generated {datetime.now(timezone.utc).isoformat()}. **Stopped at Gate A. Training is not authorized yet.**', '',
        f'The v3 model produced the required abstention on {abstained}/{len(negative)} negative controls. '
        'It still invents translations for gibberish and reverses meaning on some real Kannada inputs. '
        'The prepared data is a candidate repair, not evidence of an improved student.', '',
        f'Phase 0 evaluation: {"complete" if complete else "incomplete"}. '
        f'Post-export verification: **{verification_state}**. '
        'Phase B training, Gate B comparison, Phase C quantization and device measurements have not run. '
        'The user imposed a 10-minute finalization limit ending at 2026-10-19 12:55:32 UTC.', '',
        '[Review sample: 200 translation rows and 50 abstention rows](../data/processed/student_gate_a_v1/review_sample.csv). '
        '[Quarantined candidates](../data/processed/student_gate_a_v1/review_queue.csv). '
        '[Data manifest](../data/processed/student_gate_a_v1/manifest.json).', '',
        'A Kannada-fluent reviewer must mark exactly one of `ok` or `wrong` for every sample row and add corrections in `notes`. '
        'Use `1`, `yes`, or `x` as a mark. Keep source and English columns intact. '
        'The checker requires at most 10% wrong in each section (at most 20/200 translation rows and 5/50 abstention rows). '
        'Your explicit confirmation is still required after the review passes. No candidate has been used to train a student.', '',
        '**Current v3 Q8_0 baseline**', '',
        '| Suite | Cases | chrF2 | Negation polarity mismatches | Operational failures |',
        '|---|---:|---:|---:|---:|'
    ]
    for title, folder, summary in summaries:
        if summary:
            m = summary['overall']
            lines.append(f'| [{title}](../results/student_gate_a_20261019/{folder}/app_visible_metrics.json) | {summary["processed"]}/{summary["expected"]} | {m["chrf2"]:.2f} | {m["negation_polarity_errors"]}/{m["negation_eligible"]} | {m["operational_failures"]} |')
        else:
            lines.append(f'| {title} | Not completed | N/A | N/A | N/A |')
    lines += ['', '| Suite | Dictionary exact match | Number preservation | Name preservation |',
              '|---|---:|---:|---:|']
    for title, _, summary in summaries:
        if summary:
            m = summary['overall']
            lines.append('| ' + title + ' | ' + ' | '.join([
                ratio(m, 'dictionary_exact_matches', 'dictionary_rows'),
                ratio(m, 'number_preserved', 'number_eligible'),
                ratio(m, 'name_preserved', 'name_eligible')]) + ' |')
    lines += ['', f'Negative-control abstention: **{abstained}/{len(negative)}**. '
              f'False abstention on real inputs: **{false_abstained}/{len(real)}**. '
              'Zero false abstentions is not useful reassurance when the model never abstains.', '',
              'chrF2 uses character orders 1–6, beta=2, case-sensitive text, and excludes whitespace. '
              'The controls/failures chrF2 score covers only its three real inputs. '
              'Negation checks compare explicit English polarity markers; names use heuristic extraction and spelling matching. '
              'Number preservation compares numeric tokens, so spelled-out numbers can fail this diagnostic. '
              'These are diagnostics, not Kannada-speaker semantic accuracy. The draft benchmark and dictionary sample are unreviewed. '
              'IN22 English references are human translations, but their Romanization is machine-generated. '
              'Operational failures stay in the saved predictions and metrics. '
              'For the reported app-visible metrics, failed generations are scored as empty translations because Android rejects partial outputs. '
              'The original metrics.json files preserve raw-candidate scores (IN22 chrF2 15.7252), including partial text from 22 output-limit failures. '
              'Use app_visible_metrics.json and the same failure policy for subsequent student comparisons.', '',
              '| Requested input | Reference | v3 output |', '|---|---|---|']
    for row in rows:
        if row.get('suite') == 'known_failures':
            lines.append('| ' + ' | '.join(cell(row[k]) for k in ('romanized_input', 'english', 'output')) + ' |')
    timings = [r['elapsed_ms'] for r in rows if r['route'] == 'student_model']
    token_rows = [r for r in rows if r.get('telemetry', {}).get('prompt_eval_count') is not None]
    lines += ['', 'Every suite folder contains `predictions.jsonl`, `metrics.json`, `config.json`, `worst_30.json`, and a source snapshot. '
              'All inference used the unchanged GGUF through local Ollama 0.23.2, raw ChatML, the app glossary route, '
              'temperature 0.1, seed 42, context 1024 and a 192-token response cap. History and learned glossary were empty. '
              'No external model API calls, paid services, or private chats were used.', '',
              f'Median desktop model-route wall time: {statistics.median(timings):.1f} ms. '
              f'Token precheck matched runtime prompt counts on {sum(r["prompt_tokens_precheck"] == r["telemetry"]["prompt_eval_count"] for r in token_rows)}/{len(token_rows)} recorded cases. '
              'This is not an Android/S23 FE latency or runtime-parity measurement.', '',
              'An independent workspace edit changed `TranslationPrompt.kt` during preparation. The current baseline and candidate prompts '
              'use the new time/negation hints; their frozen prompt SHA256 is '
              f'`{config["prompt_sha256"]}`. '
              'The earlier `baseline_benchmark` run used the older prompt and is superseded. '
              'This task made no Android feature or audio-roadmap edits.', '',
              '**Candidate data**', '',
              '| Category | Training candidates | Validation candidates |', '|---|---:|---:|']
    for category in ('conversation', 'dictionary', 'abstention'):
        lines.append(f'| {category} | {manifest["train_by_category"].get(category, 0):,} | {manifest["validation_by_category"].get(category, 0):,} |')
    lines += [f'| Total | {manifest["train_rows"]:,} | {manifest["validation_rows"]:,} |', '',
              'Conversation targets are copied verbatim from BPCC-H human translations; source IDs from `quality_v1` are tracked. '
              'Kannada inputs were Romanized with pretrained AI4Bharat IndicXlit, followed by 3–5 spelling variants plus the base input. '
              'English/Latin spans, detected names, time words and negation markers are protected. Duplicate variants are removed. '
              'Dictionary targets are short authored Alar senses with unresolved references excluded; they are review candidates. '
              'Before training, dictionary senses must meet the user’s reviewed-sense requirement; a passing random sample alone is not row-level review of every sense.', '',
              f'Dictionary coverage: {sum(manifest["dictionary_initials"].values()):,} entries across {len(manifest["dictionary_initials"])} initials '
              f'({min(manifest["dictionary_initials"].values())}–{max(manifest["dictionary_initials"].values())} each). '
              f'{manifest["real_rare_dictionary_rows"]} entries occur at most once in Aksharantar native training words. '
              'This is a rarity proxy, not confirmation that each word is rare. Real words retain their normal dictionary target.', '',
              'The 250 abstention candidates map only to `[unclear]` and were absent from 156,620 Alar entries, 489 glossary entries, '
              'and Aksharantar train/validation/test inventories (2,906,728 / 7,025 / 11,380 rows). '
              'Inventory absence cannot establish absence from all Kannada words or names. '
              'No mixed partial-abstention sentences were fabricated; none had reviewer-confirmed references.', '',
              'Each row records source group, source ID/provenance and license. Conversation references come from '
              '`data/trusted/conversational_bpcc.csv`; dictionary senses come from `data/trusted/lexicon_alar.csv`. '
              'Synthetic controls record `project_generated_candidate`. See the JSONL provenance fields for upstream attribution and URLs.', '',
              'Source groups and spelling families are kept in one split. Benchmark, IN22, dictionary holdout, requested failures and '
              'other reserved cases are excluded using normalized inputs, native text and English references. '
              'The fuzzy guard uses SequenceMatcher >=0.88, compact/repeated-letter/ph-f families, and edit distance <=1 for strings of length 4–10. '
              'This is the implemented near-duplicate definition; it is not a semantic-paraphrase detector.', '',
              f'Review queue: {manifest["review_queue_rows"]:,} distinct queued records: '
              f'{manifest["review_queue_by_source"].get("bpcc_h_daily_conversational",0):,} BPCC, '
              f'{manifest["review_queue_by_source"].get("alar_kannada_english_dict",0):,} dictionary and '
              f'{manifest["review_queue_by_source"].get("historical_llm_teacher_output",0):,} historical teacher candidates. '
              'Historical teacher outputs are review candidates only. '
              'No new teacher output was generated. Some BPCC pairs localize people’s names, including Bhuvana/George and Modi/Trump; '
              'suspected mismatches were quarantined without changing the human English text.', '',
              '| Rejection reason | Reason events |', '|---|---:|']
    for reason, count in manifest['counts'].items():
        if reason.startswith('rejected:'):
            lines.append(f'| {reason.removeprefix("rejected:")} | {count:,} |')
    lines += ['', 'Rejection counts are reason events and must not be added as distinct rejected rows. '
              'Selection caps were 1,500 conversation source groups and 1,000 dictionary entries. No rows were padded to reach a target.', '',
              '**Verification and reproducibility limits**', '',
              'Nine targeted tests passed: prompt and glossary contract, fuzzy-index candidate coverage, short-typo detection, '
              'one-edit distance, structural quarantine rules, protected spelling variants and chrF identity/no-overlap. '
              'No Android build was required because this task did not edit Android code.', '',
              f'Independent post-export verification: **{verification_state}**. '
              '[Full verification evidence](../results/student_gate_a_20261019/dataset_verification.json).']
    if verification:
        lines += ['', f'Checked {verification["rows"]:,} rows; {len(verification["errors"])} recorded errors; '
                  f'{len(verification["cross_split_variant_matches"])} cross-split spelling-variant matches. '
                  f'Source-group overlap: {verification["source_group_overlap"]}. '
                  f'Protected evaluation/data hashes unchanged: {verification["protected_evaluation_and_glossary_data_unchanged"]}.']
        if verification['errors']:
            lines += ['', '**These verification errors must be resolved before any training:**', '',
                      '```json', json.dumps(verification['errors'][:20], ensure_ascii=False, indent=2), '```']
    lines += ['', 'IndicXlit uses the official pretrained indic-en v1.0 tensors through a local PyTorch adapter: all 263 learned tensors '
              'were mapped, with no trained replacement weights. Decoding is greedy with a Latin/EOS mask and no frequency rescoring. '
              'Independent numerical parity with the original Fairseq runtime has not been established. '
              'The 12,274-token cache had no unknown input characters or incomplete generations, but that does not prove correct Romanization. '
              'The Kannada reviewer must check spelling variants and meanings.', '',
              'Baseline GGUF: 531,067,840 bytes (506.47 MiB), SHA256 '
              '`ce172bdd5f50f6a65547c7b05268ea982674efb33795a2fbcd21f2d73e75ea1a`. '
              'Model: Qwen2.5-0.5B v3 Q8_0, local name `kanglish-gate-v3-q8:latest`. '
              'App llama.cpp revision: `5aeac37a35b44fde4bdffaec9159f2fcb253b622`. '
              '[Environment versions](../results/student_gate_a_20261019/environment.json). '
              '[Candidate configuration](../data/processed/student_gate_a_v1/config.json). '
              'Seeds are 42. No API keys are needed.', '',
              '**Reproduction commands**', '',
              'Run from the repository root using the existing pinned source corpus files and model/tokenizer assets. '
              'The public IndicXlit download uses no inference API. Commands below use new output folders so saved evidence is preserved. '
              'Ollama must already be serving locally. The baseline runner checks the GGUF hash and freezes configuration.', '',
              '```powershell',
              'python -B -m scripts.student_pipeline.download_assets',
              'python -B -u -m scripts.student_pipeline.indicxlit_runtime --out results/student_gate_a_repro/romanization_cache.jsonl --batch-size 96',
              'python -B -u -m scripts.student_pipeline.data freeze --run results/student_gate_a_repro --cache results/student_gate_a_repro/romanization_cache.jsonl --seed 42',
              'python -B -u -m scripts.student_pipeline.data prepare --run results/student_gate_a_repro --cache results/student_gate_a_repro/romanization_cache.jsonl --out data/processed/student_gate_a_repro --seed 42 --max-sentences 1500 --max-dictionary 1000',
              'Copy-Item -LiteralPath results/student_gate_a_20261019/protected_hashes_before.json -Destination results/student_gate_a_repro/protected_hashes_before.json',
              'python -B -u -m scripts.student_pipeline.verify --run results/student_gate_a_repro --data data/processed/student_gate_a_repro',
              'ollama create kanglish-gate-v3-q8 -f results/audit_20261019/Modelfile.v3',
              'python -B -u -m scripts.student_pipeline.evaluate --cases results/student_gate_a_repro/evaluation/benchmark.jsonl --out results/student_gate_a_repro/baseline_benchmark --max-seconds 1800',
              'python -B -u -m scripts.student_pipeline.evaluate --cases results/student_gate_a_repro/evaluation/in22.jsonl --out results/student_gate_a_repro/baseline_in22 --max-seconds 1800',
              'python -B -u -m scripts.student_pipeline.evaluate --cases results/student_gate_a_repro/evaluation/dictionary.jsonl --out results/student_gate_a_repro/baseline_dictionary --max-seconds 1800',
              'python -B -u -m scripts.student_pipeline.evaluate --cases results/student_gate_a_repro/evaluation/controls_and_failures.jsonl --out results/student_gate_a_repro/baseline_controls --max-seconds 1800',
              'python -B -m unittest tests.test_student_gate_pipeline -v',
              'python -B -m scripts.student_pipeline.data review-status --out data/processed/student_gate_a_v1',
              'python -B -m scripts.student_pipeline.report',
              '```', '',
              'The preparation commands refuse to overwrite an existing candidate export. Resume an incomplete evaluation by repeating '
              'the same command; changed inputs, prompt, model or evaluator code cause it to refuse. '
              'Source corpus acquisition is not rerun by these commands; their existing row provenance and checksums are retained. '
              'The report command reads this dated run, while the other example commands build the separate reproduction run.', '',
              '**Thirty lowest-chrF baseline outputs**', '',
              'Ranked by sentence chrF2, with ties sorted by case ID. This is a diagnostic ranking, not human severity judgment. '
              '[Full rows and metadata](../results/student_gate_a_20261019/baseline_worst_30.json).', '',
              '| ID | Input | Reference | Output | chrF2 |', '|---|---|---|---|---:|']
    for row in worst:
        lines.append('| ' + ' | '.join(cell(row.get(k, '')) for k in ('id', 'romanized_input', 'english', 'output')) + f' | {row["sentence_chrf2"]:.2f} |')
    lines += ['', '**Remaining gated work**', '',
              '| Stage | Status |', '|---|---|',
              '| Gate A | Kannada review and explicit user confirmation pending; resolve any verification errors first. |',
              '| Phase B | LoRA training and local/Colab/Kaggle training scripts not completed. No trained-model measurements. |',
              '| Gate B | Compare the approved-data student with this frozen baseline. Diagnose instead of extending training if benchmark and negative controls do not improve. |',
              '| Phase C | Merge and Q8_0/Q5_K_M/Q4_K_M conversion, accuracy/size/load measurements, S23 FE recommendation and stale Settings label fix pending. |', '',
              'No new accuracy gain, quantization-loss result or device recommendation can be claimed before those stages run.', '']
    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({'report': str(REPORT), 'baseline_complete': complete, 'verification': verification_state,
                      'predictions': len(rows), 'training_started': False}))


if __name__ == '__main__':
    main()
