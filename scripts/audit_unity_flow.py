"""Sampled waiting and command continuity, not animation naturalness certification."""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def read(path):
    actors=defaultdict(list)
    for row in csv.DictReader((path/'telemetry.csv').open()):
        actors[int(row['id'])].append({k:float(v) for k,v in row.items()})
    result={}
    for actor, rows in actors.items():
        commanded_still=actual_still=0
        longest=episode=0
        angles=[]
        for a,b in zip(rows,rows[1:]):
            dt=b['time']-a['time']
            actual=math.hypot(b['x']-a['x'],b['z']-a['z'])/dt
            if actual<.1:
                actual_still+=dt;episode+=dt;longest=max(longest,episode)
            else:episode=0
            sa=math.hypot(a['input_x'],a['input_z']);sb=math.hypot(b['input_x'],b['input_z'])
            if sb<.1:commanded_still+=dt
            if sa>.4 and sb>.4 and a['arrivals']==b['arrivals']:
                cosine=(a['input_x']*b['input_x']+a['input_z']*b['input_z'])/(sa*sb)
                angles.append(math.degrees(math.acos(max(-1,min(1,cosine)))))
        result[actor]=dict(status=rows[-1]['status'],arrivals=int(rows[-1]['arrivals']),
            actual_still_s=actual_still,longest_sampled_still_s=longest,commanded_still_s=commanded_still,
            command_turns_over_75deg=sum(a>75 for a in angles),
            command_turn_p95_deg=sorted(angles)[min(len(angles)-1,int(.95*len(angles)))] if angles else 0,
            side_flips=int(rows[-1]['side_flips']),rapid_side_flips=int(rows[-1]['rapid_side_flips']))
    low=[r for r in result.values() if r['status']==0]
    return dict(run=path.name,actors=result,low_status=dict(
        actual_still_total_s=sum(r['actual_still_s'] for r in low),
        commanded_still_total_s=sum(r['commanded_still_s'] for r in low),
        longest_sampled_still_s=max(r['longest_sampled_still_s'] for r in low),
        command_turns_over_75deg=sum(r['command_turns_over_75deg'] for r in low),
        arrivals=[r['arrivals'] for r in low]))


if __name__=='__main__':
    paths=[Path(p) for p in sys.argv[1:]]
    result=dict(runs=[read(p) for p in paths],qualification='Approx. 0.25s samples; speed below 0.1m/s is stationary proxy. Direction changes exclude near-zero commands. Different trajectories, no perceived naturalness claim.')
    (paths[0].parent/'social-flow-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    for run in result['runs']:print(run['run'],json.dumps(run['low_status']))
