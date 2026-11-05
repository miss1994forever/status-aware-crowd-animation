"""Integrity, tables, replay recheck and isolated timing for mobility experiment."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab import controller as old
from src.crowd_mobility_lab.controller import choose,DEFAULT
from src.crowd_mobility_lab.evaluate import evaluate
from scripts.audit_crowd_mobility_diagnosis import states_at
DATA=ROOT/'data/crowd-mobility-lab';OUT=ROOT/'outputs/crowd-mobility-lab'


def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def summarize():
    rows=[]
    for p in sorted((DATA/'formal-metrics').glob('*.json')):
        try:rows.append(json.loads(p.read_text()))
        except json.JSONDecodeError:pass # An in-flight write; final count is checked explicitly.
    save(DATA/'results.json',rows);save(OUT/'results.json',rows)
    save(OUT/'catalog.json',[{'key':r['key'],'scene':r['scene'],'split':r['split'],'label':r['label'],'file':f"runs/{r['key']}.json"} for r in rows])
    columns=['key','split','scene','kind','label','strength']+sorted({k for r in rows for k,v in r.items() if not isinstance(v,(dict,list))}-{'key','split','scene','kind','label','strength'})
    with (DATA/'results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    (OUT/'results.csv').write_bytes((DATA/'results.csv').read_bytes())
    text=['# 全部冻结结果','',f'{len(rows)}/23 次；未完成不填零。穿透与源差距为身体代理/动作统计，不是网格或自然度真值。','',
        '|分组/场景|条件|到达|代理穿透|冻结人秒|移动比例|已到达路径伸长|活动关节速度变化p99|移动上身参考方向RMS|','|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        stretch='NA' if r['completed_path_stretch_mean'] is None else f"{r['completed_path_stretch_mean']:.3f}"
        text.append(f"|{r['split']}/{r['scene']}|{r['label']}|{r['arrived_fraction']:.0%}|{r['max_proxy_penetration']:.5f}|{r['emergency_hold_agent_seconds']:.2f}|{r['moving_active_fraction']:.3f}|{stretch}|{r['active_joint_velocity_change_p99']:.3f}|{r['upper_reference_direction_rms_moving']:.3f}|")
    (DATA/'tables.md').write_text('\n'.join(text)+'\n')
    frozen=json.loads((DATA/'frozen-v1.json').read_text());checks={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen['sha256'].items()}
    save(DATA/'integrity.json',{'expected_runs':23,'actual_runs':len(rows),'unique_keys':len({r['key'] for r in rows})==len(rows),'frozen_hashes_match':checks,'all_frozen_hashes_match':all(checks.values()),
        'all_replays_present':all((OUT/'runs'/f"{r['key']}.json").exists() for r in rows)})
    lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
    save(OUT/'skeleton.json',{'names':lib.names,'parents':lib.parents,'lengths':lib.lengths.tolist()})
    for name in ['index.html','ui.js']:(OUT/name).write_bytes((ROOT/'crowd-mobility-lab'/name).read_bytes())
    (OUT/'LICENSE.txt').write_bytes((ROOT/'data/raw/bandai-pilot/LICENSE').read_bytes())
    return rows


def explain(rows):
    explanations=[]
    for r in rows:
        if r['label']!='R0':continue
        run=json.loads((OUT/'runs'/f"{r['key']}.json").read_text())
        counts={'decisions':len(run['decisions']),'orca_infeasible':sum(not d.get('orca_feasible',True) for d in run['decisions']),
            'zero_body_feasible':sum(d['safe_count']==0 for d in run['decisions'])}
        cases=[]
        for d in run['decisions']:
            chosen=next((c for c in d['candidates'] if c['selected']),None)
            if not chosen:continue
            rejected=[c for c in d['candidates'] if not c['feasible'] and c['score']<chosen['score']]
            if rejected:cases.append({'t':d['t'],'id':d['id'],'selected':chosen,'better_cost_but_body_rejected':min(rejected,key=lambda c:c['score'])})
        positions=np.array([[a['pos'] for a in f['agents']] for f in run['frames']]);occupancy=(np.linalg.norm(positions,axis=-1)<1.5).sum(1)
        explanations.append({'key':r['key'],**counts,'body_changed_choice_count_in_logged_steps':len(cases),'examples':cases[:3],
            'max_shared_disk_occupancy':int(occupancy.max()),'shared_disk_radius':1.5,'edges':r['interaction_edges'],
            'maximum_root_radius':float(np.linalg.norm(positions,axis=-1).max()),
            'note':'Body gate includes .015 margin and source residual .4 limit; all candidate components are logged.'})
    save(DATA/'decision-mechanisms.json',explanations)
    comparisons=[]
    for scene in {r['scene'] for r in rows}:
        group={r['label']:r for r in rows if r['scene']==scene}
        if not all(k in group for k in ['G_old','R0','R1']):continue
        runs={k:json.loads((OUT/'runs'/f"{group[k]['key']}.json").read_text()) for k in ['G_old','R0','R1']}
        comparisons.append({'scene':scene,'initial_frames_identical':runs['G_old']['frames'][0]==runs['R0']['frames'][0]==runs['R1']['frames'][0],
            'tasks_identical':all(runs[k]['spec']==runs['G_old']['spec'] for k in ['R0','R1']),
            'all_trajectories_have_full_duration':all(len(x['frames'])==round(x['spec']['duration']/.05)+1 for x in runs.values())})
    save(DATA/'task-comparability.json',comparisons)


def recovery_diagnostic():
    lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
    run=json.loads((ROOT/'outputs/predictive-motion-lab/runs/train_shared-10-None-13_G_0.json').read_text());states=states_at(run,200,lib)
    entries=[]
    for s in states:
        opt,d=choose(lib,s,states,[],'long_cv',DEFAULT,log=True)
        entries.append({'id':s.id,'safe_count':d['safe_count'],'desired':d['desired'],'selected':next((x for x in d['candidates'] if x['selected']),None)})
    save(DATA/'late-frozen-state-diagnostic.json',{'t':10,'source':'old G train seed13','entries':entries,
        'scope':'Post-hoc one-step feasibility on already jammed observed state, not a new tuned run or a recovery-success claim.'})


def benchmark():
    lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()));source=json.loads((ROOT/'outputs/predictive-motion-lab/runs/train_shared-10-None-13_G_0.json').read_text())
    states=states_at(source,60,lib);rows=[]
    for method in ['G_old','R0']:
        samples=[]
        for _ in range(3):
            cpu=time.process_time();wall=time.perf_counter()
            for s in states:
                if method=='G_old':old.choose(lib,s,states,[])
                else:choose(lib,s,states,[],'long_cv',DEFAULT)
            samples.append({'cpu_ms':(time.process_time()-cpu)*1000,'elapsed_ms':(time.perf_counter()-wall)*1000})
        rows.append({'method':method,'same_input':'old G training snapshot t=3s, all ten agents','samples':samples,'includes_rendering':False,'includes_personal_library_precompute':False})
    save(DATA/'isolated-performance.json',rows)


def recheck(keys):
    lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()));results=[]
    for key in keys:
        run=json.loads((OUT/'runs'/f'{key}.json').read_text());actual=evaluate(run,lib);prior=json.loads((DATA/'formal-metrics'/f'{key}.json').read_text())
        results.append({'key':key,'all_metrics_match':all(prior.get(k)==v for k,v in actual.items()),'recomputed':actual})
    save(DATA/'independent-recheck.json',results)


def kinematics(rows):
    lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()));output=[]
    for r in rows:
        run=json.loads((OUT/'runs'/f"{r['key']}.json").read_text());frames=run['frames']
        poses=np.array([[a['pose'] for a in f['agents']] for f in frames]);yaw=np.array([[a['yaw'] for a in f['agents']] for f in frames]);speed=np.array([[a['speed'] for a in f['agents']] for f in frames])
        active=np.array([[not a['hold'] and not a['arrived'] for a in f['agents']] for f in frames]);mask=active[1:]&active[:-1]
        errors=[]
        for j,p in enumerate(lib.parents):
            if p is not None and lib.lengths[j]>1e-6:errors.append(np.max(np.abs(np.linalg.norm(poses[:,:,j]-poses[:,:,p],axis=-1)/lib.lengths[j]-1)))
        changes=[]
        for f,g in zip(frames,frames[1:]):
            for a,b in zip(f['agents'],g['agents']):
                if a['clip']!=b['clip']:changes.append(abs(float((lib.angles[lib.ids.index(a['clip'])]-lib.angles[lib.ids.index(b['clip'])]+np.pi)%(2*np.pi)-np.pi)))
        output.append({'key':r['key'],'raw_saved_pose_bone_relative_error_max':float(max(errors)),'active_yaw_rate_max':float(np.abs(np.diff(yaw,axis=0)[mask]).max(initial=0)/.05),
            'active_scalar_acceleration_max':float(np.abs(np.diff(speed,axis=0)[mask]).max(initial=0)/.05),'source_direction_edge_max':max(changes,default=0),
            'stop_bound_exception_note':'Active-pair bounds exclude entry/exit of emergency hold and terminal arrival; full acceleration is separately reported and can spike.',
            'bone_note':'Raw rounded 20Hz pose before audit re-projection; viewer uses bone-length reconstruction when interpolating.'})
    save(DATA/'kinematic-audit.json',output)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--benchmark',action='store_true');p.add_argument('--recheck',nargs='*');a=p.parse_args()
    rows=summarize();explain(rows)
    recovery_diagnostic()
    kinematics(rows)
    if a.benchmark:benchmark()
    if a.recheck:recheck(a.recheck)
    print('Completed rows',len(rows),'/',23)
