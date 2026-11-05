"""Cross-check raw lateral samples and rendered-root lateral travel after startup."""
import csv,json,math,sys
from collections import defaultdict
from pathlib import Path

def delta(a,b):return (a-b+180)%360-180

def read(run,source):
    groups=defaultdict(list)
    for r in csv.DictReader((run/'motion.csv').open()):groups[r['id']].append(r)
    result={}
    for actor,rows in groups.items():
        source_s=actual_s=both_s=longest=streak=strafe_s=0.;events=[];start=None;previous=None
        for r in rows:
            raw=source[r['source_frame']]
            assert (raw['clip_index'],raw['clip_name'])==(r['clip_index'],r['clip_name'])
            if float(r['time'])<1 or r['journey_phase']!='0':previous=r;continue
            dt=float(r['dt']);x,z=float(raw['local_x']),float(raw['local_z'])
            angle=abs(math.degrees(math.atan2(x,z)));src=math.hypot(x,z)>.2 and 70<angle<=110
            actual=False
            if previous and int(previous['frame'])+1==int(r['frame']):
                dx,dz=float(r['x'])-float(previous['x']),float(r['z'])-float(previous['z'])
                vel=math.degrees(math.atan2(dx,dz));a=abs(delta(vel,float(r['sim_yaw'])))
                actual=math.hypot(dx,dz)/dt>.2 and 70<a<=110
            source_s+=dt*src;actual_s+=dt*actual;both_s+=dt*(src and actual)
            strafe_s+=dt*(r['clip_name']=='strafe')
            if src and actual:
                if start is None:start=float(r['time'])
                streak+=dt;longest=max(longest,streak)
            else:
                if streak>=.15:events.append(dict(start=start,duration=streak))
                start=None;streak=0
            previous=r
        if streak>=.15:events.append(dict(start=start,duration=streak))
        result[actor]=dict(source_lateral_s=source_s,actual_lateral_s=actual_s,corroborated_lateral_s=both_s,longest_corroborated_s=longest,strafe_clip_s=strafe_s,corroborated_episodes_over_150ms=events)
    return dict(run=run.name,actors=result)

if __name__=='__main__':
    table={r['source_frame']:r for r in csv.DictReader(Path(sys.argv[1]).open())}
    runs=[Path(p) for p in sys.argv[2:]]
    report=dict(runs=[read(p,table) for p in runs],qualification='First trip after 1s; lateral angle70–110deg and speed>0.2m/s in raw source and actual rendered-root travel. No validated foot contact/sliding/naturalness metric.')
    (runs[-1].parent/'lateral-corroboration-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    for r in report['runs']:
        print(r['run'],'corroborated total',sum(x['corroborated_lateral_s'] for x in r['actors'].values()))
        print('2H',r['actors']['2'])
