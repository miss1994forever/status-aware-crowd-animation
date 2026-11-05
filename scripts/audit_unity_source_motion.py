"""Classify selected raw source motion separately from output turning lag."""
import csv,json,math,sys
from pathlib import Path
from collections import defaultdict

def audit(source, runs):
    table={int(r['source_frame']):r for r in csv.DictReader(source.open())}
    result=[]
    for run in runs:
        stats=defaultdict(lambda:dict(samples=0,source_moving_s=0.,source_oblique_s=0.,source_lateral_s=0.,hold_s=0.,hold_oblique_s=0.))
        for r in csv.DictReader((run/'motion.csv').open()):
            if int(r['journey_phase'])!=0:continue
            raw=table[int(r['source_frame'])]
            assert raw['clip_index']==r['clip_index'] and raw['clip_name']==r['clip_name'], 'Source database mismatch'
            x,z=float(raw['local_x']),float(raw['local_z'])
            angle=abs(math.degrees(math.atan2(x,z)))
            moving=math.hypot(x,z)>.2
            oblique=moving and 15<=angle<=70
            lateral=moving and 70<angle<=110
            dt=float(r['dt']);hold=int(r['facing_hold'])==1
            s=stats[r['id']];s['samples']+=1
            s['source_moving_s']+=dt*moving;s['source_oblique_s']+=dt*oblique;s['source_lateral_s']+=dt*lateral
            s['hold_s']+=dt*hold;s['hold_oblique_s']+=dt*(hold and oblique)
        result.append(dict(run=run.name,actors=dict(stats)))
    return dict(runs=result,source_map=str(source),qualification='Raw simulation-root velocity transformed into its source facing. Selected frames include turns/transitions; this does not prove foot contact, absence of sliding or perceived naturalness.')

if __name__=='__main__':
    source=Path(sys.argv[1]);runs=[Path(p) for p in sys.argv[2:]]
    r=audit(source,runs)
    (runs[0].parent/'sidestep-source-motion-audit.json').write_text(json.dumps(r,indent=2)+'\n')
    for run in r['runs']:print(run['run'], '3L',run['actors']['3'])
