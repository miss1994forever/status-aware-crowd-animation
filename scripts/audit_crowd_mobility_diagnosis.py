"""Counterfactual candidate feasibility on actual frozen failed states."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.controller import State,options,rollout
from src.predictive_motion_lab.geometry import box,box_gap


def states_at(run,index,lib):
    result=[];f=run['frames'][index];before=run['frames'][max(0,index-1)]
    for a,b,g in zip(f['agents'],before['agents'],run['spec']['goals']):
        reference=lib.ids.index(['M01','M02','M03'][a['id']%3])
        velocity=(np.array(a['pose'])-np.array(b['pose']))/.05 if index else lib.velocity(reference,a['phase'],1/lib.periods[reference])
        result.append(State(a['id'],np.array(a['pos']),np.array(g),a['yaw'],a['travel'],a['speed'],lib.ids.index(a['clip']),reference,a['phase'],np.array(a['pose']),velocity,a['arrived'],a['hold']))
    return result


def main():
    out=ROOT/'data/crowd-mobility-lab';out.mkdir(parents=True,exist_ok=True)
    path=ROOT/'outputs/predictive-motion-lab/runs/train_shared-10-None-13_G_0.json';run=json.loads(path.read_text())
    lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()));rows=[]
    times=np.arange(1,21)*.05
    for t in [0,1,2,2.4,3,5,10,20]:
        states=states_at(run,round(t/.05),lib)
        for s in states:
            original=options(lib,s,'G')
            expanded=[]
            for c in np.unique(original[:,0]).astype(int):
                for scale in [.5,.8,1.15]:
                    for steer in [-1.8,-1.35,-.9,-.45,0,.45,.9,1.35,1.8]:
                        expanded.append([c,scale,steer,0])
            for name,opts in [('original',original),('expanded_controls',np.array(expanded))]:
                p=rollout(lib,s,opts,times);shape=box(p['pose'],p['pos'],p['yaw'])
                deformed=np.linalg.norm(p['pose']-p['source'],axis=-1).max(axis=(0,2))>.4
                gaps={k:np.full((20,len(opts)),10.) for k in ['constant_velocity','stationary_neighbors']}
                for o in states:
                    if o.id==s.id or np.linalg.norm(o.pos-s.pos)>3.5:continue
                    v=np.zeros(2) if o.hold or o.arrived else o.speed*np.array([np.sin(o.yaw+o.travel),np.cos(o.yaw+o.travel)])
                    for predictor in gaps:
                        pos=o.pos+times[:,None]*(v if predictor=='constant_velocity' else np.zeros(2))
                        ob=box(o.pose,pos,np.full(20,o.yaw))
                        gaps[predictor]=np.minimum(gaps[predictor],box_gap(shape,tuple(x[:,None] for x in ob)))
                rows.append({'t':t,'id':s.id,'options':name,'count':len(opts),'speed':s.speed,'hold':s.hold,
                    'deformation_rejected':int(deformed.sum()),
                    **{predictor+'_safe_'+str(h):int(((gap[:h].min(0)>=.005)&~deformed).sum()) for predictor,gap in gaps.items() for h in [4,20]},
                    'current_min_center_distance':min(float(np.linalg.norm(o.pos-s.pos)) for o in states if o.id!=s.id)})
    report={'source':str(path.relative_to(ROOT)),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':rows,
            'scope':'Same observed states; stationary predictor is diagnostic, not a deployable collision-free policy; .2/1 second feasibility. Expanded control pool omits phase alternatives and is not a strict superset.'}
    (out/'old-g-diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
    for t in [0,1,2,2.4,3,5,10,20]:
        print(t,[(name,{k:sum(r[k]>0 for r in rows if r['t']==t and r['options']==name) for k in ['constant_velocity_safe_20','constant_velocity_safe_4','stationary_neighbors_safe_20']}) for name in ['original','expanded_controls']],flush=True)


if __name__=='__main__':main()
