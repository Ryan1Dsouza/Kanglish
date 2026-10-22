"""Resumable, local-only evaluation with a frozen app prompt and frozen references."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from .contract import ROOT, PROMPT_PATH, GLOSSARY_PATH, OPTIONS, assert_prompt_contract, sha, read_jsonl, write_json, glossary, exact, glossary_matches, prompt, clean, local_request
from .checks import metric_summary, chrf_score, chrf_stats

def run(args):
    args.out.mkdir(parents=True, exist_ok=True)
    paths = {"cases":args.cases, "prompt":PROMPT_PATH, "glossary":GLOSSARY_PATH,
             "contract":Path(__file__).with_name("contract.py"), "evaluator":Path(__file__)}
    contract_hash = assert_prompt_contract()
    model_name = args.model if ":" in args.model else args.model+":latest"
    show = local_request("/api/show", {"model":model_name})
    model_sha = sha(args.gguf)
    if model_sha not in show.get("modelfile", ""): raise ValueError("Ollama model does not match supplied GGUF")
    config = {"model":model_name,"gguf_sha256":model_sha,"options":OPTIONS,
        "input_sha256":{k:sha(v) for k,v in paths.items()},"history":[],"learned_glossary":[],
        "spend_cap":0,"external_model_calls":0,"ollama_version":local_request("/api/version"),
        "prompt_contract_sha256":contract_hash,"metrics":"chrF2 n=6 beta=2 case-sensitive no whitespace; dictionary exact ignores case/outer whitespace; names and negation are rule-based diagnostics",
        "runtime_limitation":"Desktop Ollama, not Android runtime or phone latency; matching prompt/glossary and configured sampler."}
    config_path=args.out/"config.json"
    if config_path.exists():
        old=json.loads(config_path.read_text())
        if old != config: raise ValueError("Cannot resume with changed inputs, model, config, or code")
    else: write_json(config_path,config)
    prediction_path=args.out/"predictions.jsonl"
    existing=read_jsonl(prediction_path) if prediction_path.exists() else []
    cases=read_jsonl(args.cases)
    if [r["id"] for r in existing] != [r["id"] for r in cases[:len(existing)]]:
        raise ValueError("Prediction file is not a prefix of this frozen evaluation suite")
    from tokenizers import Tokenizer
    tokenizer=Tokenizer.from_file(str(args.tokenizer))
    entries=glossary()
    started=time.monotonic(); completed=list(existing)
    with prediction_path.open("a",encoding="utf-8",newline="\n") as stream:
        for case in cases[len(existing):]:
            if time.monotonic()-started > args.max_seconds: break
            row=dict(case); start=time.perf_counter(); source=row["romanized_input"].strip()
            result=exact(source,entries); matches=[]; message=""
            if result is not None:
                row.update(route="exact_glossary", output=result,status="ok")
            else:
                matches=glossary_matches(source,entries); message=prompt(source,matches)
                row.update(route="student_model",prompt=message,glossary_matches=matches)
                token_count=len(tokenizer.encode(message,add_special_tokens=True).ids)
                row["prompt_tokens_precheck"]=token_count
                if not source or len(source)>4000 or token_count+192>1024:
                    row.update(output="",status="app_input_or_context_limit")
                else:
                    try:
                        response=local_request("/api/generate",dict(model=model_name,prompt=message,raw=True,stream=False,options=OPTIONS,keep_alive="30m"))
                        raw=response.get("response",""); output=clean(raw)
                        status="ok" if response.get("done") and response.get("done_reason")!="length" and output else "generation_failure"
                        row.update(output=output,raw_output=raw,status=status,telemetry={k:response.get(k) for k in ("done_reason","prompt_eval_count","eval_count","total_duration","load_duration","eval_duration")})
                    except Exception as exc:
                        row.update(output="",status="request_error",error=f"{type(exc).__name__}: {exc}")
            row["elapsed_ms"]=round((time.perf_counter()-start)*1000,2)
            row["model"]=model_name; row["human_assessment"]=None
            stream.write(json.dumps(row,ensure_ascii=False)+"\n"); stream.flush(); completed.append(row)
            if len(completed)%25==0 or len(completed)==len(cases):
                print(json.dumps({"completed":len(completed),"total":len(cases),"last_id":row["id"],"last_status":row["status"]}),flush=True)
    groups=defaultdict(list)
    for row in completed: groups[row["suite"]].append(row)
    summary={"complete":len(completed)==len(cases),"processed":len(completed),"expected":len(cases),
        "finished_utc":datetime.now(timezone.utc).isoformat(),"overall":metric_summary(completed),
        "by_suite":{k:metric_summary(v) for k,v in groups.items()},"predictions_sha256":sha(prediction_path),
        "inputs_unchanged":all(sha(v)==config["input_sha256"][k] for k,v in paths.items())}
    write_json(args.out/"metrics.json",summary)
    scored=[dict(r,sentence_chrf2=chrf_score(chrf_stats(r.get("output",""),r["english"]))) for r in completed if r.get("english") and r["category"]!="abstention"]
    write_json(args.out/"worst_30.json",sorted(scored,key=lambda r:r["sentence_chrf2"])[:30])
    print(json.dumps(summary),flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases",type=Path,required=True);parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--model",default="kanglish-gate-v3-q8")
    parser.add_argument("--gguf",type=Path,default=ROOT/"mobile/android/app/build/outputs/apk/debug/kanglish_qwen_0.5b_v3.gguf")
    parser.add_argument("--tokenizer",type=Path,default=ROOT/"models/kanglish_qwen_0.5b_v3_merged/tokenizer.json")
    parser.add_argument("--max-seconds",type=float,default=1800)
    run(parser.parse_args())

if __name__=="__main__": main()
