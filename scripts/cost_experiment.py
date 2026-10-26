"""Compare attendance extraction cost and accuracy for batching/cache variants."""
from __future__ import annotations
import argparse, json, statistics, sys, time, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fairdraw import llm_client, config
from fairdraw.usage_log import get_run_totals
from fairdraw.attendance_agent import extract_attendance
from fairdraw.chat_splitter import parse_chat
from fairdraw.data_io import load_roster

ROOT = Path(__file__).resolve().parents[1]

def expected():
    raw=json.loads((ROOT/'data/labeled/expected_claims.json').read_text())['claims']
    return {(int(i), (x['subject'],x['status'])) for i,items in raw.items() for x in items}

def score(claims, target):
    got={(x.message_index,(x.subject_text,x.status)) for x in claims}; tp=len(got&target)
    p=tp/len(got) if got else 1; r=tp/len(target) if target else 1
    return {'precision':p,'recall':r,'f1':2*p*r/(p+r) if p+r else 0}

def run_variant(name, messages, roster, batch_size, cache_mode, repeats=1):
    original=llm_client.CACHE_FILE; all_runs=[]; target=expected()
    for repeat in range(repeats):
        if cache_mode=='none':
            cache_path=ROOT/'results'/f'.cost_experiment_{name}_{repeat}.json'
            llm_client.CACHE_FILE=cache_path
            if cache_path.exists(): cache_path.unlink()
        else: llm_client.CACHE_FILE=original
        before=get_run_totals(); started=time.perf_counter()
        result=extract_attendance(messages, [p.name for p in roster], {p.name:p.aliases for p in roster}, batch_size=batch_size)
        elapsed=time.perf_counter()-started; after=get_run_totals()
        usage={k:after.get(k,0)-before.get(k,0) for k in ('input_tokens','cached_input_tokens','output_tokens','calls','cache_hits')}
        usage['latency_seconds']=elapsed; usage['estimated_cost']=None
        all_runs.append({'repeat':repeat+1,**usage,**score(result.claims,target)})
    llm_client.CACHE_FILE=original
    return {'variant':name,'runs':all_runs,'average':{key:statistics.fmean(row[key] for row in all_runs) for key in all_runs[0] if key!='repeat'}}

def _write_refusal(planned, total, reason):
    out=ROOT/'results'; out.mkdir(exist_ok=True)
    payload={'status':'refused','planned_calls':planned,'total_planned_calls':total,'reason':reason}
    (out/'cost_experiment.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    lines=['# Cost experiment','','**Status: REFUSED before any model call.**','',f'- Planned calls: `{total}`','',reason,'','| Variant | Planned calls |','|---|---:|']
    lines += [f'| {name} | {count} |' for name,count in planned.items()]
    (out/'cost_experiment.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--roster',type=Path,default=ROOT/'data/sample_roster.csv'); args=parser.parse_args()
    roster=load_roster(args.roster.name,args.roster.parent); parsed=parse_chat((ROOT/'data/labeled/labeled_chat.txt').read_text(encoding='utf-8')).messages
    planned = {"A_one_call_per_message": len(parsed), "B_batches_of_25": (len(parsed)+24)//25, "C_batches_plus_cache": 2*((len(parsed)+24)//25)}
    total_planned = sum(planned.values())
    counters = llm_client._read_json(llm_client.COUNTER_FILE, {"session": 0, "daily": 0})
    session_used = int(counters.get("session", 0)); daily_used = int(counters.get("daily", 0))
    if max(planned.values()) > config.MAX_LLM_CALLS_PER_RUN:
        reason = f"Refused before any model call: variant A requires {planned['A_one_call_per_message']} calls in one run, above the per-run limit of {config.MAX_LLM_CALLS_PER_RUN}."
        _write_refusal(planned, total_planned, reason); print(reason); return
    if session_used + total_planned > config.SESSION_CALL_BUDGET:
        reason = f"Refused before any model call: the experiment needs {total_planned} calls, but only {max(0, config.SESSION_CALL_BUDGET-session_used)} session calls remain."
        _write_refusal(planned, total_planned, reason); print(reason); return
    if daily_used + total_planned > config.DAILY_CALL_BUDGET:
        reason = f"Refused before any model call: the experiment needs {total_planned} calls and would exceed the daily budget of {config.DAILY_CALL_BUDGET}."
        _write_refusal(planned, total_planned, reason); print(reason); return
    os.environ["FAIRDRAW_DISABLE_CACHE"] = "1"
    data=[run_variant('A_one_call_per_message',messages=parsed,roster=roster,batch_size=1,cache_mode='none'),run_variant('B_batches_of_25',parsed,roster,25,'none'),run_variant('C_batches_plus_cache',parsed,roster,25,'cache',2)]
    out=ROOT/'results'; out.mkdir(exist_ok=True); (out/'cost_experiment.json').write_text(json.dumps({'settings':{'chat':'data/labeled/labeled_chat.txt','variant_A':'batch_size=1, cache=off','variant_B':'batch_size=25, cache=off','variant_C':'batch_size=25, cache=on, two runs'},'variants':data},indent=2))
    lines=['# Cost experiment','','| Variant | Input | Cached | Output | Calls | Latency | Precision | Recall | F1 |','|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for item in data:
        a=item['average']; lines.append(f"| {item['variant']} | {a['input_tokens']:.0f} | {a['cached_input_tokens']:.0f} | {a['output_tokens']:.0f} | {a['calls']:.0f} | {a['latency_seconds']:.2f}s | {a['precision']:.3f} | {a['recall']:.3f} | {a['f1']:.3f} |")
    (out/'cost_experiment.md').write_text('\n'.join(lines)+'\n'); print('\n'.join(lines))
if __name__=='__main__': main()

