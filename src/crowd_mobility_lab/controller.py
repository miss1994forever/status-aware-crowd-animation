"""Local reciprocal-guided body/action tracking. Reuses synthesis, not old chooser.

Only own goal/reference and visible neighbor pose/kinematics are used. Every
decision is made from the same snapshot. No actual neighbor plans are read.
"""
from dataclasses import replace
import math
import time
import numpy as np
from src.predictive_motion_lab import controller as old
from src.predictive_motion_lab.motion import wrap
from src.predictive_motion_lab.geometry import box,box_gap,wall_boxes
from src.expression_layer import personal_library
from .reciprocal import halfplanes,project,preferred_velocity,velocity


DEFAULT={'tau':3.,'circulation':1.2,'budget':64,'geometry_horizon':.2,'scales':[.5,.8,1.15],
         'steering_offsets':[-.6,-.3,0,.3,.6],'speed_warp_min':.4,'speed_warp_max':1.6,'margin':.015,
         'tracking_weight':4.,'orca_weight':20.,'deformation_limit':.4,'preferred_speed':1.}


def candidates(lib,s,desired,cfg):
    clips=np.where(np.abs(wrap(lib.angles-lib.angles[s.clip]))<=.7)[0]
    angle=math.atan2(desired[0],desired[1]) if np.linalg.norm(desired)>1e-7 else s.yaw+s.travel
    rows=[]
    # Desired root heading can deviate from goal heading; body still turns at
    # the old bounded rate and root follows body+source travel, no root snap.
    relative=wrap(angle-math.atan2(*(s.goal-s.pos)))
    for c in clips:
        ratio=s.speed/lib.speeds[c]
        if s.speed>.05 and not cfg['speed_warp_min']<=ratio<=cfg['speed_warp_max']:continue
        for scale in cfg['scales']:
            for offset in cfg['steering_offsets']:
                for phase in ([0] if c==s.clip else [-.08,0,.08]):rows.append([c,scale,relative+offset,phase])
    return np.array(rows)


def root_only(lib,s,opts):
    ci=opts[:,0].astype(int);speed=np.full(len(opts),s.speed);yaw=np.full(len(opts),s.yaw);travel=np.full(len(opts),s.travel);pos=np.repeat(s.pos[None],len(opts),axis=0)
    target=math.atan2(*(s.goal-s.pos))-lib.angles[ci]+opts[:,2]
    for _ in range(20):
        yaw+=np.clip(wrap(target-yaw),-.07,.07);travel+=np.clip(wrap(lib.angles[ci]-travel),-.09,.09)
        speed+=np.clip(lib.speeds[ci]*opts[:,1]-speed,-.06,.06)
        pos+=speed[:,None]*np.stack([np.sin(yaw+travel),np.cos(yaw+travel)],-1)*.05
    return pos-s.pos


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
    times=np.arange(1,21)*.05;p=old.rollout(lib,s,opts,times);shape=box(p['pose'],p['pos'],p['yaw'])
    gap=np.full((20,len(opts)),10.)
    for wb in wall_boxes(walls):gap=np.minimum(gap,box_gap(shape,wb))
    for o in visible:
        if o.id==s.id or np.linalg.norm(o.pos-s.pos)>3.5:continue
        ob=box(o.pose,o.pos+times[:,None]*velocity(o),np.full(20,o.yaw))
        gap=np.minimum(gap,box_gap(shape,tuple(x[:,None] for x in ob)))
    horizon=1. if variant=='long_cv' else cfg['geometry_horizon']
    minimum=gap[:round(horizon/.05)].min(0)
    modification=np.linalg.norm(p['pose']-p['source'],axis=-1).max(axis=(0,2))
    feasible=(minimum>=cfg['margin'])&(modification<=cfg['deformation_limit'])
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


def simulate(base,spec,variant='reciprocal_flow',strength=0,cfg=None,reverse=False):
    cfg={**DEFAULT,**(cfg or {})};states=old.initial(base,spec);personal={s.reference:personal_library(base,s.reference,strength) for s in states}
    # Own initial archive is identical in personal libraries.
    frames=[old.frame(states,base,0)];decisions=[];durations=[];edges=set();holds=0;switches=0;arrival={}
    for step in range(round(spec['duration']/.2)):
        snapshot=states;plans={};start=time.perf_counter()
        for s in (list(reversed(snapshot)) if reverse else snapshot):
            if s.arrived:continue
            opt,d=choose(personal[s.reference],s,snapshot,spec['walls'],variant,cfg,log=(step%5==0))
            plans[s.id]=(opt,d);decisions.append({'t':round(step*.2,6),'id':s.id,**d})
            for o in snapshot:
                if s.id<o.id and np.linalg.norm(s.pos-o.pos)<1.5:edges.add((s.id,o.id))
        durations.append(time.perf_counter()-start);paths={}
        for s in snapshot:
            if s.arrived:continue
            opt,_=plans[s.id]
            if opt is None:holds+=1
            else:paths[s.id]=old.rollout(personal[s.reference],s,opt,np.arange(1,5)*.05)
        for j in range(4):
            rendered=[]
            for s in snapshot:
                if s.id not in paths:
                    new=replace(s,hold=not s.arrived,speed=0.,pose_velocity=np.zeros_like(s.pose))
                else:
                    p=paths[s.id];clip=int(plans[s.id][0][0,0]);prev=s.pose if j==0 else p['pose'][j-1,0]
                    new=old.State(s.id,p['pos'][j,0],s.goal,float(p['yaw'][j,0]),float(p['travel'][j,0]),float(p['speed'][j,0]),clip,s.reference,
                        float(p['phase'][j,0]),p['pose'][j,0],(p['pose'][j,0]-prev)/.05)
                    if j==3:
                        switches+=int(s.clip!=clip)
                        if np.linalg.norm(new.pos-new.goal)<.22:new.arrived=True;arrival.setdefault(s.id,(step+1)*.2)
                rendered.append(new)
            frames.append(old.frame(rendered,base,step*.2+(j+1)*.05))
        states=rendered
    return {'spec':spec,'mode':variant,'p_weight':0,'layer_strength':strength,'config':cfg,'frames':frames,'decisions':decisions,
        'runtime':{'planning_seconds':sum(durations),'planning_step_ms_p50':float(np.median(durations)*1000),'planning_step_ms_p95':float(np.quantile(durations,.95)*1000),
            'agent_count':len(states),'switches':switches,'emergency_hold_agent_steps':holds,'arrival_times':arrival,'interaction_edges':sorted(edges)}}
