"""Audit status-conditioned space inputs and paired fixed-expression diagnostics."""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def read(path):
    config = json.loads((path/'config.json').read_text())
    runtime = json.loads((path/'runtime-config.json').read_text())
    rows = [{k:float(v) for k,v in row.items()} for row in csv.DictReader((path/'telemetry.csv').open())]
    groups = defaultdict(list)
    for row in rows:
        groups[int(row['id'])].append(row)
    actors = {}
    for actor, samples in groups.items():
        expected = (actor%3)*.5 if config['statusPattern']=='cycle' else actor%2 if config['statusPattern']=='low-high' else 1-actor%2
        if any(row['status'] != expected for row in samples):
            raise ValueError('Status preset not applied')
        if any(not 0 <= row['social_weight'] <= .50001 for row in samples):
            raise ValueError('Observation weighting exceeded cap')
        actors[actor] = dict(own_status=expected, arrivals=int(samples[-1]['arrivals']),
            desired_gap_range=[min(r['social_gap'] for r in samples),max(r['social_gap'] for r in samples)],
            effective_estimate_range=[min(r['social_estimate'] for r in samples),max(r['social_estimate'] for r in samples)],
            max_observation_weight=max(r['social_weight'] for r in samples),
            progress_weight_range=[min(r['social_progress_weight'] for r in samples),max(r['social_progress_weight'] for r in samples)])
    fixtures=json.loads((path/'social-fixtures.json').read_text())['fixtures']
    if abs(fixtures[0]['inputX']-fixtures[1]['inputX'])<.01 or abs(fixtures[2]['inputX']-fixtures[3]['inputX'])<.01:
        raise ValueError('Controlled fixture inputs do not affect actual command')
    if runtime['build'] not in ('social-space-v4','social-space-v5','social-space-v6','social-space-v7') or runtime['statusPattern']!=config['statusPattern'] or runtime['fixedExpression']!=config['fixedExpression']:
        raise ValueError('Runtime/config mismatch')
    return dict(run=path.name,completed=(path/'finished.txt').exists(),spatial=config['spatial'],
        status_pattern=config['statusPattern'],fixed_expression=config['fixedExpression'],actors=actors),rows


if __name__=='__main__':
    paths=[Path(p) for p in sys.argv[1:]]
    data=[read(p) for p in paths]
    comparisons=[]
    for index in range(1,min(len(data),3)):
        a={(int(r['frame']),int(r['id'])):r for r in data[0][1]}
        b={(int(r['frame']),int(r['id'])):r for r in data[index][1]}
        keys=a.keys()&b.keys()
        comparisons.append(dict(a=paths[0].name,b=paths[index].name,
            same_frame_actor_keys=a.keys()==b.keys(),
            max_position_difference_m=max(math.hypot(a[k]['x']-b[k]['x'],a[k]['z']-b[k]['z']) for k in keys),
            max_arm_parameter_difference_deg=max(abs(a[k]['arm_deg']-b[k]['arm_deg']) for k in keys if a[k]['pose_updates']>0 and b[k]['pose_updates']>0),
            max_lowering_parameter_difference_m=max(abs(a[k]['lowering']-b[k]['lowering']) for k in keys if a[k]['pose_updates']>0 and b[k]['pose_updates']>0)))
    result=dict(runs=[r[0] for r in data],paired_diagnostics=comparisons,
        qualification='Engineering input/behavior sensitivity only. Fixed-expression runs freeze parameters, not later locomotion poses; feedback trajectories diverge. No validated status recognition or perceived hierarchy claim.')
    (paths[0].parent/'social-space-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
