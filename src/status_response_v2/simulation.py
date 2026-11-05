"""Closed-loop development runner, reusing frozen navigation/safety read-only."""
from dataclasses import replace
import copy
import time
import numpy as np
from src.predictive_motion_lab import controller as old
from src.expression_layer import personal_library
from src.status_interaction_lab.social import visible
from src.status_interaction_lab.navigation import choose, DEFAULT
from src.status_interaction_lab.motion import rollout
from .control import Memory, CONFIG, step, body_library


def simulate(base,spec,mode,config=None):
    cfg={**CONFIG,**(config or {})};states=old.initial(base,spec)
    rng=np.random.default_rng(spec['seed']+987)
    values=spec.get('private_values',rng.choice([-1.,1.],len(states)).tolist())
    private={s.id:float(x) for s,x in zip(states,values)}
    personal={s.reference:personal_library(base,s.reference,cfg['personal_strength']) for s in states}
    for s in states:
        lib=body_library(personal[s.reference],private[s.id],0,0,cfg)
        s.pose=lib.sample(s.clip,s.phase);s.pose_velocity=lib.velocity(s.clip,s.phase,1/lib.periods[s.clip])
    memories={s.id:Memory() for s in states};frames=[old.frame(states,base,0.)]
    decisions=[];durations=[];arrivals={};holds=0;switches=0
    for block in range(round(spec['duration']/.2)):
        start=time.perf_counter();snapshot=states;observed=[visible(s) for s in states]
        paths={};plans={}
        for s in snapshot:
            if s.arrived:continue
            proposed=copy.deepcopy(memories[s.id])
            r=step(visible(s),observed,base.names,private[s.id],proposed,mode,cfg)
            lib=body_library(personal[s.reference],private[s.id],r['turn'],r['compact'],cfg)
            opt,decision=choose(lib,s,observed,spec['walls'],'long_cv',DEFAULT)
            if opt is not None:
                paths[s.id]=rollout(lib,s,opt,np.arange(1,5)*.05);plans[s.id]=opt
                memories[s.id]=proposed
            else:
                holds+=1
                # Remember observed evidence but never integrate unapplied body controls.
                memories[s.id].samples=proposed.samples;memories[s.id].target=proposed.target
            decisions.append(dict(t=round(block*.2,6),id=s.id,**decision,response=r,
                                  executed=opt is not None))
        durations.append(time.perf_counter()-start)
        for j in range(4):
            rendered=[]
            for s in snapshot:
                if s.id not in paths:
                    new=replace(s,hold=not s.arrived,speed=0.,pose_velocity=np.zeros_like(s.pose))
                else:
                    p=paths[s.id];clip=int(plans[s.id][0,0]);prev=s.pose if j==0 else p['pose'][j-1,0]
                    new=old.State(s.id,p['pos'][j,0],s.goal,float(p['yaw'][j,0]),float(p['travel'][j,0]),float(p['speed'][j,0]),clip,s.reference,float(p['phase'][j,0]),p['pose'][j,0],(p['pose'][j,0]-prev)/.05)
                    if j==3:
                        switches+=int(s.clip!=clip)
                        if np.linalg.norm(new.pos-new.goal)<.22:
                            new.arrived=True;arrivals.setdefault(s.id,(block+1)*.2)
                rendered.append(new)
            frames.append(old.frame(rendered,base,block*.2+(j+1)*.05))
        states=rendered
    return dict(spec=spec,mode=mode,config=cfg,frames=frames,decisions=decisions,
                private_experiment=private,p_weight=0,layer_strength=cfg['personal_strength'],
                runtime=dict(planning_seconds=sum(durations),planning_step_ms_p50=float(np.median(durations)*1000),
                             planning_step_ms_p95=float(np.quantile(durations,.95)*1000),agent_count=len(states),
                             switches=switches,emergency_hold_agent_steps=holds,arrival_times=arrivals))
