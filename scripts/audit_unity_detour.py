"""Sampled first-trip route length and late motion away from the destination."""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


def read(path):
    actors=defaultdict(list)
    for r in csv.DictReader((path/'telemetry.csv').open()):actors[int(r['id'])].append({k:float(v) for k,v in r.items()})
    high_exit=max(r[-1]['departure_time'] for r in actors.values() if r[-1]['status']==1)
    result={}
    for i,rows in actors.items():
        trip=[]
        for r in rows:
            trip.append(r)
            if r['arrivals']>=1:break
        length=sum(math.hypot(b['x']-a['x'],b['z']-a['z']) for a,b in zip(trip,trip[1:]))
        late_away=0
        for a,b in zip(trip,trip[1:]):
            da=math.hypot(a['x']-a['destination_x'],a['z']-a['destination_z'])
            db=math.hypot(b['x']-b['destination_x'],b['z']-b['destination_z'])
            if a['time']>=high_exit and db>da+.02:late_away+=b['time']-a['time']
        result[i]=dict(status=rows[-1]['status'],arrival_s=rows[-1]['arrival_time'],exit_s=rows[-1]['departure_time'],sampled_first_trip_path_m=length,late_away_after_all_high_exited_s=late_away,
            minimum_discretion_weight=min(r.get('discretion_weight',1) for r in trip))
    return dict(run=path.name,actors=result,last_high_exit_s=high_exit,
        low_mean_arrival_s=sum(r['arrival_s'] for r in result.values() if r['status']==0)/4)


if __name__=='__main__':
    paths=[Path(p) for p in sys.argv[1:]]
    report=dict(runs=[read(p) for p in paths],qualification='Approx. 0.25s sampled route lengths. High-status exit time is used only for offline diagnosis. Budget control uses only own travelled distance and own goal; no hidden neighbour labels.')
    (paths[0].parent/'budget-detour-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    for run in report['runs']:print(run['run'],json.dumps({i:run['actors'][i] for i in (0,3)}),'low mean',run['low_mean_arrival_s'])
