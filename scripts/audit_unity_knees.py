"""Compare per-frame source/output knees in the source pelvis frame.

Threshold events are diagnostics, not a validated measure of perceived popping.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def vector(row, prefix):
    return tuple(row[prefix + c] for c in 'xyz')


def distance(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def percentile(values, p):
    values = sorted(values)
    if not values:
        return 0
    f = (len(values)-1)*p
    lo = int(f)
    return values[lo] + (values[min(lo+1, len(values)-1)]-values[lo])*(f-lo)


def read(path):
    rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader((path/'knees.csv').open())]
    groups = defaultdict(list)
    for row in rows:
        groups[int(row['id'])].append(row)
    steps, raw_steps, final_steps, offsets, events = [], [], [], [], []
    actors = {}
    for actor, samples in groups.items():
        own_steps = []
        for leg in 'lr':
            previous = None
            for sample in samples:
                raw, final = vector(sample, 'raw_'+leg), vector(sample, 'out_'+leg)
                offset = tuple(b-a for a, b in zip(raw, final))
                offsets.append(distance(offset, (0, 0, 0)))
                if previous is not None and sample['frame'] == previous[0]['frame']+1:
                    step = distance(offset, previous[3])
                    steps.append(step);own_steps.append(step)
                    raw_steps.append(distance(raw, previous[1]));final_steps.append(distance(final, previous[2]))
                    if step > .03:
                        events.append(dict(id=actor, leg=leg, time=sample['time'], frame=int(sample['frame']), added_step_m=step))
                previous = sample, raw, final, offset
        actors[actor] = dict(status=samples[-1]['status'], samples=len(samples),
                            p99_added_step_m=percentile(own_steps, .99), max_added_step_m=max(own_steps, default=0))
    result = dict(run=path.name, completed=(path/'finished.txt').exists(),
                  lower_policy=int(rows[-1]['lower_policy']), actor_count=len(groups),
                  source_step_p99_m=percentile(raw_steps, .99), final_step_p99_m=percentile(final_steps, .99),
                  added_step_p99_m=percentile(steps, .99), added_step_max_m=max(steps, default=0),
                  added_offset_p95_m=percentile(offsets, .95), added_step_events_over_03m=len(events),
                  max_foot_target_error_m=max(r['foot_error'] for r in rows),
                  largest_events=sorted(events, key=lambda x:x['added_step_m'], reverse=True)[:15], actors=actors)
    return result, {(int(r['frame']), int(r['id'])): r for r in rows}


if __name__ == '__main__':
    paths = [Path(p) for p in sys.argv[1:]]
    data = [read(p) for p in paths]
    result = dict(runs=[x[0] for x in data], qualification='Added knee displacement steps only; foot-target error is not sliding, and event counts do not prove naturalness.')
    result['source_comparison'] = []
    for index in range(1, len(data)):
        a, b = data[0][1], data[index][1]
        keys = a.keys() & b.keys()
        max_source = max((distance(vector(a[k], 'raw_'+leg), vector(b[k], 'raw_'+leg)) for k in keys for leg in 'lr'), default=0)
        result['source_comparison'].append(dict(a=paths[0].name, b=paths[index].name, same_sample_keys=a.keys()==b.keys(), max_raw_knee_difference_m=max_source))
    output = paths[0].parent/('social-knee-audit.json' if all(p.name.startswith('social-') for p in paths) else 'knee-comparison.json')
    output.write_text(json.dumps(result, indent=2)+'\n')
    for r in result['runs']:
        print(r['run'], 'policy', r['lower_policy'], 'added step p99/max', r['added_step_p99_m'], r['added_step_max_m'], 'events >3cm', r['added_step_events_over_03m'], 'foot error', r['max_foot_target_error_m'])
    print(json.dumps(result['source_comparison'], indent=2))
