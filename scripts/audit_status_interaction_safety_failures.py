"""Targeted diagnosis of saved failure states and common motion cost."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_status_interaction_lab import DATA,OUT,save

def main():
    rows=[]
    for path in sorted((OUT/'runs').glob('*.json')):
        if not ('corridor' in path.name or 'stress' in path.name):continue
        r=json.loads(path.read_text());fs=r['frames'];n=len(fs[0]['agents']);goals=np.array(r['spec']['goals'])
        last=np.array([a['pos'] for a in fs[-1]['agents']]);remaining=np.linalg.norm(last-goals,axis=-1);held=[]
        for i in range(n):
            seq=[a['agents'][i]['hold'] for a in fs];longest=cur=0
            for v in seq:cur=cur+1 if v else 0;longest=max(longest,cur)
            ds=[d for d in r['decisions'] if d['id']==i]
            held.append(dict(id=i,remaining=float(remaining[i]),arrived=remaining[i]<.22,longest_hold_seconds=longest*.05,
                no_safe_candidate_steps=sum(d['safe_count']==0 for d in ds),min_safe_candidates=min((d['safe_count'] for d in ds),default=0),
                reciprocal_infeasible_steps=sum(not d.get('orca_feasible',True) for d in ds)))
        rows.append(dict(key=path.stem,agents=held,note='No safe candidate combines safety/cone gates; candidate detailed costs were not saved, so this does not uniquely identify a specific gate. Walls enter body checks, not reciprocal velocity halfplanes.'))
    # numpy booleans cast for JSON boundary.
    for r in rows:
        for a in r['agents']:a['arrived']=bool(a['arrived'])
    save(DATA/'failure-diagnosis.json',rows);print('Failure cases',len(rows))
if __name__=='__main__':main()
