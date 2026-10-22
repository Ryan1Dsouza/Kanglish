"""Independent post-export source/label, split, prompt and protected-data checks."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
from .contract import ROOT,sha,read_jsonl,write_json,glossary,glossary_matches,prompt,exact,assert_prompt_contract
from .checks import normalized,FuzzyIndex,row_issues
from .data import csv_rows,blacklist_index,reserve_extra,review_status

def run(args):
    rows={s:read_jsonl(args.data/f'{s}_candidates.jsonl') for s in ('train','validation')}
    allrows=rows['train']+rows['validation'];sources={}
    for path in ('data/trusted/conversational_bpcc.csv','data/trusted/lexicon_alar.csv'):
        sources.update({r['entry_id']:r for r in csv_rows(ROOT/path)})
    absence=json.loads((args.run/'absence_verification.json').read_text());safe=set(absence['candidate_strings'])
    heldout=[]
    for name in ('benchmark.jsonl','in22.jsonl','dictionary.jsonl','controls_and_failures.jsonl'):
        heldout.extend(read_jsonl(args.run/'evaluation'/name))
    heldout+=reserve_extra();blocked=blacklist_index(heldout);errors=[];entries=glossary();seen={}
    for i,row in enumerate(allrows):
        if row['category']=='abstention':
            if row['romanized_input'] not in safe or row['english']!='[unclear]':errors.append((row['id'],'bad_abstention'))
        else:
            original=sources.get(row['source_group'])
            if not original or row['english']!=original['english_meaning']:errors.append((row['id'],'reference_not_exact_source'))
            if original and (row['license']!=original['license'] or row['source']!=original['source']):errors.append((row['id'],'provenance_mismatch'))
        if row['source'] not in ('bpcc_h_daily_conversational','alar_kannada_english_dict','seeded_verified_absence'):
            errors.append((row['id'],'disallowed_source'))
        for field in ('romanized_input','original_kannada','english'):
            if row['category']=='abstention' and field=='english':continue
            found=blocked.matches(row.get(field,''))
            if found:errors.append((row['id'],'evaluation_near_duplicate',field,found[0]))
        issues=row_issues(row['romanized_input'],row['english'],row['category'],row.get('names',()),row.get('latin_spans',()),row.get('parent_input'))
        if issues:errors.append((row['id'],'row_rule',issues))
        hints=[] if exact(row['romanized_input'],entries) is not None else glossary_matches(row['romanized_input'],entries)
        if row['prompt']!=prompt(row['romanized_input'],hints):errors.append((row['id'],'prompt_mismatch'))
        key=normalized(row['romanized_input'])
        if key in seen:errors.append((row['id'],'duplicate_normalized_input',seen[key]))
        seen[key]=row['id']
        if i%1000==0:print(json.dumps({'verified_rows':i,'total':len(allrows),'errors':len(errors)}),flush=True)
    overlap={r['source_group'] for r in rows['train']}&{r['source_group'] for r in rows['validation']}
    split_overlap={r['split_group'] for r in rows['train']}&{r['split_group'] for r in rows['validation']}
    if overlap or split_overlap:errors.append(('split','source_overlap',sorted(overlap)))
    # Check spelling variants too, not just their base parents.
    train_index=FuzzyIndex(.88)
    for row in rows['train']:train_index.add(row['romanized_input'],row['id'])
    cross=[]
    for row in rows['validation']:
        found=train_index.matches(row['romanized_input'])
        if found:cross.append({'validation_id':row['id'],'match':found[0]})
    if cross:errors.append(('split','fuzzy_variant_overlap',len(cross)))
    before=json.loads((args.run/'protected_hashes_before.json').read_text())
    changed=[k for k,v in before.items() if sha(k)!=v]
    protected_data_changes=[k for k in changed if k.startswith('data/')]
    if protected_data_changes:errors.append(('protected_data_changed',protected_data_changes))
    result={'complete':True,'passed':not errors,'rows':len(allrows),'errors':errors,'cross_split_variant_matches':cross,
        'source_group_overlap':len(overlap),'split_group_overlap':len(split_overlap),
        'protected_evaluation_and_glossary_data_unchanged':not protected_data_changes,
        'concurrent_app_changes_since_start':changed,'current_prompt_sha256':assert_prompt_contract(),
        'review_status':review_status(args.data),'file_sha256':{p.name:sha(p) for p in args.data.iterdir() if p.is_file()}}
    write_json(args.run/'dataset_verification.json',result)
    print(json.dumps({'passed':result['passed'],'rows':len(allrows),'errors':len(errors),'cross_split_variant_matches':len(cross)}),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,default=ROOT/'data/processed/student_gate_a_v1')
    p.add_argument('--run',type=Path,default=ROOT/'results/student_gate_a_20261019');run(p.parse_args())

if __name__=='__main__':main()
