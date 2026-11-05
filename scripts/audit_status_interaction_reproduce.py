"""Exact frozen re-simulation, then isolated active-snapshot timing."""
import argparse,json,time,sys,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_status_interaction_lab import library,OUT,DATA,save
from src.status_interaction_lab.simulation import simulate
from src.status_interaction_lab.social import CONFIG,PrivateSelf,visible,respond,controlled_library
from src.status_interaction_lab.navigation import choose,DEFAULT
from src.expression_layer import personal_library
from src.predictive_motion_lab.controller import State


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--benchmark-only',action='store_true');parser.add_argument('--reproduce-only',action='store_true');a=parser.parse_args()
    frozen=json.loads((DATA/'frozen.json').read_text());hash_ok=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen['sha256'].items());assert hash_ok
    lib=library();key='eval_shared-10-62003_C2';r=json.loads((OUT/'runs'/f'{key}.json').read_text());result=dict(frozen_hashes_match=hash_ok,key=key)
    if not a.benchmark_only:
        start=time.perf_counter();new=simulate(lib,r['spec'],'C2')
        # Stored JSON turns tuple collections/integer keys into lists/string keys.
        new=json.loads(json.dumps(new))
        result.update(frames_exact=new['frames']==r['frames'],decisions_exact=new['decisions']==r['decisions'],runtime_counts_exact=all(new['runtime'][k]==r['runtime'][k] for k in ['switches','emergency_hold_agent_steps','interaction_edges','arrival_times']),elapsed=time.perf_counter()-start)
        save(DATA/'reproducibility.json',result);print(json.dumps(result),flush=True)
    if a.reproduce_only:return
    f=r['frames'][60];previous=r['frames'][59];states=[]
    for i,(x,p) in enumerate(zip(f['agents'],previous['agents'])):
        states.append(State(i,np.array(x['pos']),np.array(r['spec']['goals'][i]),x['yaw'],x['travel'],x['speed'],lib.ids.index(x['clip']),lib.ids.index(['M01','M02','M03'][i%3]),x['phase'],np.array(x['pose']),(np.array(x['pose'])-np.array(p['pose']))/.05,x['arrived'],x['hold']))
    seen=[visible(s) for s in states];personal={s.reference:personal_library(lib,s.reference,CONFIG['personal_strength']) for s in states};timings=[]
    for repeat in range(3):
        begin=time.process_time()
        for s in states:
            history={}
            for d in r['decisions']:
                if d['id']==s.id and 2<=d['t']<3:
                    for o in d['response']['observations']:history[o['id']]=(history.get(o['id'],[])+[o['feature']])[-5:]
            control=next(d['control_after'] for d in r['decisions'] if d['id']==s.id and d['t']==2.8)
            response=respond(visible(s),seen,lib.names,history,control,'C2',CONFIG)
            own=controlled_library(personal[s.reference],PrivateSelf(r['private_experiment'][str(s.id)]['status']),response.applied,CONFIG)
            choose(own,s,seen,r['spec']['walls'],'long_cv',DEFAULT)
        timings.append((time.process_time()-begin)*1000)
    save(DATA/'isolated-benchmark.json',dict(cpu_ms_per_active_ten_agent_step=timings,median_ms=float(np.median(timings)),budget_ms=200,includes='observation response, per-step controlled libraries, constrained candidate synthesis and navigation; excludes rendering and one-time personal library',snapshot='C2 seed62003 t3; prior last visible samples rebuilt from logs',note='Run only after experiment workers finish. Empty post-arrival steps are excluded.'))
    print('active snapshot CPU ms',timings,flush=True)
if __name__=='__main__':main()
