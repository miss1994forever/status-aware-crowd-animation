"""Read-only adaptation of crowd chooser with constrained synthesis.

The navigation objective/candidates/horizon/margins are unchanged. Only the
common motion adapter and source-relative cone gate are added.
"""
import math
import numpy as np
from src.crowd_mobility_lab.controller import candidates,root_only,DEFAULT
from src.crowd_mobility_lab.reciprocal import preferred_velocity,halfplanes,project,velocity
from src.predictive_motion_lab.motion import wrap
from src.predictive_motion_lab.geometry import box,box_gap,wall_boxes
from .motion import rollout,MAX_SOURCE_ANGLE

def choose(lib,s,visible,walls,variant,cfg,log=False):
    pref,risk=preferred_velocity(s,visible,cfg['preferred_speed'],0 if variant in ('reciprocal','no_flow','goal_only','long_cv') else cfg['circulation'])
    normals,bounds,ids=halfplanes(s,visible,cfg['tau'])
    use_reciprocity=variant not in ('no_reciprocity','goal_only')
    desired,orca_feasible=project(pref,normals,bounds,float(lib.speeds.max()*1.15)) if use_reciprocity else (pref,True)
    opts=candidates(lib,s,desired,cfg);total=len(opts)
    if not total:return None,{'safe_count':0,'candidate_count':0,'pool_count':0,'desired':desired.tolist(),'reason':'no_reachable_candidates','candidates':[],'traces':[]}
    ci=opts[:,0].astype(int)
    pose_error=np.sqrt(np.mean((lib.sample(ci,(s.phase+opts[:,3])%1)-s.pose)**2,axis=(1,2)))
    coarse=cfg['tracking_weight']*np.sum((root_only(lib,s,opts)-desired)**2,axis=1)+2*pose_error
    indices=np.argsort(coarse,kind='stable')[:cfg['budget']];opts=opts[indices];ci=ci[indices];pose_error=pose_error[indices]
    times=np.arange(1,21)*.05;p=rollout(lib,s,opts,times);shape=box(p['pose'],p['pos'],p['yaw'])
    gap=np.full((20,len(opts)),10.)
    for wb in wall_boxes(walls):gap=np.minimum(gap,box_gap(shape,wb))
    for o in visible:
        if o.id==s.id or np.linalg.norm(o.pos-s.pos)>3.5:continue
        ob=box(o.pose,o.pos+times[:,None]*velocity(o),np.full(20,o.yaw))
        gap=np.minimum(gap,box_gap(shape,tuple(x[:,None] for x in ob)))
    horizon=1. if variant=='long_cv' else cfg['geometry_horizon']
    minimum=gap[:round(horizon/.05)].min(0)
    modification=np.linalg.norm(p['pose']-p['source'],axis=-1).max(axis=(0,2))
    feasible=(minimum>=cfg['margin'])&(modification<=cfg['deformation_limit'])&(p['cone_error'].max(0)<=MAX_SOURCE_ANGLE+1e-8)
    displacement=p['pos'][-1]-s.pos
    tracking=np.sum((displacement-desired)**2,axis=1)
    violations=np.maximum(bounds[None]-displacement@normals.T,0)
    orca=violations.max(1,initial=0)**2 if use_reciprocity else np.zeros(len(opts))
    continuity=2*pose_error+.02*(ci!=s.clip)+.06*np.abs(wrap(lib.angles[ci]-s.travel))
    progress=np.linalg.norm(p['pos'][-1]-s.goal,axis=1)-np.linalg.norm(s.pos-s.goal)
    score=cfg['tracking_weight']*tracking+cfg['orca_weight']*orca+continuity+.2*progress
    safe=np.where(feasible)[0];selected=int(safe[np.argmin(score[safe])]) if len(safe) else None
    entries=[];traces=[]
    if log:
        for i in range(len(opts)):
            entries.append({'clip':lib.ids[ci[i]],'scale':float(opts[i,1]),'steer':float(opts[i,2]),'phase_offset':float(opts[i,3]),'clearance':float(minimum[i]),
                'feasible':bool(feasible[i]),'tracking':float(tracking[i]),'orca':float(orca[i]),'continuity':float(continuity[i]),'progress':float(progress[i]),
                'deformation':float(modification[i]),'score':float(score[i]),'selected':i==selected,'reason':'safe' if feasible[i] else 'body_margin_or_transition'})
        ii={int(np.argmin(score)),int(np.argmax(minimum))}
        if selected is not None:ii.add(selected)
        for i in sorted(ii):traces.append({'clip':lib.ids[ci[i]],'selected':i==selected,'feasible':bool(feasible[i]),'pos':p['pos'][:,i].round(6).tolist(),
            'yaw':p['yaw'][:,i].tolist(),'center':shape[0][:,i].tolist(),'half':shape[2][:,i].tolist()})
    return (opts[selected:selected+1] if selected is not None else None),{'safe_count':len(safe),'candidate_count':len(opts),'pool_count':total,'desired':desired.tolist(),
        'preferred':pref.tolist(),'flow_risk':risk,'orca_feasible':orca_feasible,'neighbor_ids':ids,'normals':normals.tolist(),'bounds':bounds.tolist(),'candidates':entries,'traces':traces}

