"""Source-backed Romanized candidates and frozen evaluation; stops at Gate A.

No teacher generation, student training, private chats, or app changes are made.
External translation targets are never synthesized or rewritten. [unclear] is
the sole synthetic target, explicitly authorized for verified-absent controls.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import random
import re
import unicodedata
import zipfile

from .contract import ROOT, sha, read_jsonl, write_json, write_jsonl, glossary, exact, glossary_matches, prompt, assert_prompt_contract
from .checks import normalized, compact, family_key, rank, FuzzyIndex, row_issues, names_in_reference, name_preserved, NEG_ROM, TIME_WORDS, STOP_NAMES
from scripts.trusted_pipeline.quality import balanced_lexicon_sample, english_target_issue

WORD=re.compile(r"[\u0c80-\u0ce5\u0cf0-\u0cff]+")
LATIN=re.compile(r"[A-Za-z][A-Za-z0-9_+.'-]*")
RUN=ROOT/'results/student_gate_a_20261019'
SOURCE_FIELDS=('entry_id','source','license','attribution','source_url','source_checksum')

def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def native_normalize(text):return unicodedata.normalize('NFC',text).replace('\u200c','').replace('\u200d','')

def load_cache(path):return {r['native']:r for r in read_jsonl(path)}

def freeze_jsonl(path,rows):
    if path.exists():
        if read_jsonl(path)!=rows:raise ValueError('Frozen evaluation file differs: '+str(path))
    else:write_jsonl(path,rows)

def romanize(text,cache):return WORD.sub(lambda m:cache[m.group()]['romanized'],native_normalize(text))

def source_candidate(row,category,cache=None):
    source=row['original_kanglish'] if category=='dictionary' else romanize(row['kannada_script'],cache)
    return {'id':row['entry_id'],'source_group':row['entry_id'],'category':category,
        'romanized_input':source,'english':row['english_meaning'],'original_kannada':row['kannada_script'],
        'source':row['source'],'license':row['license'],'provenance':{k:row.get(k,'') for k in SOURCE_FIELDS},
        'reference_authority':'human-authored_dictionary' if category=='dictionary' else 'human-translated_BPCC-H',
        'review_status':'pending_gate_a','source_review_status':row.get('review_status','raw'),
        'variant':'base','transliteration_method':'Alar_source_romanization' if category=='dictionary' else 'IndicXlit_v1_indic_en_pytorch_greedy'}

def blacklist_index(cases,short_edits=True):
    index=FuzzyIndex(.88,short_edits=short_edits)
    for row in cases:
        for field in ('romanized_input','original_kannada','english'):
            if row.get(field):index.add(row[field],{'id':row['id'],'field':field,'suite':row.get('suite','reserved')})
    return index

def known_failure_rows():
    audit=json.loads((ROOT/'results/audit_20261019/verified_sources/dataset_audit.json').read_text(encoding='utf-8'))
    cases=audit['probe_cases'];rows=[]
    for i,source in enumerate(('marmarisu','naanu baralla ivattu','naale college ge barthira','zqxvpl')):
        matched=next((r for r in cases if compact(r['input'])==compact(source)),{})
        reference=matched.get('reference','')
        if isinstance(reference,dict):reference=reference.get('text','')
        rows.append({'id':f'KNOWN-{i+1:02d}','suite':'known_failures','category':'abstention' if source=='zqxvpl' else ('dictionary' if source=='marmarisu' else 'conversation'),
            'romanized_input':source,'english':'[unclear]' if source=='zqxvpl' else reference,
            'reference_status':matched.get('reference_status','diagnostic; inspect source audit'),
            'source':'prior_audit_and_user_fixed_failures','license':'diagnostic_only','source_case':matched,'names':[]})
    return rows

def reserve_extra():
    reserved=[]
    test=csv_rows(ROOT/'data/test.csv')
    for i,row in enumerate(test):
        fields=list(row)
        source=row.get('kanglish',row.get('input',row.get('kanglish_input',row[fields[0]])))
        target=row.get('english',row.get('expected',row.get('expected_translation',row[fields[1]] if len(fields)>1 else '')))
        reserved.append({'id':f'OWNER-{i}','romanized_input':source,'english':target})
    for path in (ROOT/'data/corpus/leakage_blacklist.txt',):
        if path.exists():
            reserved.extend({'id':f'BLACKLIST-{i}','romanized_input':line} for i,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines()) if line.strip())
    return reserved

def gibberish_pool(seed=42):
    rng=random.Random(seed);pool={'zqxvpl'}
    while len(pool)<401:
        # Diverse consonant-heavy strings; absence is checked, and human review is still required.
        size=rng.randint(6,13)
        alphabet='bcdfghjklmnpqrstvwxyz'
        chars=[rng.choice(alphabet) for _ in range(size)]
        if len(pool)%3==0:chars[rng.randrange(1,size-1)]=rng.choice('aeiou')
        pool.add(''.join(chars))
    return sorted(pool,key=lambda s:rank(s,seed))

def verify_absence(pool,lexicon,entries):
    keys={family_key(w):w for w in pool};hits=defaultdict(list);counts=Counter();native_counts=Counter()
    def check(word,where):
        # Corpus Romanizations are Latin; punctuation/space folding matches the control normalization.
        key=re.sub(r'[^a-z]','',word.casefold())
        key=re.sub(r'([a-z])\1+',r'\1',key).replace('ph','f')
        if key in keys:hits[keys[key]].append(where)
    for row in lexicon:check(row['original_kanglish'],'Alar');counts['Alar']+=1
    for word,_ in entries:check(word,'app_glossary');counts['app_glossary']+=1
    archive=ROOT/'data/raw/aksharantar/kan.zip'
    with zipfile.ZipFile(archive) as z:
        for member in ('kan_train.json','kan_valid.json','kan_test.json'):
            with io.TextIOWrapper(z.open(member),encoding='utf-8') as stream:
                for line in stream:
                    if not line.strip():continue
                    row=json.loads(line);check(row.get('english word',''),member);counts[member]+=1
                    if member=='kan_train.json':native_counts[row.get('native word','')]+=1
            print(json.dumps({'absence_scan':member,'rows':counts[member]}),flush=True)
    return {'checked_pool':len(pool),'matches':dict(hits),'scanned':dict(counts),
        'aksharantar_sha256':sha(archive),'lexicon_sha256':sha(ROOT/'data/trusted/lexicon_alar.csv'),
        'glossary_sha256':sha(ROOT/'mobile/android/app/src/main/assets/glossary.json'),
        'interpretation':'Absent from these normalized headword/word inventories, not proof of absence from all Kannada or names.'},native_counts

def freeze(args):
    import pyarrow.parquet as pq
    out=args.run/'evaluation';out.mkdir(parents=True,exist_ok=True)
    cache=load_cache(args.cache)
    benchmark=[]
    for row in csv_rows(ROOT/'data/benchmark_test_v1_draft.csv'):
        benchmark.append({'id':row['id'],'suite':'benchmark_draft','category':row['category'],
            'romanized_input':row['kanglish_input'],'english':row['primary_reference'],
            'acceptable_alternatives':row['acceptable_alternatives'],'review_status':row['review_status'],
            'source':'data/benchmark_test_v1_draft.csv','license':row['license'],'names':names_in_reference(row['primary_reference'])})
    if not (out/'benchmark.jsonl').exists():write_jsonl(out/'benchmark.jsonl',benchmark)
    elif read_jsonl(out/'benchmark.jsonl')!=benchmark:raise ValueError('Frozen benchmark differs')
    native_path=ROOT/'data/raw/in22_conv/in22_conv_mteb_default_test.parquet'
    table=pq.read_table(native_path,columns=['kan_Knda','eng_Latn']);in22=[]
    for i,(native,english) in enumerate(zip(table['kan_Knda'].to_pylist(),table['eng_Latn'].to_pylist())):
        tokens=WORD.findall(native_normalize(native))
        in22.append({'id':f'IN22-{i:04d}','suite':'in22_conv_romanized','category':'conversation',
            'romanized_input':romanize(native,cache),'original_kannada':native,'english':english,
            'source':'mteb/IN22-Conv:test','license':'CC-BY-4.0','source_group':f'IN22-row-{i}',
            'reference_status':'human_translated_corpus; machine_romanized_input','names':names_in_reference(english),
            'transliteration_issues':[w for w in tokens if cache[w]['input_unknown_characters'] or not cache[w]['completed']]})
    freeze_jsonl(out/'in22.jsonl',in22)
    # Start full IN22 inference as soon as this file exists; other preparation is independent.
    print(json.dumps({'in22_ready':str(out/'in22.jsonl'),'rows':len(in22)}),flush=True)
    lex=csv_rows(ROOT/'data/trusted/lexicon_alar.csv');entries=glossary();known=known_failure_rows()
    # Frozen evaluation selection v1 predates the stricter short-typo training guard.
    # Keep its seeded cohort reproducible; preparation uses short_edits=True.
    protected=blacklist_index(benchmark+in22+known+reserve_extra(),short_edits=False)
    chosen=[]
    for row in balanced_lexicon_sample(lex,limit=1800,seed=args.seed):
        candidate=source_candidate(row,'dictionary')
        if any(protected.matches(candidate.get(field,'')) for field in ('romanized_input','original_kannada','english')):continue
        if exact(candidate['romanized_input'],entries) is not None:continue
        chosen.append(candidate)
    chosen.sort(key=lambda r:rank(r['id'],args.seed+1))
    dictionary=chosen[:100]
    for row in dictionary:row.update(suite='dictionary_holdout',names=[],review_status='source_dictionary_reference_unreviewed_sample')
    freeze_jsonl(out/'dictionary.jsonl',dictionary)
    freeze_jsonl(out/'dictionary_pool.jsonl',chosen[100:])
    pool=gibberish_pool(args.seed);absence,freq=verify_absence(pool,lex,entries)
    if 'zqxvpl' in absence['matches']:raise ValueError('Known negative control exists in a source inventory; review it')
    safe=[w for w in pool if w not in absence['matches'] and w!='zqxvpl']
    controls=[]
    control_index=blacklist_index(benchmark+in22+known+dictionary,short_edits=False)
    for word in safe:
        if control_index.matches(word):continue
        controls.append({'id':f'NEG-{len(controls)+1:03d}','suite':'negative_controls','category':'abstention',
            'romanized_input':word,'english':'[unclear]','source':'seeded_absence_checked_controls','license':'project_generated_diagnostic',
            'reference_status':'user_authorized_fixed_abstention_target','names':[]})
        control_index.add(word,{'id':controls[-1]['id']})
        if len(controls)==50:break
    excluded={r['romanized_input'] for r in controls}|{'zqxvpl'}
    train_controls=[w for w in safe if w not in excluded and not control_index.matches(w)][:250]
    absence.update({'evaluation_controls':len(controls)+1,'candidate_controls':len(train_controls),'candidate_strings':train_controls})
    write_json(args.run/'absence_verification.json',absence)
    for row in dictionary:row['aksharantar_native_frequency']=freq[row['original_kannada']]
    write_json(args.run/'dictionary_frequency.json',{r['id']:freq[r['original_kannada']] for r in chosen})
    freeze_jsonl(out/'controls_and_failures.jsonl',known+controls)
    write_json(out/'manifest.json',{'seed':args.seed,'benchmark':len(benchmark),'in22':len(in22),'dictionary':len(dictionary),
        'negative_and_failure_probes':len(known)+len(controls),'romanization_cache_sha256':sha(args.cache),
        'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'data/benchmark_test_v1_draft.csv',native_path,ROOT/'data/trusted/lexicon_alar.csv']},
        'status':'frozen_evaluation_only_never_training'})

def spelling_variants(row,seed):
    text=row['romanized_input'];original_latin={w.casefold() for w in LATIN.findall(row['original_kannada'])}
    protected=set(TIME_WORDS)|set(row.get('names',[]))|original_latin|{'bidi'}
    pieces=list(re.finditer(r'[A-Za-z]+',text));possibilities=[]
    def add(match,replacement,kind):
        if replacement!=match.group():possibilities.append((text[:match.start()]+replacement+text[match.end():],kind))
    for m in pieces:
        word=m.group();lower=word.lower()
        if lower in protected or NEG_ROM.fullmatch(lower) or len(word)<3:continue
        for before,after in [('aa','a'),('ee','i'),('ii','i'),('oo','u'),('ph','f')]:
            if before in lower:add(m,re.sub(before,after,word,count=1,flags=re.I),before+'/'+after)
        vowels=[i for i,c in enumerate(lower) if c in 'aeiou' and 0<i<len(word)-1]
        if vowels:
            i=vowels[0];add(m,word[:i]+word[i]+word[i:], 'vowel_doubling')
            if len(word)>=6:add(m,word[:i]+word[i+1:],'dropped_internal_vowel')
        if lower.endswith('ge') and len(word)>4:
            add(m,word[:-2]+'ke','ge/ke');add(m,word[:-2]+' ge','suffix_spacing')
        elif lower.endswith('ke') and len(word)>4:add(m,word[:-2]+'ge','ke/ge')
    # Joining two native-origin words supplies realistic spacing noise; Latin spans stay intact.
    for left,right in zip(pieces,pieces[1:]):
        if text[left.end():right.start()]==' ' and left.group().lower() not in protected and right.group().lower() not in protected and not NEG_ROM.fullmatch(left.group()) and not NEG_ROM.fullmatch(right.group()):
            possibilities.append((text[:left.end()]+text[right.start():],'joined_spacing'))
    unique={}
    for value,kind in possibilities:
        key=normalized(value)
        if key!=normalized(text):unique.setdefault(key,(value,kind))
    ranked=sorted(unique.values(),key=lambda p:rank(row['id']+'|'+p[0],seed))
    count=3+int(rank(row['id'],seed)[0],16)%3
    return ranked[:count]

class Groups:
    def __init__(self,n):self.parent=list(range(n))
    def find(self,i):
        while self.parent[i]!=i:self.parent[i]=self.parent[self.parent[i]];i=self.parent[i]
        return i
    def join(self,a,b):self.parent[self.find(b)]=self.find(a)

def prepare(args):
    assert_prompt_contract();out=args.out
    if out.exists():raise ValueError('Refusing to overwrite a candidate export')
    out.mkdir(parents=True)
    cache=load_cache(args.cache);ev=args.run/'evaluation';entries=glossary();review=[];counts=Counter()
    heldout=[]
    for file in ('benchmark.jsonl','in22.jsonl','dictionary.jsonl','controls_and_failures.jsonl'):heldout.extend(read_jsonl(ev/file))
    heldout+=reserve_extra();blocked=blacklist_index(heldout)
    all_bpcc=csv_rows(ROOT/'data/trusted/conversational_bpcc.csv')
    quality_ids=set()
    for file in ('train_candidates.jsonl','validation_candidates.jsonl'):
        quality_ids.update(r['group_id'] for r in read_jsonl(ROOT/'data/processed/quality_v1'/file))
    # Capitalized proper-name evidence comes only from permitted human source references.
    name_vocab={'george','trump','modi'}
    for row in all_bpcc:name_vocab.update(names_in_reference(row['english_meaning']))
    name_vocab-=STOP_NAMES
    name_vocab.update({'george','trump','modi'})
    def reject(row,reasons,details=None):
        for reason in reasons:counts['rejected:'+reason.split(':')[0]]+=1
        review.append({'id':row.get('id',''),'source':row.get('source',''),'license':row.get('license',''),
            'romanized_input':row.get('romanized_input',''),'english':row.get('english',''),
            'original_kannada':row.get('original_kannada',''),'reason':'; '.join(reasons),
            'details':json.dumps(details or {},ensure_ascii=False),'ok':'','wrong':'','notes':''})
    bases=[]
    for i,raw in enumerate(all_bpcc):
        row=source_candidate(raw,'conversation',cache);row['also_in_quality_v1']=row['id'] in quality_ids
        row['names']=names_in_reference(row['english'],name_vocab);row['latin_spans']=LATIN.findall(raw['kannada_script'])
        bad_tokens=[w for w in WORD.findall(native_normalize(row['original_kannada'])) if cache[w]['input_unknown_characters'] or not cache[w]['completed'] or not cache[w]['romanized']]
        reasons=row_issues(row['romanized_input'],row['english'],'conversation',row['names'],row['latin_spans'])
        if bad_tokens:reasons.append('transliterator_unknown_or_incomplete')
        if len(row['english'])>240 or len(row['romanized_input'])>400:reasons.append('long_sentence_review')
        if reasons:reject(row,reasons,{'transliteration_tokens':bad_tokens});continue
        matches=[]
        for field in ('romanized_input','original_kannada','english'):
            found=blocked.matches(row[field])
            if found:matches.append({'field':field,**found[0]})
        if matches:reject(row,['evaluation_near_duplicate'],matches);continue
        variants=spelling_variants(row,args.seed)
        if len(variants)<3:reject(row,['fewer_than_three_safe_spelling_variants']);continue
        row['spelling_variants']=variants;bases.append(row)
        if i%1000==0:print(json.dumps({'checked_bpcc':i,'accepted_bases':len(bases)}),flush=True)
    counts['source_bpcc_rows']=len(all_bpcc)
    bases.sort(key=lambda r:rank(r['id'],args.seed));counts['eligible_conversation_groups']=len(bases)
    if len(bases)>args.max_sentences:counts['not_selected:conversation_cap']=len(bases)-args.max_sentences
    bases=bases[:args.max_sentences]
    dictionary=read_jsonl(ev/'dictionary_pool.jsonl')
    freq=json.loads((args.run/'dictionary_frequency.json').read_text())
    buckets=defaultdict(list)
    for row in dictionary:
        reasons=row_issues(row['romanized_input'],row['english'],'dictionary')
        if reasons:reject(row,reasons);continue
        if any(blocked.matches(row.get(field,'')) for field in ('romanized_input','original_kannada','english')):
            reject(row,['evaluation_near_duplicate']);continue
        row['also_in_quality_v1']=row['id'] in quality_ids
        row['aksharantar_native_frequency']=freq.get(row['id'],0)
        row['rare_word_proxy']=row['aksharantar_native_frequency']<=1
        buckets[row['romanized_input'][0].lower()].append(row)
    for bucket in buckets.values():bucket.sort(key=lambda r:rank(r['id'],args.seed))
    selected=[];offset=0
    while len(selected)<args.max_dictionary:
        added=False
        for letter in sorted(buckets):
            if offset<len(buckets[letter]):selected.append(buckets[letter][offset]);added=True
            if len(selected)>=args.max_dictionary:break
        if not added:break
        offset+=1
    bases+=selected
    absence=json.loads((args.run/'absence_verification.json').read_text())
    absence_hash=sha(args.run/'absence_verification.json')
    for i,word in enumerate(absence['candidate_strings']):
        if blocked.matches(word):continue
        bases.append({'id':f'ABSTAIN-{i:03d}','source_group':f'ABSTAIN-{i:03d}','category':'abstention',
            'romanized_input':word,'english':'[unclear]','original_kannada':'','source':'seeded_verified_absence',
            'license':'project_generated_candidate','reference_authority':'user_authorized_fixed_abstention',
            'review_status':'pending_gate_a','variant':'base','absence_verification_sha256':absence_hash})
    # Keep source siblings, English-answer duplicates and fuzzy input families in one split.
    groups=Groups(len(bases));index=FuzzyIndex(.88);first_source={};exact_keys={}
    for i,row in enumerate(bases):
        if row['source_group'] in first_source:groups.join(i,first_source[row['source_group']])
        first_source[row['source_group']]=i
        for field in ('romanized_input','original_kannada','english'):
            if row['category']=='abstention' and field=='english':continue
            value=row.get(field,'')
            if not value:continue
            key=field+':'+family_key(value)
            if key in exact_keys:groups.join(i,exact_keys[key])
            exact_keys[key]=i
            for found in index.matches(value,all_matches=True):groups.join(i,found['match'])
            index.add(value,i)
        if i%500==0:print(json.dumps({'grouped_bases':i,'total':len(bases)}),flush=True)
    members=defaultdict(list)
    for i,row in enumerate(bases):members[groups.find(i)].append(row['id'])
    group_ids={root:rank('|'.join(sorted(ids)),args.seed) for root,ids in members.items()}
    train=[];validation=[];seen={};excluded_groups=set();rows=[]
    for i,base in enumerate(bases):
        group_id=group_ids[groups.find(i)]
        split='validation' if int(group_id[:8],16)%10==0 else 'train'
        variants=base.pop('spelling_variants',[])
        for variant_index,(text,kind) in enumerate([(base['romanized_input'],'base')]+variants):
            row=dict(base,romanized_input=text,variant=kind,id=base['id']+f':{variant_index}',split_group=group_id,split=split)
            row['parent_input']=base['romanized_input']
            reasons=row_issues(text,row['english'],row['category'],row.get('names',()),row.get('latin_spans',()),base['romanized_input'])
            if row['category']=='abstention' and row['english']!='[unclear]':reasons.append('invalid_abstention')
            match=blocked.matches(text)
            if match:reasons.append('evaluation_near_duplicate')
            if reasons:reject(row,reasons,match);excluded_groups.add(group_id);continue
            key=normalized(text)
            if key in seen:
                if seen[key]['english']!=row['english']:
                    excluded_groups.update((group_id,seen[key]['split_group']));reject(row,['conflicting_reference'])
                else:counts['deduplicated:exact_input_answer']+=1
                continue
            seen[key]=row;rows.append(row)
    # A bad spelling variant excludes its complete connected source group.
    from tokenizers import Tokenizer
    tokenizer=Tokenizer.from_file(str(ROOT/'models/kanglish_qwen_0.5b_v3_merged/tokenizer.json'))
    for row in rows:
        if row['split_group'] in excluded_groups:
            reject(row,['excluded_source_group']);continue
        exact_result=exact(row['romanized_input'],entries)
        hints=[] if exact_result is not None else glossary_matches(row['romanized_input'],entries)
        row['prompt']=prompt(row['romanized_input'],hints)
        row['glossary_hints']=hints;row['would_use_exact_glossary']=exact_result is not None
        if len(tokenizer.encode(row['prompt']).ids)+192>1024:reject(row,['app_context_limit']);continue
        (train if row['split']=='train' else validation).append(row)
    # Teacher outputs remain solely in the CSV review queue, never candidate training JSONL.
    teacher_path=ROOT/'data/processed/gemini_teacher_dataset.jsonl'
    for i,raw in enumerate(read_jsonl(teacher_path)):
        messages=raw.get('messages',[])
        inp=next((m.get('content','') for m in messages if m.get('role')=='user'),raw.get('kanglish',raw.get('input','')))
        target=next((m.get('content','') for m in messages if m.get('role')=='assistant'),raw.get('english',raw.get('output','')))
        reject({'id':f'TEACHER-REVIEW-{i}','source':'historical_llm_teacher_output','romanized_input':inp,'english':target},['teacher_output_requires_kannada_review'],raw)
    train.sort(key=lambda r:rank(r['id'],args.seed));validation.sort(key=lambda r:rank(r['id'],args.seed))
    semantic=[r for r in train if r['category']!='abstention'];abstention=[r for r in train if r['category']=='abstention']
    if len(semantic)<200 or len(abstention)<50:raise ValueError('Insufficient eligible rows for the requested review sample; do not pad')
    rng=random.Random(args.seed);sample=rng.sample(semantic,200)+rng.sample(abstention,50)
    fields=['id','category','romanized_input','english','original_kannada','source','source_group','license','variant','ok','wrong','notes']
    with (out/'review_sample.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for row in sample:writer.writerow(dict(row,ok='',wrong='',notes=''))
    review_fields=['id','source','license','romanized_input','english','original_kannada','reason','details','ok','wrong','notes']
    with (out/'review_queue.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=review_fields);writer.writeheader();writer.writerows(review)
    write_jsonl(out/'train_candidates.jsonl',train);write_jsonl(out/'validation_candidates.jsonl',validation)
    group_overlap={r['split_group'] for r in train}&{r['split_group'] for r in validation}
    if group_overlap:raise AssertionError('Source groups leaked between splits')
    config={'seed':args.seed,'max_sentence_groups':args.max_sentences,'max_dictionary_groups':args.max_dictionary,
        'variants_per_sentence':'3 to 5 plus unchanged base; keep references identical; protect names/time/negation/Latin spans',
        'fuzzy_threshold':.88,'fuzzy_metric':'difflib.SequenceMatcher full compact strings + folded spelling families + edit distance <=1 for compact strings 4..10 characters',
        'split':'connected components of source IDs, fuzzy native/Romanized inputs and English answer families; stable hash 90/10',
        'abstention_target':'[unclear]','mixed_partial_abstention_rows':0,
        'mixed_partial_abstention_reason':'No Kannada-speaker-confirmed mixed-unknown references available',
        'allowed_reference_sources':['BPCC-H human translations','Alar authored dictionary senses pending review','user-authorized fixed [unclear]'],
        'teacher_outputs_in_training':0,'private_chats_used':0,'external_model_api_calls':0,'spend_cap':0,
        'prompt_sha256':assert_prompt_contract(),'romanization_cache_sha256':sha(args.cache),
        'romanization_model':'AI4Bharat/IndicXlit indic-en v1.0; local pretrained PyTorch inference, greedy',
        'student_model':'Qwen2.5-0.5B v3 Q8_0 baseline only; no training started'}
    write_json(out/'config.json',config)
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'gate':'A','status':'WAITING_FOR_HUMAN_REVIEW_AND_USER_CONFIRMATION',
        'training_allowed':False,'training_started':False,'train_rows':len(train),'validation_rows':len(validation),
        'train_source_groups':len({r['source_group'] for r in train}),'validation_source_groups':len({r['source_group'] for r in validation}),
        'connected_split_groups':len(members),'cross_split_source_group_overlap':len(group_overlap),
        'review_sample':{'semantic':200,'abstention':50,'total':250,'seed':args.seed},'review_queue_rows':len(review),
        'review_queue_by_source':dict(Counter(r['source'] for r in review)),
        'counts':dict(counts),'train_by_source':dict(Counter(r['source'] for r in train)),
        'train_by_category':dict(Counter(r['category'] for r in train)),'validation_by_category':dict(Counter(r['category'] for r in validation)),
        'dictionary_initials':dict(Counter(r['romanized_input'][0].lower() for r in train+validation if r['category']=='dictionary')),
        'real_rare_dictionary_rows':sum(r.get('rare_word_proxy',False) for r in train+validation),
        'quality_v1_source_rows_reused':len({r['source_group'] for r in train+validation if r.get('also_in_quality_v1')}),
        'output_sha256':{p.name:sha(p) for p in out.iterdir() if p.is_file()},
        'limitations':['Automatic checks are conservative heuristics, not Kannada-speaker validation.','Machine spelling variants may be unnatural or change meaning; Gate A is mandatory.','Inventory absence does not prove a string is not a rare word or name.','Mixed unknown-word sentences were not fabricated.']}
    write_json(out/'manifest.json',manifest)
    print(json.dumps(manifest,ensure_ascii=True),flush=True)

def review_status(folder):
    rows=csv_rows(Path(folder)/'review_sample.csv')
    approved={};groups=defaultdict(lambda:Counter())
    candidates={r['id']:r for r in read_jsonl(Path(folder)/'train_candidates.jsonl')}
    for row in rows:
        original=candidates.get(row['id'])
        if not original or row['romanized_input']!=original['romanized_input'] or row['english']!=original['english']:
            raise ValueError('Review source text or reference changed; rebuild reviewed data explicitly')
        group='abstention' if row['category']=='abstention' else 'semantic'
        ok=row['ok'].strip().lower() in ('1','yes','true','x','ok')
        wrong=row['wrong'].strip().lower() in ('1','yes','true','x','wrong')
        groups[group]['total']+=1
        if ok==wrong:groups[group]['unresolved']+=1
        elif wrong:groups[group]['wrong']+=1
        else:groups[group]['ok']+=1
    for group,counts in groups.items():
        approved[group]=counts['total']==(50 if group=='abstention' else 200) and not counts['unresolved'] and counts['wrong']/counts['total']<=.10
    return {'review_counts':{g:dict(c) for g,c in groups.items()},'sample_threshold_passed':len(approved)==2 and all(approved.values()),
        'user_confirmation_received':False,'training_allowed':False,'next_action':'Explicit user confirmation of Gate A is required even if sample checks pass.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['freeze','prepare','review-status'])
    parser.add_argument('--run',type=Path,default=RUN);parser.add_argument('--cache',type=Path,default=RUN/'romanization_cache.jsonl')
    parser.add_argument('--out',type=Path,default=ROOT/'data/processed/student_gate_a_v1')
    parser.add_argument('--seed',type=int,default=42);parser.add_argument('--max-sentences',type=int,default=1500);parser.add_argument('--max-dictionary',type=int,default=1000)
    args=parser.parse_args()
    if args.command=='review-status':print(json.dumps(review_status(args.out),indent=2))
    else:(freeze if args.command=='freeze' else prepare)(args)

if __name__=='__main__':main()
