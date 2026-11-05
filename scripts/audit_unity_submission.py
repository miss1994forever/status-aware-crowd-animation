"""Summarize integration telemetry; never substitutes for visual evaluation."""
import csv
import json
import math
import sys
from pathlib import Path

run = Path(sys.argv[1])
rows = list(csv.DictReader((run / 'telemetry.csv').open()))
actors = {}
for row in rows:
    actors.setdefault(row['id'], []).append({k: float(v) for k, v in row.items()})
summary = {}
for actor, samples in actors.items():
    path = sum(math.hypot(b['x']-a['x'], b['z']-a['z']) for a,b in zip(samples,samples[1:]))
    summary[actor] = dict(path_m=round(path,3), pose_updates=int(samples[-1]['pose_updates']),
        max_response=max(s['response'] for s in samples),
        max_foot_target_error_m=max(s['foot_error'] for s in samples),
        max_arm_deg=max(s['arm_deg'] for s in samples),
        observed_range=[min(s['observed'] for s in samples),max(s['observed'] for s in samples)],
        arrivals=int(samples[-1]['arrivals']))
result = dict(run=run.name, completed=(run/'finished.txt').exists(),
    simulated_seconds=max((r['time'] for a in actors.values() for r in a),default=0),
    actor_count=len(actors), actors=summary,
    qualification='Engineering telemetry only; no claim of naturalness or perceived status.')
(run/'audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
