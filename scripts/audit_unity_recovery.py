"""Audit task distance and waiting/movement choices, separately from animation quality."""
import csv,json,math,sys
from collections import defaultdict
from pathlib import Path

def audit(run):
    groups=defaultdict(list)
    for r in csv.DictReader((run/'motion.csv').open()):groups[int(r['id'])].append(r)
    telemetry=defaultdict(list)
    for r in csv.DictReader((run/'telemetry.csv').open()):telemetry[int(r['id'])].append(r)
    actors={}
    for i,rows in groups.items():
        final=telemetry[i][-1];first=telemetry[i][0];goal=(float(first['destination_x']),float(first['destination_z']))
        travelled=zero_s=slow_s=retreat_s=actual_still_s=0.;previous=None;max_extra=0.
        for r in rows:
            if r['journey_phase']!='0':continue
            x,z=float(r['x']),float(r['z']);vx,vz=float(r['input_x']),float(r['input_z']);speed=math.hypot(vx,vz);dt=float(r['dt'])
            if float(r['time'])>1:
                zero_s+=dt*(speed<.01);slow_s+=dt*(.01<=speed<.5)
                gx,gz=goal[0]-x,goal[1]-z
                retreat_s+=dt*(vx*gx+vz*gz<-.01)
            if previous and int(r['frame'])==int(previous['frame'])+1:
                d=math.hypot(x-float(previous['x']),z-float(previous['z']));travelled+=d
                actual_still_s+=dt*(float(r['time'])>1 and d/dt<.1)
            previous=r
        max_extra=max(float(r['detour_extra']) for r in telemetry[i] if r['journey_phase']=='0')
        actors[i]=dict(arrival_time=float(final['arrival_time']),departure_time=float(final['departure_time']),first_trip_path_m=float(final['first_trip_path']),measured_animation_root_path_m=travelled,zero_command_s=zero_s,slow_command_s=slow_s,retreat_command_s=retreat_s,measured_still_s=actual_still_s,max_detour_extra_m=max_extra)
    return dict(run=run.name,actors=actors)

if __name__=='__main__':
    paths=[Path(x) for x in sys.argv[1:]]
    report=dict(runs=[audit(p) for p in paths],qualification='Zero/slow input commands are not a semantic waiting state; actual stillness means root speed<0.1m/s. First trip; command durations exclude first1s. Path and arrival diagnostics do not prove animation naturalness.')
    (paths[0].parent/'recovery-route-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    for r in report['runs']:print(r['run'],'3L',r['actors'][3])
