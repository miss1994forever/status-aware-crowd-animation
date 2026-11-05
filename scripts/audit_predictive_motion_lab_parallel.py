"""Schedule remaining FROZEN independent runs on local CPU processes.

No agent delegation and no algorithm/configuration changes. Timing gathered
under concurrency is flagged; isolated benchmark is the performance evidence.
Never run alongside the sequential builder for the same keys.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib
import json
import multiprocessing
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.controller import simulate
from src.predictive_motion_lab.evaluate import audit
DATA=ROOT/'data/predictive-motion-lab';OUT=ROOT/'outputs/predictive-motion-lab'


def job(task):
    split,spec,mode,p,workers=task
    lib=Library(json.loads((DATA/'library.json').read_text()))
    key=f"{split}_{spec['name']}_{mode}_{p}"
    began=time.perf_counter();cpu=time.process_time()
    run=simulate(lib,spec,'G' if mode=='G+P' else mode,p);run['mode']=mode
    run['execution_schedule']=f'{workers} independent local processes; elapsed timings under contention'
    (OUT/'runs'/f'{key}.json').write_text(json.dumps(run,ensure_ascii=False,separators=(',',':'))+'\n')
    metric=audit(run,lib);metric.update(key=key,split=split,scene=spec['kind'],width=spec['width'],mode=mode,p_weight=p,seed=spec['seed'],
        wall_seconds=time.perf_counter()-began,worker_process_cpu_seconds=time.process_time()-cpu,
        execution_schedule=run['execution_schedule'])
    (DATA/'metrics'/f'{key}.json').write_text(json.dumps(metric,ensure_ascii=False,separators=(',',':'))+'\n')
    return {'key':key,'arrived':metric['arrived_fraction'],'penetration':metric['max_proxy_penetration'],'wall_seconds':metric['wall_seconds']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=3);args=parser.parse_args()
    cfg=json.loads((DATA/'configs.json').read_text());tasks=[]
    freeze=json.loads((DATA/'frozen-v4.json').read_text())
    if not all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['sha256'].items()):raise RuntimeError('Frozen code/config mismatch')
    for split in ['train','heldout']:
        for spec in cfg[split]:
            for mode,p in cfg['conditions']:
                key=f"{split}_{spec['name']}_{mode}_{p}"
                if not (DATA/'metrics'/f'{key}.json').exists():tasks.append((split,spec,mode,p,args.workers))
    (DATA/'parallel-schedule.json').write_text(json.dumps({'saved_unix':time.time(),'workers':args.workers,'remaining_keys':[f"{s}_{spec['name']}_{m}_{p}" for s,spec,m,p,w in tasks],
        'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'note':'Timing under concurrency; use performance-isolated.json for CPU comparison.'},indent=2)+'\n')
    print('Remaining frozen runs:',len(tasks),flush=True)
    with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn')) as executor:
        futures=[executor.submit(job,t) for t in tasks]
        for f in as_completed(futures):print(json.dumps(f.result()),flush=True)


if __name__=='__main__':main()
