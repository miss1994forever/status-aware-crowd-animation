"""Compare sampled crowd exposure and progress, grouped by the actor's own preset."""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def audit(path):
    frames = defaultdict(list)
    rows = list(csv.DictReader((path/'telemetry.csv').open()))
    for row in rows:
        frames[int(row['frame'])].append({k: float(v) for k, v in row.items()})
    actors = defaultdict(list)
    for group in frames.values():
        for row in group:
            density = [math.exp(-((row['x']-other['x'])**2+(row['z']-other['z'])**2)/(2*1.6**2))
                       for other in group if row['id'] != other['id']]
            # Actual sampled positions, separate from the planner's predicted cost.
            row['actual_exposure'] = max(0, sum(density)-max(density, default=0)-.35)
            actors[int(row['id'])].append(row)
    result = {}
    for actor, samples in actors.items():
        result[actor] = dict(status=samples[-1]['status'], arrivals=int(samples[-1]['arrivals']),
            first_arrival_s=next((r['time'] for r in samples if r['arrivals'] >= 1), None),
            mean_sampled_exposure=sum(r['actual_exposure'] for r in samples)/len(samples),
            low_command_fraction=sum(math.hypot(r['input_x'], r['input_z']) < .4 for r in samples)/len(samples),
            min_gap=samples[-1]['min_frame_gap'])
    groups = {}
    for status in (0, .5, 1):
        members = [r for r in result.values() if r['status'] == status]
        groups[status] = dict(actors=len(members),
            mean_exposure=sum(r['mean_sampled_exposure'] for r in members)/len(members),
            mean_first_arrival_s=sum(r['first_arrival_s'] for r in members)/len(members) if all(r['first_arrival_s'] is not None for r in members) else None,
            arrivals=[r['arrivals'] for r in members])
    return dict(run=path.name, runtime=json.loads((path/'runtime-config.json').read_text()), actors=result, groups=groups)


if __name__ == '__main__':
    paths = [Path(p) for p in sys.argv[1:]]
    report = dict(runs=[audit(p) for p in paths],
        qualification='Same seed, feedback trajectories differ. Sampled geometric exposure is an engineering proxy, not perceived discomfort or a causal estimate of human status behavior.')
    (paths[0].parent/('social-flow-preference-audit.json' if any(p.name.startswith('social-flow-') for p in paths) else 'social-crowd-preference-audit.json')).write_text(json.dumps(report, indent=2)+'\n')
    for run in report['runs']:
        print(run['run'], json.dumps(run['groups']))
