"""Offline measured co-travel diagnostics. Hidden labels only group the audit."""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def read(path):
    frames=defaultdict(dict)
    for r in csv.DictReader((path/'telemetry.csv').open()):
        row={k:float(v) for k,v in r.items()};frames[int(row['frame'])][int(row['id'])]=row
    ordered=sorted(frames.values(),key=lambda g:next(iter(g.values()))['time'])
    pair_stats=defaultdict(lambda:dict(near_parallel_s=0,front_corridor_s=0,longest_near_parallel_s=0,episode=0))
    low_still=0;low_turns=0
    for prev,now in zip(ordered,ordered[1:]):
        dt=next(iter(now.values()))['time']-next(iter(prev.values()))['time']
        vel={i:((r['x']-prev[i]['x'])/dt,(r['z']-prev[i]['z'])/dt) for i,r in now.items()}
        for i,a in now.items():
            if a['journey_phase']<2 and a['status']==0 and math.hypot(*vel[i])<.1:low_still+=dt
            if a['status']==0 and a['journey_phase']<2 and a['arrivals']==prev[i]['arrivals']:
                old=prev[i];sa_cmd=math.hypot(old['input_x'],old['input_z']);sb_cmd=math.hypot(a['input_x'],a['input_z'])
                if sa_cmd>.4 and sb_cmd>.4:
                    dot=(old['input_x']*a['input_x']+old['input_z']*a['input_z'])/(sa_cmd*sb_cmd)
                    if math.degrees(math.acos(max(-1,min(1,dot))))>75:low_turns+=1
            for j,b in now.items():
                if a['status']!=0 or b['status']!=1:continue
                stat=pair_stats[f'{i}/{j}'];va,vb=vel[i],vel[j];sa,sb=math.hypot(*va),math.hypot(*vb)
                rel=(a['x']-b['x'],a['z']-b['z']);distance=math.hypot(*rel)
                aligned=sa>.3 and sb>.3 and (va[0]*vb[0]+va[1]*vb[1])/(sa*sb)>.7
                near=a['journey_phase']<2 and b['journey_phase']<2 and aligned and distance<2.5
                if near:
                    stat['near_parallel_s']+=dt;stat['episode']+=dt
                    stat['longest_near_parallel_s']=max(stat['longest_near_parallel_s'],stat['episode'])
                    along=(rel[0]*vb[0]+rel[1]*vb[1])/sb
                    lateral=abs(rel[0]*vb[1]-rel[1]*vb[0])/sb
                    if 0<along<2.5 and lateral<1.2:stat['front_corridor_s']+=dt
                else:stat['episode']=0
    for stat in pair_stats.values():del stat['episode']
    last=ordered[-1]
    return dict(run=path.name,pairs=dict(pair_stats),low_still_total_s=low_still,low_command_turns_over_75deg=low_turns,
        total_near_parallel_s=sum(s['near_parallel_s'] for s in pair_stats.values()),
        total_front_corridor_s=sum(s['front_corridor_s'] for s in pair_stats.values()),
        arrived=sum(r['arrivals']==1 for r in last.values()),exited=sum(r['journey_phase']==2 for r in last.values()),
        min_live_centre_gap_m=next(iter(last.values()))['min_frame_gap'])


if __name__=='__main__':
    paths=[Path(p) for p in sys.argv[1:]]
    report=dict(runs=[read(p) for p in paths],qualification='Approx. 0.25s position samples. Co-travel: speeds >0.3m/s, heading cosine >0.7, distance <2.5m. Front: additionally 0<ahead<2.5m and lateral<1.2m. True status only groups offline metrics; it is not a controller input. Feedback trajectories differ; no human-behavior validation.')
    (paths[0].parent/('budget-passage-audit.json' if any(p.name.startswith('budget-') for p in paths) else 'passage-audit.json')).write_text(json.dumps(report,indent=2)+'\n')
    for r in report['runs']:print(r['run'],'pair9/8',r['pairs']['9/8'],'all front/near',r['total_front_corridor_s'],r['total_near_parallel_s'],'still',r['low_still_total_s'],'gap',r['min_live_centre_gap_m'])
