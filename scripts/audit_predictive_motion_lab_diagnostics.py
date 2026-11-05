"""Explanations and acceptance checks from frozen artifacts, never retunes chooser."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.controller import State,choose,simulate,rollout
from src.predictive_motion_lab.evaluate import audit
from src.predictive_motion_lab.geometry import box

DATA=ROOT/'data/predictive-motion-lab';OUT=ROOT/'outputs/predictive-motion-lab'


def save(name,value):
    (DATA/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def reconstruct(run,index,lib):
    result=[];frame=run['frames'][index];previous=run['frames'][max(0,index-1)]
    for a,b,goal in zip(frame['agents'],previous['agents'],run['spec']['goals']):
        i=a['id'];reference=lib.ids.index(run['spec'].get('reference','M02')) if len(frame['agents'])==1 else lib.ids.index(['M01','M02','M03'][i%3])
        velocity=(np.array(a['pose'])-np.array(b['pose']))/.05 if index else lib.velocity(lib.ids.index(a['clip']),a['phase'],a['speed']/lib.speeds[lib.ids.index(a['clip'])]/lib.periods[lib.ids.index(a['clip'])])
        result.append(State(i,np.array(a['pos']),np.array(goal),a['yaw'],a['travel'],a['speed'],lib.ids.index(a['clip']),reference,a['phase'],np.array(a['pose']),velocity,a['arrived'],a['hold']))
    return result


def mechanism(lib):
    cases=[]
    for file in sorted((OUT/'runs').glob('train_door*G_0.json')):
        run=json.loads(file.read_text())
        for d in run['decisions']:
            selected=next((c for c in d['candidates'] if c['selected']),None)
            if not selected:continue
            alternatives=[c for c in d['candidates'] if c['clip']==selected['clip'] and c['scale']==selected['scale'] and c['steer']==selected['steer'] and not c['feasible'] and c['reason']=='predicted_body_overlap' and c['score']<selected['score']]
            if alternatives:
                state=reconstruct(run,round(d['t']/.05),lib)[0]
                opts=np.array([[lib.ids.index(c['clip']),c['scale'],c['steer'],c['phase_offset']] for c in [selected,alternatives[0]]])
                paths=rollout(lib,state,opts,np.arange(1,21)*.05)
                cases.append({'file':file.name,'t':d['t'],'selected':selected,'identical_root_control_other_phase_rejected':alternatives,
                              'verified_future_root_max_difference':float(np.abs(paths['pos'][:,0]-paths['pos'][:,1]).max()),
                              'future_pose_max_difference':float(np.linalg.norm(paths['pose'][:,0]-paths['pose'][:,1],axis=-1).max()),
                              'replayed_task_arrived':bool(run['runtime']['arrival_times']),
                              'meaning':'Same clip, scale, steer and source direction produce identical root trajectory; phase changes projected skeleton and feasibility.'})
                break
    save('mechanism-cases.json',cases)
    # Same snapshot, candidate list, change only body proxy; no artificial clip swap.
    file=OUT/'runs/train_door-1-0.46-13_G_0.json'
    if file.exists():
        run=json.loads(file.read_text());snapshot=reconstruct(run,20,lib)
        choices={}
        for mode in ['G','circle','no_prediction','no_continuity']:
            opt,log=choose(lib,snapshot[0],snapshot,run['spec']['walls'],mode,log=True)
            choices[mode]=log
        save('same-snapshot-counterfactual.json',{'source':file.name,'t':1.,'choices':choices})
    return cases


def summarize():
    metrics=[json.loads(f.read_text()) for f in sorted((DATA/'metrics').glob('*.json'))]
    graph=[]
    for m in metrics:
        if m['agent_count']<10:continue
        edges=m['interaction_edges'];adj={i:set() for i in range(m['agent_count'])}
        for a,b in edges:adj[a].add(b);adj[b].add(a)
        components=[];unseen=set(adj)
        while unseen:
            stack=[unseen.pop()];component=[]
            while stack:
                i=stack.pop();component.append(i)
                for j in adj[i]&unseen:unseen.remove(j);stack.append(j)
            components.append(component)
        graph.append({'key':m['key'],'edge_count':len(edges),'largest_component':max(map(len,components)),'max_degree':max(map(len,adj.values())),
                      'arrived_fraction':m['arrived_fraction'],'stagnant_agents':m['stagnant_agents'],'proxy_penetration':m['max_proxy_penetration']})
    save('interaction-graphs.json',graph)
    failure=[]
    for m in metrics:
        if m['scene']!='shared':continue
        run=json.loads((OUT/'runs'/f"{m['key']}.json").read_text())
        # Last-window clip distribution and feasibility log distinguish speed
        # homogenization, failure to find an action, and simple timeout.
        final=run['frames'][-1]['agents'];hist={}
        for a in final:hist[a['clip']]=hist.get(a['clip'],0)+1
        occupancy=[sum(np.linalg.norm(a['pos'])<1.5 for a in f['agents']) for f in run['frames']]
        peak=int(np.argmax(occupancy))
        minimal=[d for d in run['decisions'] if d['t']>=run['spec']['duration']-3]
        row={'key':m['key'],'last_three_seconds_zero_safe_fraction':sum(d['safe_count']==0 for d in minimal)/max(1,len(minimal)),
             'final_clip_histogram':hist,'stagnant_agents':m['stagnant_agents'],'remaining_goal_distance_mean':m['remaining_goal_distance_mean'],'worst':m['worst'],
             'shared_center_disk_radius':1.5,'max_simultaneous_roots_in_shared_disk':int(occupancy[peak]),'shared_disk_peak_t':run['frames'][peak]['t'],
             'clip_distribution_at_1s':{c:sum(a['clip']==c for a in run['frames'][20]['agents']) for c in {a['clip'] for a in run['frames'][20]['agents']}}}
        worst=m['worst']
        if worst and 'agents' in worst and worst['gap']<0:
            t=worst['t'];start_index=int(t/.2)*4;end_index=min(round(t/.05),len(run['frames'])-1)
            before=run['frames'][start_index];after=run['frames'][end_index];dt=after['t']-before['t'];errors=[]
            for i in worst['agents']:
                a=before['agents'][i];b=after['agents'][i]
                velocity=np.zeros(2) if a['hold'] or a['arrived'] else a['speed']*np.array([np.sin(a['yaw']+a['travel']),np.cos(a['yaw']+a['travel'])])
                predicted=np.array(a['pos'])+velocity*dt
                errors.append({'agent':i,'constant_velocity_position_error':float(np.linalg.norm(predicted-np.array(b['pos']))),
                               'body_yaw_change':float(b['yaw']-a['yaw']),
                               'local_joint_max_change':float(np.linalg.norm(np.array(b['pose'])-np.array(a['pose']),axis=-1).max())})
            row['observable_prediction_errors_during_executed_step']=errors
            row['preceding_decision_safe_counts']=[{'id':d['id'],'safe':d['safe_count']} for d in run['decisions'] if abs(d['t']-before['t'])<1e-6 and d['id'] in worst['agents']]
        failure.append(row)
    save('failure-diagnostics.json',failure)
    cfg=json.loads((DATA/'configs.json').read_text())
    frozen=json.loads((DATA/'frozen-v4.json').read_text())
    hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen['sha256'].items()}
    expected=sum(len(cfg[s])*len(cfg['conditions']) for s in ['train','heldout'])
    save('acceptance.json',{'expected_runs':expected,'actual_runs':len(metrics),'all_frozen_hashes_match':all(hashes.values()),'hash_checks':hashes,
                           'all_keys_unique':len({m['key'] for m in metrics})==len(metrics),'heldout_seeds_disjoint':not ({s['seed'] for s in cfg['train']}&{s['seed'] for s in cfg['heldout']}),
                           'train_test_door_widths_disjoint':not ({s['width'] for s in cfg['train'] if s['kind']=='door'}&{s['width'] for s in cfg['heldout'] if s['kind']=='door'}),
                           'max_replay_bone_relative_error':max((m['max_bone_relative_error'] for m in metrics),default=None),
                           'note':'Completeness/integrity checks are not evidence of naturalness or human-perceived status.'})
    return metrics


def benchmark(lib):
    """Single process, CPU process time and elapsed wall time, congested snapshots.

    Runs after experiment jobs finish. No renderer included; not FPS. All
    agents planned from the same snapshot, repeated three times unchanged.
    """
    rows=[]
    for count,seed in [(10,71),(30,89)]:
        file=OUT/f'runs/heldout_shared-{count}-None-{seed}_G_0.json'
        if not file.exists():continue
        run=json.loads(file.read_text())
        index=min(round(5/.05),len(run['frames'])-1)
        snapshot=reconstruct(run,index,lib)
        samples=[]
        for _ in range(3):
            wall=time.perf_counter();cpu=time.process_time()
            for s in snapshot:choose(lib,s,snapshot,run['spec']['walls'],'G')
            samples.append({'cpu_ms':(time.process_time()-cpu)*1000,'elapsed_ms':(time.perf_counter()-wall)*1000})
        rows.append({'count':count,'snapshot_t':run['frames'][index]['t'],'samples':samples,'includes_rendering':False,'one_complete_synchronous_decision':True})
    save('performance-isolated.json',rows)


def extras(lib):
    cfg=json.loads((DATA/'configs.json').read_text());rows=[]
    folder=OUT/'diagnostics';folder.mkdir(exist_ok=True)
    for width in [.36,.46]:
        spec={**next(s for s in cfg['train'] if s['width']==width),'reference':'M03'}
        run=simulate(lib,spec,'F');m=audit(run,lib)
        rows.append({'width':width,'reference':'M03','role':'Post-hoc coverage diagnostic, changed initial reference; excluded from fair F/G/P comparison.','metrics':m})
        (folder/f'fixed-M03-width-{width}.json').write_text(json.dumps(run,separators=(',',':'))+'\n')
    save('coverage-oracle-diagnostic.json',rows)
    widths=[]
    for i,c in enumerate(lib.ids):
        poses=lib.sample(i,np.arange(128)/128)
        center,axes,half=box(poses,np.zeros((128,2)),np.full(128,-lib.angles[i]))
        needed=2*(np.abs(center[:,0])+(np.abs(axes[:,:,0])*half).sum(axis=1)).max()+.01
        widths.append({'clip':c,'centered_straight_rectangle_full_cycle_sufficient_width':float(needed),'includes_two_sides_margin':.01,
                       'note':'Sufficient conservative width for centered full-cycle straight travel, not minimum achievable door width.'})
    save('centerline-width-diagnostic.json',widths)
    impossible=[]
    for mode in ['F','G']:
        spec={**cfg['train'][0],'name':'certified-too-thin-within-time-budget','width':.06,
              'walls':[[-100,-.12,-.03,.12],[.03,-.12,100,.12]]}
        run=simulate(lib,spec,mode);m=audit(run,lib)
        impossible.append({'mode':mode,'spec':spec,'metrics':m,'certificate':{
            'proxy_min_diameter':.08,'door_width':.06,'maximum_root_travel_within_12s':float(lib.speeds.max()*1.15*12),
            'detour_wall_end_distance':100,'scope':'Impossible within finite time under this thickened skeleton proxy and bounded continuous root motion. Not a mesh statement.'}})
        (folder/f'impossible-{mode}.json').write_text(json.dumps(run,separators=(',',':'))+'\n')
    save('certified-failure-diagnostic.json',impossible)
    file=OUT/'runs/train_door-1-0.46-13_G_0.json'
    run=json.loads(file.read_text());copy=simulate(lib,run['spec'],'G')
    save('reproducibility.json',{'run':str(file.relative_to(ROOT)),'all_replay_frames_exactly_equal':copy['frames']==run['frames'],
                                'frame_count':len(copy['frames']),'old_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'compared':'Root, pose, phase, clip, hold and arrival frames; timing excluded.'})


def moving_expression(lib):
    rows=[];arms=[lib.names.index(n) for n in ['Chest','Head','LowerArm_L','Hand_L','LowerArm_R','Hand_R']]
    for metric in sorted((DATA/'metrics').glob('*.json')):
        m=json.loads(metric.read_text());run=json.loads((OUT/'runs'/f"{m['key']}.json").read_text());n=m['agent_count']
        frames=run['frames'];agents=[a for f in frames[:-1] for a in f['agents']]
        poses=np.array([a['pose'] for a in agents]);phases=np.array([a['phase'] for a in agents])
        refs=np.array([lib.ids.index(run['spec'].get('reference','M02')) if n==1 else lib.ids.index(['M01','M02','M03'][a['id']%3]) for a in agents])
        reference=lib.sample(refs,phases)
        err=np.sqrt(np.mean(((poses[:,arms]-poses[:,0,None])-(reference[:,arms]-reference[:,0,None]))**2,axis=(1,2)))
        before=np.array([a['pos'] for a in agents]);after=np.array([a['pos'] for f in frames[1:] for a in f['agents']])
        moving=(np.linalg.norm(after-before,axis=1)/.05>.05)&np.array([not a['hold'] and not a['arrived'] for a in agents])
        rows.append({'key':m['key'],'actual_reference_pose_rms_moving_only':float(err[moving].mean()) if moving.any() else None,
                     'moving_frame_agent_samples':int(moving.sum()),'total_frame_agent_samples':len(agents),'moving_definition':'actual root displacement / .05 > .05 heights/s AND not hold/arrived',
                     'actual_reference_pose_rms_all_frames':float(err.mean()),'note':'Post-hoc conditional diagnostic; not human expression/status ground truth.'})
    save('expression-moving-diagnostic.json',rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--benchmark',action='store_true');parser.add_argument('--extra',action='store_true');parser.add_argument('--moving',action='store_true');args=parser.parse_args()
    lib=Library(json.loads((DATA/'library.json').read_text()))
    save('expression-profile.json',{'reference':'Immutable initial M01/M02/M03 by agent; not status labels',
        'joints':['Chest','Head','UpperArm_L','LowerArm_L','Hand_L','UpperArm_R','LowerArm_R','Hand_R'],
        'feature_order':'24 mean local relative XYZ values (joint-major), then 24 per-axis standard deviations, 128 canonical phases',
        'feature_scale':lib.feature_scale.tolist(),'scale_definition':'max(std across all eleven accepted clip archives, axis=0), .015)',
        'clip_ids':lib.ids,'expression_cost':'mean squared standardized difference between candidate and immutable reference archive',
        'target_native_speed_ranges':{c:[float(.8*v),float(1.15*v)] for c,v in zip(lib.ids,lib.speeds)},
        'availability':'Direction edges in library.json/transitions; all G and G+P see the same candidates given the same state. F fixes the initial clip.'})
    if args.benchmark:benchmark(lib)
    if args.extra:extras(lib)
    if args.moving:moving_expression(lib)
    metrics=summarize();cases=mechanism(lib)
    print('runs',len(metrics),'phase/body mechanism cases',len(cases))
