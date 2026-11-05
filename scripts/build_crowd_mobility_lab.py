"""Run experiments only in crowd-mobility-lab. Frozen sources read-only."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.evaluate import audit
from src.crowd_mobility_lab.controller import simulate,DEFAULT
from src.crowd_mobility_lab.evaluate import evaluate
DATA=ROOT/'data/crowd-mobility-lab';OUT=ROOT/'outputs/crowd-mobility-lab'


def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n')


def register():
    old=json.loads((ROOT/'data/predictive-motion-lab/configs.json').read_text());train=dict(next(s for s in old['train'] if s['kind']=='shared'))
    tests=[]
    for seed,jitter,goal_jitter,rotation in [(8317,.025,0,0),(14293,.12,.05,.23),(23981,.10,.05,.61)]:
        rng=np.random.default_rng(seed);angles=np.arange(10)*2*np.pi/10+rotation+rng.uniform(-jitter,jitter,10)
        start=np.stack([np.sin(angles),np.cos(angles)],axis=-1)*3.8
        end=angles+np.pi+rng.uniform(-goal_jitter,goal_jitter,10)
        goal=np.stack([np.sin(end),np.cos(end)],axis=-1)*3.8
        tests.append({'name':f'shared-10-new-{seed}','kind':'shared','seed':seed,'starts':start.tolist(),'goals':goal.tolist(),'walls':[],
            'reference':'M02','duration':26,'radius':3.8,'angle_jitter':jitter,'goal_angle_jitter':goal_jitter,'global_rotation':rotation})
    starts=[[-3.8-i*.9,-.25] for i in range(5)]+[[3.8+i*.9,.25] for i in range(5)]
    goals=[[-x,-z] for x,z in starts]
    corridor={'name':'corridor-10-new-41017','kind':'corridor','seed':41017,'starts':starts,'goals':goals,'walls':[[-10,-2,10,-.8],[-10,.8,10,2]],'duration':26,'reference':'M02','width':1.6}
    conditions=[{'label':'G_old','variant':'G','strength':0,'baseline':True},
        {'label':'R0','variant':'long_cv','strength':0}, {'label':'R1','variant':'long_cv','strength':1},
        {'label':'no_reciprocity','variant':'goal_only','strength':0,'overrides':{'geometry_horizon':1.}},
        {'label':'short_body','variant':'reciprocal','strength':0}]
    plan={'version':1,'train':[train],'heldout':tests,'diagnostics':[corridor],'conditions':conditions,'parameters':DEFAULT,
        'main':'R0/R1 use reciprocal guidance and full 1 second body hard check. No prior per-ID passing schedule, no global plans.',
        'target':'At least 90% arrivals on original and most new shared scenes, with collision/continuity/failure also reported.',
        'limits':'26 seconds original deadline retained for all. Omnidirectional visible snapshots; no neighbor goal/reference/clip or true future plans.'}
    save(DATA/'plan.json',plan)
    paths=list((ROOT/'src/crowd_mobility_lab').glob('*.py'))+[Path(__file__),ROOT/'src/expression_layer.py',ROOT/'data/predictive-motion-lab/library.json',DATA/'plan.json']
    paths.extend(ROOT/p for p in json.loads((ROOT/'data/predictive-motion-lab/frozen-v4.json').read_text())['sha256'])
    save(DATA/'frozen-v1.json',{'saved_unix':time.time(),'before_new_heldout':True,'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}})
    print('Registered/frozen BEFORE new tests: 3 new shared seeds, original train and corridor diagnostic.',flush=True)


def task(job):
    split,spec,condition=job;key=f"{split}_{spec['name']}_{condition['label']}"
    lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
    start=time.perf_counter();cpu=time.process_time();origin='new_simulation'
    if condition.get('baseline'):
        if split=='train':
            run=json.loads((ROOT/'outputs/predictive-motion-lab/runs/train_shared-10-None-13_G_0.json').read_text());origin='exact_frozen_training_replay'
        else:
            from src.predictive_motion_lab.controller import simulate as original
            run=original(lib,spec,'G')
        run['layer_strength']=0
    else:run=simulate(lib,spec,condition['variant'],condition['strength'],condition.get('overrides'))
    save(OUT/'runs'/f'{key}.json',run)
    m=evaluate(run,lib);m.update(key=key,split=split,scene=spec['name'],kind=spec['kind'],label=condition['label'],strength=condition['strength'],
        worker_cpu_seconds=time.process_time()-cpu,worker_elapsed_seconds=time.perf_counter()-start,origin=origin,schedule='3 independent processes; isolate benchmark separately')
    save(DATA/'formal-metrics'/f'{key}.json',m)
    return {k:m[k] for k in ['key','arrived_fraction','max_proxy_penetration','stagnant_agents','emergency_hold_agent_seconds','worker_elapsed_seconds']}


def suite():
    plan=json.loads((DATA/'plan.json').read_text());frozen=json.loads((DATA/'frozen-v1.json').read_text())
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen['sha256'].items()),'Frozen code changed'
    jobs=[]
    for split in ['train','heldout','diagnostics']:
        for spec in plan[split]:
            for c in plan['conditions']:
                if split=='diagnostics' and c['label'] not in ['G_old','R0','R1']:continue
                key=f"{split}_{spec['name']}_{c['label']}"
                if not (DATA/'formal-metrics'/f'{key}.json').exists():jobs.append((split,spec,c))
    with ProcessPoolExecutor(max_workers=3,mp_context=multiprocessing.get_context('spawn')) as ex:
        for future in as_completed([ex.submit(task,j) for j in jobs]):print(json.dumps(future.result()),flush=True)
    rows=[json.loads(p.read_text()) for p in sorted((DATA/'formal-metrics').glob('*.json'))]
    save(DATA/'results.json',rows);save(OUT/'results.json',rows)
    save(OUT/'catalog.json',[{'key':r['key'],'scene':r['scene'],'split':r['split'],'label':r['label'],'file':f"runs/{r['key']}.json"} for r in rows])
    save(OUT/'skeleton.json',{'names':Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text())).names,
        'parents':Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text())).parents})
    for name in ['index.html','ui.js']:
        if (ROOT/'crowd-mobility-lab'/name).exists():(OUT/name).write_bytes((ROOT/'crowd-mobility-lab'/name).read_bytes())


def main():
    p=argparse.ArgumentParser();p.add_argument('--variant',default='reciprocal_flow');p.add_argument('--strength',type=float,default=0);p.add_argument('--name',default='attempt1');p.add_argument('--duration',type=float);p.add_argument('--config');p.add_argument('--register',action='store_true');p.add_argument('--suite',action='store_true');a=p.parse_args()
    if a.register:register();return
    if a.suite:suite();return
    lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()));cfg=json.loads((ROOT/'data/predictive-motion-lab/configs.json').read_text())
    spec=next(s for s in cfg['train'] if s['kind']=='shared');spec=dict(spec)
    if a.duration:spec['duration']=a.duration
    overrides=json.loads(a.config) if a.config else {}
    begin=time.perf_counter();run=simulate(lib,spec,a.variant,a.strength,overrides);save(OUT/'runs'/f'{a.name}.json',run)
    m=audit(run,lib);m.update(name=a.name,variant=a.variant,strength=a.strength,wall_seconds=time.perf_counter()-begin)
    save(DATA/'metrics'/f'{a.name}.json',m);print(json.dumps({k:m[k] for k in ['name','arrived_fraction','max_proxy_penetration','stagnant_agents','emergency_hold_agent_seconds','wall_seconds']}),flush=True)


if __name__=='__main__':main()
