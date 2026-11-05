"""Build verified motion library, pre-register configs, then run frozen experiments."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.predictive_motion_lab.motion import Library,prepare
from src.predictive_motion_lab.controller import simulate
from src.predictive_motion_lab.evaluate import audit

DATA=ROOT/'data/predictive-motion-lab';OUT=ROOT/'outputs/predictive-motion-lab'


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')


def scenario(kind,seed,width=None,count=1):
    rng=np.random.default_rng(seed)
    if kind=='door':
        starts=[[0,-1.4]];goals=[[0,1.6]]
        walls=[[-2,-.12,-width/2,.12],[width/2,-.12,2,.12]]
    else:
        r=3.8 if count<=10 else 5.5
        angles=np.arange(count)*2*math.pi/count+rng.uniform(-.025,.025,count)
        starts=np.stack([np.sin(angles),np.cos(angles)],axis=-1)*r
        goals=-starts
        starts=starts.tolist();goals=goals.tolist();walls=[]
    return {'name':f'{kind}-{count}-{width}-{seed}','kind':kind,'seed':seed,'width':width,'starts':starts,'goals':goals,'walls':walls,
            'reference':'M02','duration':12 if kind=='door' else (18 if count==2 else 26 if count==10 else 36)}


def configs():
    # Test widths/seeds are disjoint and committed to disk BEFORE any results.
    return {'version':4,'train':[scenario('door',13,w) for w in [.28,.36,.46,.62]]+[scenario('wide',13,count=2),scenario('shared',13,count=10)],
            'heldout':[scenario('door',71,w) for w in [.31,.40,.53,.72]]+[scenario('wide',71,count=2),scenario('shared',71,count=10),scenario('shared',89,count=30)],
            'conditions':[['F',0],['G',0],['G+P',.12],['G+P',.6],['G+P',2.],['no_prediction',0],['circle',0],['no_continuity',0]],
            'parameters':{'horizon_seconds':1,'replan_seconds':.2,'integration_seconds':.05,'blend_seconds':.4,'radius':.04,'scale_range':[.8,1.15],
                          'feasible_margin':.005,'max_yaw_rate':1.4,'max_travel_angle_rate':1.8,'max_accel':1.2,'max_transition_deformation':.4,
                          'shared_navigation':'steer bias +0.6 rad if observable neighbor within 2.5 heights and >0.2 ahead; weight 0.15'},
            'test_policy':'Frozen before running. No per-condition tuning. Retain failures. Any post-test correction requires new version and disclosure.'}


def build_page():
    source=ROOT/'predictive-motion-lab'
    for name in ['index.html','ui.js']:
        if (source/name).exists():(OUT/name).write_bytes((source/name).read_bytes())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--split',choices=['train','heldout','all'],default='train');parser.add_argument('--limit',type=int);parser.add_argument('--condition');parser.add_argument('--page',action='store_true');args=parser.parse_args()
    DATA.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    if args.prepare:
        save(DATA/'library.json',prepare(ROOT));save(DATA/'configs.json',configs())
        (OUT/'LICENSE.txt').write_bytes((ROOT/'data/raw/bandai-pilot/LICENSE').read_bytes())
        save(DATA/'stage-log.json',[{'stage':'preparation','time':time.time(),'state':'coverage and configurations saved before simulation'}])
        return
    if args.page:build_page();return
    lib=Library(json.loads((DATA/'library.json').read_text()));cfg=json.loads((DATA/'configs.json').read_text())
    splits=['train','heldout'] if args.split=='all' else [args.split]
    rows=[]
    for split in splits:
        scenes=cfg[split][:args.limit] if args.limit else cfg[split]
        for spec in scenes:
            for mode,p in cfg['conditions']:
                if args.condition and mode!=args.condition:continue
                key=f"{split}_{spec['name']}_{mode}_{p}"
                file=OUT/'runs'/f'{key}.json';metricfile=DATA/'metrics'/f'{key}.json'
                if metricfile.exists():
                    print('cached',key,flush=True);continue
                began=time.perf_counter()
                run=simulate(lib,spec,'G' if mode=='G+P' else mode,p);run['mode']=mode
                save(file,run)
                metric=audit(run,lib);metric.update(key=key,split=split,scene=spec['kind'],width=spec['width'],mode=mode,p_weight=p,seed=spec['seed'],wall_seconds=time.perf_counter()-began)
                save(metricfile,metric)
                print(key,'arrived',metric['arrived_fraction'],'penetration',round(metric['max_proxy_penetration'],4),'hold',round(metric['emergency_hold_agent_seconds'],2),'seconds',round(metric['wall_seconds'],2),flush=True)
    for f in sorted((DATA/'metrics').glob('*.json')):rows.append(json.loads(f.read_text()))
    save(DATA/'results.json',rows);save(OUT/'results.json',rows)
    with (DATA/'results.csv').open('w',newline='') as stream:
        fields=[k for k,v in rows[0].items() if not isinstance(v,(dict,list))] if rows else []
        writer=csv.DictWriter(stream,fields,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    save(OUT/'catalog.json',[{'key':r['key'],'split':r['split'],'mode':r['mode'],'scene':r['scene'],'width':r['width'],'count':r['agent_count'],'p':r['p_weight'],'file':f"runs/{r['key']}.json"} for r in rows])
    save(OUT/'skeleton.json',{'names':lib.names,'parents':lib.parents})
    save(DATA/'environment.json',{'python':platform.python_version(),'numpy':np.__version__,'platform':platform.platform(),
        'config_sha256':hashlib.sha256((DATA/'configs.json').read_bytes()).hexdigest(),'code_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in list((ROOT/'src/predictive_motion_lab').glob('*.py'))+[Path(__file__)]}})
    build_page()


if __name__=='__main__':main()
