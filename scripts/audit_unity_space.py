"""Spatial diagnostics from sampled centre positions; not mesh-collision or perception tests."""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def audit(path):
    if (path / 'INVALID.txt').exists():
        raise ValueError('Refusing invalidated run: ' + str(path))
    config = json.loads((path / 'config.json').read_text())
    rows = [{k: float(v) for k, v in row.items()}
            for row in csv.DictReader((path / 'telemetry.csv').open())]
    actors, frames = defaultdict(list), defaultdict(list)
    for row in rows:
        actors[int(row['id'])].append(row)
        frames[int(row['frame'])].append(row)
    distances = [math.hypot(a['x']-b['x'], a['z']-b['z'])
                 for group in frames.values() for i, a in enumerate(group) for b in group[i+1:]]
    per_actor = {}
    for actor, samples in actors.items():
        flips = sum(a['held_side'] * b['held_side'] < 0 for a, b in zip(samples, samples[1:]))
        per_actor[actor] = dict(
            arrivals=int(samples[-1]['arrivals']),
            path_m=sum(math.hypot(a['x']-b['x'], a['z']-b['z']) for a, b in zip(samples, samples[1:])),
            held_side_flips_sampled=flips,
            low_command_fraction=sum(math.hypot(r['input_x'], r['input_z']) < .4 for r in samples)/len(samples))
        if 'side_flips' in samples[-1]:
            per_actor[actor].update(side_flips_all_frames=int(samples[-1]['side_flips']),
                rapid_side_flips_all_frames=int(samples[-1]['rapid_side_flips']),
                safety_overrides_all_frames=int(samples[-1]['safety_overrides']))
        if 'guard_frames' in samples[-1]:
            per_actor[actor].update(guard_frames=int(samples[-1]['guard_frames']),
                max_sampled_guard_residual_mps=max(r['guard_residual'] for r in samples))
    spatial_rows = [r for r in rows if r['spatial_policy'] >= 1]
    return dict(run=path.name, config=config, completed=(path/'finished.txt').exists(),
                sampled_min_centre_distance_m=min(distances, default=None),
                all_frame_min_centre_distance_m=rows[-1].get('min_frame_gap'),
                sampled_pair_observations_below_060m=sum(d < .6 for d in distances),
                no_safe_candidate_fraction=(sum(r['safe_candidates'] == 0 for r in spatial_rows)/len(spatial_rows)) if spatial_rows else None,
                max_foot_target_error_m=max(r['foot_error'] for r in rows),
                actors=per_actor)


if __name__ == '__main__':
    paths = [Path(arg) for arg in sys.argv[1:]]
    result = dict(runs=[audit(path) for path in paths], qualification='Sampled centre distances can miss between-sample events and cannot certify mesh clearance, naturalness, or status.')
    output_name = 'social-geometry-audit.json' if all(p.name.startswith('social-') for p in paths) else 's1b-space-audit.json' if all(p.name.startswith('s1b-') for p in paths) else 's1-space-audit.json'
    (paths[0].parent/output_name).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
