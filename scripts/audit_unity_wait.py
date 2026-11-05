"""Describe zero-input episodes and turn behavior; no semantic waiting classifier."""
import csv,json,math,sys
from pathlib import Path

def delta(a,b):return abs((a-b+180)%360-180)

def audit(run):
    rows=[r for r in csv.DictReader((run/'motion.csv').open()) if r['id']=='7' and r['journey_phase']=='0']
    episodes=[];start=None
    for i,r in enumerate(rows):
        stopped=math.hypot(float(r['input_x']),float(r['input_z']))<.01
        if stopped and start is None:start=i
        if not stopped and start is not None:
            samples=rows[start:i];end=rows[i];following=[x for x in rows[i:] if float(x['time'])<=float(end['time'])+.5]
            turn=sum(delta(float(a['sim_yaw']),float(b['sim_yaw'])) for a,b in zip(following,following[1:]))
            episodes.append(dict(start=float(samples[0]['time']),end=float(end['time']),duration=sum(float(x['dt']) for x in samples),start_yaw=float(samples[0]['sim_yaw']),end_yaw=float(samples[-1]['sim_yaw']),next_input_yaw=math.degrees(math.atan2(float(end['input_x']),float(end['input_z']))),yaw_travel_first_half_second_after=turn))
            start=None
    selected=[x for x in rows if 3.5<=float(x['time'])<=7.5]
    total=sum(delta(float(a['sim_yaw']),float(b['sim_yaw'])) for a,b in zip(selected,selected[1:]))
    return dict(run=run.name,episodes=episodes,total_yaw_travel_3_5to7_5=total,zero_input_s=sum(float(x['dt']) for x in selected if math.hypot(float(x['input_x']),float(x['input_z']))<.01))

if __name__=='__main__':
    runs=[Path(p) for p in sys.argv[1:]];r=dict(runs=[audit(p) for p in runs],qualification='Zero translation commands, not necessarily zero animation root motion. Feedback changes episode timings; centre clearance and naturalness need separate checks.')
    (runs[0].parent/'wait-goal-turn-audit.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
