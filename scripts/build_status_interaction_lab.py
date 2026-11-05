"""Own-path-only experiment runner; registration precedes evaluation."""
import argparse,hashlib,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.status_interaction_lab.simulation import simulate
from src.status_interaction_lab.social import CONFIG
from src.status_interaction_lab.yoke import matched_yoke
from concurrent.futures import ProcessPoolExecutor
from src.crowd_mobility_lab.evaluate import evaluate
DATA=ROOT/'data/status-interaction-lab';OUT=ROOT/'outputs/status-interaction-lab'
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n')
def library():return Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
def scene(seed=13,n=10,duration=26,kind='shared'):
    if seed==13 and n==10:
        s=dict(json.loads((ROOT/'data/crowd-mobility-lab/plan.json').read_text())['train'][0]);s['duration']=duration;return s
    if kind=='pair':return dict(name=f'pair-{seed}',kind=kind,seed=seed,starts=[[-2,-.18],[2,.18]],goals=[[2,-.18],[-2,.18]],walls=[],duration=duration,reference='M02')
    if kind=='corridor':
        s=dict(json.loads((ROOT/'data/crowd-mobility-lab/plan.json').read_text())['diagnostics'][0]);s.update(seed=seed,name=f'corridor-{seed}',duration=duration);return s
    rng=np.random.default_rng(seed);a=np.arange(n)*2*np.pi/n+.37+rng.uniform(-.07,.07,n)
    radius=3.8 if n==10 else 5.8
    b=a+np.pi+rng.uniform(-.04,.04,n)
    return dict(name=f'shared-{n}-{seed}',kind=kind,seed=seed,starts=(np.stack([np.sin(a),np.cos(a)],-1)*radius).tolist(),goals=(np.stack([np.sin(b),np.cos(b)],-1)*radius).tolist(),walls=[],duration=duration,reference='M02')
def run(key,spec,mode,config=None,yoke=None):
    target=OUT/'runs'/f'{key}.json'
    if target.exists():raise RuntimeError(f'Refusing overwrite: {target}')
    lib=library();start=time.perf_counter();cpu=time.process_time()
    r=simulate(lib,spec,mode,config,yoke=yoke);save(target,r)
    m=evaluate(r,lib);m.update(key=key,mode=mode,wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu)
    save(DATA/'metrics'/f'{key}.json',m)
    print(json.dumps({k:m[k] for k in ['key','arrived_fraction','max_proxy_penetration','stagnant_agents','planning_seconds','cpu_seconds']}),flush=True)
    return r,m

def freeze():
    target=DATA/'frozen.json'
    if target.exists():raise RuntimeError('Already frozen')
    plan=json.loads((DATA/'preregistration.json').read_text())
    plan.update(config=CONFIG,kinematic_bounds={'source_cone':.75,'bone_rate':8.,'toe_rate':12.,'ground':0.},evaluation=[scene(s) for s in plan['evaluation_seeds']]+[scene(62023,kind='corridor')])
    save(DATA/'plan.json',plan)
    files=list((ROOT/'src/status_interaction_lab').glob('*.py'))+[Path(__file__),DATA/'plan.json']
    files += list((ROOT/'src/crowd_mobility_lab').glob('*.py'))+list((ROOT/'src/predictive_motion_lab').glob('*.py'))+[ROOT/'src/expression_layer.py',ROOT/'data/predictive-motion-lab/library.json']
    save(target,dict(unix=time.time(),sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))

def evaluation_scene(s):
    for mode in ['C1','C2','C2-no-confidence','C2-yoked']:
        key=f"eval_{s['name']}_{mode}"
        if (DATA/'metrics'/f'{key}.json').exists():continue
        yoke=None
        if mode=='C2-yoked':
            donor=json.loads((OUT/'runs'/f"eval_{s['name']}_C2.json").read_text())
            yoke,records=matched_yoke(donor);save(DATA/'yokes'/f"{s['name']}.json",records)
        run(key,s,mode,yoke=yoke)
    return s['name']+' complete'

def main():
    p=argparse.ArgumentParser();p.add_argument('--key');p.add_argument('--seed',type=int,default=13);p.add_argument('--n',type=int,default=10);p.add_argument('--duration',type=float,default=26);p.add_argument('--kind',default='shared');p.add_argument('--mode',default='C2');p.add_argument('--freeze',action='store_true');p.add_argument('--suite',action='store_true');a=p.parse_args()
    if a.freeze:freeze();return
    if a.suite:
        frozen=json.loads((DATA/'frozen.json').read_text());assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen['sha256'].items())
        plan=json.loads((DATA/'plan.json').read_text())
        with ProcessPoolExecutor(max_workers=2) as pool:
            for result in pool.map(evaluation_scene,plan['evaluation']):print(result,flush=True)
        return
    run(a.key,scene(a.seed,a.n,a.duration,a.kind),a.mode)
if __name__=='__main__':main()
