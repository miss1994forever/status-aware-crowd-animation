"""Audit one-way arrival/exit lifecycle and the bounded status-gap distance mapping."""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def audit(path):
    config=json.loads((path/'config.json').read_text())
    runtime=json.loads((path/'runtime-config.json').read_text())
    assert config['singlePass'] and runtime['singlePass']
    assert runtime['build'] in ('social-space-v8','social-space-v9','social-space-v10','social-space-v11','social-space-v12', 'social-space-v13','social-space-v14','social-space-v15','social-space-v16','social-space-v17','social-space-v18','social-space-v19','social-space-v20','social-space-v21','social-space-v22','social-space-v23') and runtime['spatial']==config['spatial']
    rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader((path/'telemetry.csv').open())]
    actors=defaultdict(list);frames=defaultdict(list)
    for row in rows:actors[int(row['id'])].append(row);frames[int(row['frame'])].append(row)
    result={};formula_error=0
    for actor,samples in actors.items():
        assert all(r['arrivals'] in (0,1) for r in samples)
        assert all(a['journey_phase']<=b['journey_phase'] for a,b in zip(samples,samples[1:]))
        assert all(r['status']==(actor%3)*.5 for r in samples)
        final=samples[-1]
        arrived=[r for r in samples if r['journey_phase']>=1]
        departed=[r for r in samples if r['journey_phase']==2]
        assert arrived and departed, f'Actor {actor} did not arrive and exit'
        assert 0<=final['arrival_time']<final['departure_time']<=final['time']
        assert math.hypot(final['x'],final['z'])>=7.3, 'Actor removed inside the transit area'
        assert all(math.hypot(r['input_x'],r['input_z'])==0 for r in departed)
        assert all(r['pose_updates']==departed[0]['pose_updates'] for r in departed), 'Departed actor still animated'
        assert max(math.hypot(a['x']-b['x'],a['z']-b['z']) for a,b in zip(samples,samples[1:]))<.6, 'Position discontinuity'
        for row in samples:
            if row['journey_phase']==2:continue
            if config['spatial']>=8:
                delta=row['status']-row['social_raw_estimate']
                expected=1.1+row['social_weight']*(.4*max(0,delta)**2+.6*max(0,-delta)**2)*(row.get('discretion_weight',1) if config['spatial']==10 and row['target_id']>=0 else 1)
                formula_error=max(formula_error,abs(expected-row['social_gap']))
        result[actor]=dict(status=final['status'],arrivals=int(final['arrivals']),phase=int(final['journey_phase']),
            arrival_time=final['arrival_time'],departure_time=final['departure_time'])
    for group in frames.values():
        live={int(r['id']) for r in group if r['journey_phase']<2}
        assert all(int(r['target_id'])<0 or int(r['target_id']) in live for r in group), 'Departed actor retained as target'
    assert formula_error<2e-6
    groups={}
    for status in (0,.5,1):
        own=[r for r in result.values() if r['status']==status]
        groups[status]=dict(count=len(own),mean_arrival_s=sum(r['arrival_time'] for r in own)/len(own),last_departure_s=max(r['departure_time'] for r in own))
    return dict(run=path.name,complete=(path/'finished.txt').exists(),actors=result,groups=groups,
        all_frame_min_live_centre_gap_m=rows[-1]['min_frame_gap'],formula_max_error_m=formula_error,
        preference_model=runtime['preferenceModel'])


if __name__=='__main__':
    paths=[Path(p) for p in sys.argv[1:]]
    report=dict(runs=[audit(p) for p in paths],qualification='Arrival within 0.65m; exit at external endpoint. Centre gaps are not mesh clearance. Status labels are viewer diagnostics, not validated status recognition.')
    (paths[0].parent/('sidestep-oneway-audit.json' if any(p.name.startswith('sidestep-') for p in paths) else 'budget-oneway-audit.json' if any(p.name.startswith('budget-') for p in paths) else 'passage-oneway-audit.json' if any(p.name.startswith('passage-') for p in paths) else 'gap-oneway-audit.json')).write_text(json.dumps(report,indent=2)+'\n')
    for run in report['runs']:print(run['run'],json.dumps(run['groups']),'min gap',run['all_frame_min_live_centre_gap_m'])
