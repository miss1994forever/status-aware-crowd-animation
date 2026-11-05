"""Compare the specific 1M/8H encounter; labels are offline diagnostics only."""
import csv,json,math,sys
from collections import defaultdict
from pathlib import Path

def angle(x,z,gx,gz):
    return math.degrees(math.acos(max(-1,min(1,(x*gx+z*gz)/max(1e-9,math.hypot(x,z)*math.hypot(gx,gz)))))) if math.hypot(x,z)>.01 else 0

def audit(run):
    groups=defaultdict(dict)
    for r in csv.DictReader((run/'motion.csv').open()):groups[int(r['frame'])][int(r['id'])]=r
    goals={}
    for r in csv.DictReader((run/'telemetry.csv').open()):
        if r['journey_phase']=='0':goals[int(r['id'])]=(float(r['destination_x']),float(r['destination_z']))
    pairs=[]
    for f,rs in groups.items():
        if 1 not in rs or 8 not in rs or any(rs[i]['journey_phase']!='0' for i in [1,8]):continue
        a,b=rs[1],rs[8];dist=math.hypot(float(a['x'])-float(b['x']),float(a['z'])-float(b['z']))
        if float(a['time'])>1:pairs.append((dist,f,float(a['time'])))
    nearest=min(pairs)
    def summary(frames):
        result={}
        for actor in [1,8]:
            speeds=[];angles=[];hold=slow=0.;samples=0
            for f in frames:
                r=groups[f][actor];vx,vz=float(r['input_x']),float(r['input_z']);speed=math.hypot(vx,vz)
                gx,gz=goals[actor];gx-=float(r['x']);gz-=float(r['z']);dt=float(r['dt'])
                speeds.append(speed);angles.append(angle(vx,vz,gx,gz));hold+=dt*int(r['facing_hold']);slow+=dt*(speed<.5);samples+=1
            result[str(actor)]=dict(samples=samples,mean_command_speed=sum(speeds)/max(1,len(speeds)),mean_command_goal_angle=sum(angles)/max(1,len(angles)),hold_s=hold,slow_command_s=slow)
        return result
    fixed=[f for d,f,t in pairs if 4<=t<=8]
    encounter=[f for d,f,t in pairs if d<2]
    return dict(run=run.name,closest_distance=nearest[0],closest_time=nearest[2],fixed_4to8s=summary(fixed),within_2m=summary(encounter))

if __name__=='__main__':
    paths=[Path(x) for x in sys.argv[1:]];r=dict(runs=[audit(p) for p in paths],qualification='Command speeds/deviations, not measured physical speeds; fixed-time and within2m windows differ after feedback. Root centre distance does not guarantee mesh clearance.')
    (paths[0].parent/'priority-pair-audit.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(r,indent=2))
