"""Measured source-root facing and animation selections, not a naturalness score."""
import csv
import json
import io
import math
import sys
from collections import Counter,defaultdict
from pathlib import Path


def percentile(values,p):
    values=sorted(values)
    return values[min(len(values)-1,int(p*len(values)))] if values else 0


def angle_delta(a,b):return (a-b+180)%360-180


def read(path):
    groups=defaultdict(list)
    text=(path/'motion.csv').read_text()
    if not text.endswith('\n'):text=text.rsplit('\n',1)[0]+'\n'
    for row in csv.DictReader(io.StringIO(text)):
        r={k:float(v) if k!='clip_name' else v for k,v in row.items()};groups[int(r['id'])].append(r)
    actors={}
    for actor,rows in groups.items():
        samples=[r for r in rows if r['journey_phase']==0]
        clips=Counter(r['clip_name'] for r in samples)
        rates=[];lateral_s=hold_s=0;hold_run=longest_hold=0;window_turn=0;window_rates=[]
        for a,b in zip(samples,samples[1:]):
            if b['frame']!=a['frame']+1:continue
            dt=b['time']-a['time'];speed=math.hypot(b['x']-a['x'],b['z']-a['z'])/dt
            if b['facing_hold']:
                hold_s+=dt;hold_run+=dt;longest_hold=max(longest_hold,hold_run)
            else:hold_run=0
            turn=abs(angle_delta(b['sim_yaw'],a['sim_yaw']))
            if speed>.2:
                rates.append(turn/dt)
                velocity_yaw=math.degrees(math.atan2(b['x']-a['x'],b['z']-a['z']))
                slip=abs(angle_delta(velocity_yaw,b['sim_yaw']))
                if 15<=slip<=70:lateral_s+=dt
            if 8<=b['time']<=14:
                window_turn+=turn;window_rates.append(turn/dt)
        actors[actor]=dict(samples=len(samples),selected_clips=dict(clips),
            source_strafe_fraction=clips['strafe']/len(samples),hold_s=hold_s,longest_hold_s=longest_hold,
            measured_oblique_motion_s=lateral_s,moving_yaw_rate_p95_deg_s=percentile(rates,.95),
            moving_yaw_rate_p99_deg_s=percentile(rates,.99),max_moving_yaw_rate_deg_s=max(rates,default=0),
            yaw_travel_8_to_14s_deg=window_turn,yaw_rate_p95_8_to_14s=percentile(window_rates,.95))
    return dict(run=path.name,runtime=json.loads((path/'runtime-config.json').read_text()),actors=actors)


if __name__=='__main__':
    paths=[Path(p) for p in sys.argv[1:]]
    report=dict(runs=[read(p) for p in paths],qualification='Native simulation-root facing, not head gaze. Oblique motion: measured speed>0.2m/s and root-facing/velocity angle 15–70deg. Clip selections alone do not prove lateral footwork or naturalness. Feedback trajectories diverge.')
    (paths[0].parent/'sidestep-motion-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    for run in report['runs']:print(run['run'],'actor3',json.dumps(run['actors'][3]))
