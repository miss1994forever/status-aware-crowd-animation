"""Autonomous finite-library receding-horizon joint action/trajectory search.

All agent decisions read the same snapshot. No hidden characteristics enter
neighbor prediction. This is neither EMM reproduction nor ORCA.
"""
from dataclasses import dataclass
import math
import time
import numpy as np
from .motion import wrap,rebuild
from .geometry import box,box_gap,wall_boxes,world_pose


@dataclass
class State:
    id: int
    pos: np.ndarray
    goal: np.ndarray
    yaw: float
    travel: float
    speed: float
    clip: int
    reference: int
    phase: float
    pose: np.ndarray
    pose_velocity: np.ndarray
    arrived: bool=False
    hold: bool=False


def initial(lib, spec):
    result=[]
    for i,(p,g) in enumerate(zip(spec['starts'],spec['goals'])):
        ref=lib.ids.index(spec.get('reference','M02')) if len(spec['starts'])==1 else lib.ids.index(['M01','M02','M03'][i%3])
        d=np.array(g)-p;yaw=math.atan2(d[0],d[1])-lib.angles[ref]
        phase=(i*.173+spec['seed']*.037)%1
        result.append(State(i,np.array(p,dtype=float),np.array(g,dtype=float),yaw,lib.angles[ref],lib.speeds[ref],ref,ref,phase,lib.sample(ref,phase),lib.velocity(ref,phase,1/lib.periods[ref])))
    return result


def options(lib,state,mode):
    clips=np.where(np.abs(wrap(lib.angles-lib.angles[state.clip]))<=.7)[0]
    if mode=='F': clips=np.array([state.reference])
    # Small phase search only when switching; continuing phase is always included.
    rows=[]
    for c in clips:
        for scale in [.8,1.15]:
            for steer in [-.9,-.45,0,.45,.9]:
                for offset in ([0] if c==state.clip else [-.08,0,.08]):
                    rows.append((c,scale,steer,offset))
    return np.array(rows)


def rollout(lib,state,opts,times):
    """Explicit .05 s integration. Same synthesis for planning and execution.

    Root heading follows body+source travel angle; travel angle blends at <=1.8
    rad/s, yaw <=1.4 rad/s, scalar acceleration <=1.2 heights/s^2.
    Pose inertial offset includes initial velocity, fades over .4 s, then
    reconstructs fixed bones. It can distort poses: evaluator quantifies that.
    """
    k=len(opts);ci=opts[:,0].astype(int);scale=opts[:,1]
    phase=(state.phase+opts[:,3])%1
    target_yaw=math.atan2(*(state.goal-state.pos)[[0,1]])-lib.angles[ci]+opts[:,2]
    pos=np.repeat(state.pos[None],k,axis=0);yaw=np.full(k,state.yaw);travel=np.full(k,state.travel);speed=np.full(k,state.speed)
    # The source derivative at t=0 follows ACTUAL initial speed, not requested
    # terminal scale. Otherwise each speed change injects a pose-velocity jump.
    rate=state.speed/np.maximum(lib.speeds[ci],1e-6)/lib.periods[ci]
    source0=lib.sample(ci,phase);v0=lib.velocity(ci,phase,rate)
    delta=state.pose-source0;dv=state.pose_velocity-v0
    all_pos=[];all_yaw=[];all_pose=[];all_phase=[];all_travel=[];all_speed=[];all_source=[]
    previous=0
    for t in times:
        dt=t-previous;previous=t
        yaw+=np.clip(wrap(target_yaw-yaw),-1.4*dt,1.4*dt)
        travel+=np.clip(wrap(lib.angles[ci]-travel),-1.8*dt,1.8*dt)
        speed+=np.clip(lib.speeds[ci]*scale-speed,-1.2*dt,1.2*dt)
        phase=(phase+speed/np.maximum(lib.speeds[ci],1e-6)/lib.periods[ci]*dt)%1
        pos+=speed[:,None]*np.stack([np.sin(yaw+travel),np.cos(yaw+travel)],-1)*dt
        source=lib.sample(ci,phase)
        u=min(t/.4,1);fade=1-10*u**3+15*u**4-6*u**5
        pose=rebuild(source+(delta+dv*t)*fade,lib.parents,lib.lengths)
        all_pos.append(pos.copy());all_yaw.append(yaw.copy());all_pose.append(pose);all_phase.append(phase.copy());all_travel.append(travel.copy());all_speed.append(speed.copy());all_source.append(source)
    return {'pos':np.array(all_pos),'yaw':np.array(all_yaw),'pose':np.array(all_pose),'phase':np.array(all_phase),
            'travel':np.array(all_travel),'speed':np.array(all_speed),'source':np.array(all_source)}


def choose(lib,state,snapshot,walls,mode='G',p_weight=0,log=False):
    opts=options(lib,state,mode);times=np.arange(1,21)*.05
    paths=rollout(lib,state,opts,times);ci=opts[:,0].astype(int);k=len(ci)
    shape=box(paths['pose'],paths['pos'],paths['yaw'])
    circle=mode=='circle'
    # Fixed circle is one global library envelope; never shrunk for a narrow door.
    radius=.38
    clearance=np.full((20,k),10.)
    for w,wb in zip(walls,wall_boxes(walls)):
        if circle:
            closest=np.maximum(np.array(w[:2]),np.minimum(paths['pos'],np.array(w[2:])))
            gap=np.linalg.norm(paths['pos']-closest,axis=-1)-radius
        else:gap=box_gap(shape,wb)
        clearance=np.minimum(clearance,gap)
    for other in snapshot:
        if other.id==state.id:continue
        velocity=np.zeros(2) if other.hold or other.arrived else other.speed*np.array([math.sin(other.yaw+other.travel),math.cos(other.yaw+other.travel)])
        opos=other.pos+times[:,None]*velocity
        if np.linalg.norm(other.pos-state.pos)>3.5:continue
        if circle:
            gap=np.linalg.norm(paths['pos']-opos[:,None,:],axis=-1)-2*radius
        else:
            # Freeze observable body shape; constant velocity translation. No reference/clip access.
            ob=box(other.pose,opos,np.full(20,other.yaw))
            gap=box_gap(shape,tuple(x[:,None] for x in ob))
        clearance=np.minimum(clearance,gap)
    used=clearance[:4] if mode=='no_prediction' else clearance
    minimum=used.min(axis=0)
    deformation=np.linalg.norm(paths['pose']-paths['source'],axis=-1).max(axis=(0,2))
    # Explicit permissive kinematic gate, not a naturalness threshold. Kept in all ablations.
    feasible=(minimum>=.005)&(deformation<=.4)
    progress=np.linalg.norm(paths['pos'][-1]-state.goal,axis=-1)-np.linalg.norm(state.pos-state.goal)
    pose_rms=np.sqrt(np.mean((lib.sample(ci,(state.phase+opts[:,3])%1)-state.pose)**2,axis=(1,2)))
    velocity_rms=np.sqrt(np.mean((lib.velocity(ci,(state.phase+opts[:,3])%1,opts[:,1]/lib.periods[ci])-state.pose_velocity)**2,axis=(1,2)))
    continuity=2*pose_rms+.08*velocity_rms+.02*(ci!=state.clip)+.06*np.abs(wrap(lib.angles[ci]-state.travel))
    if mode=='no_continuity':continuity=np.zeros(k)
    expression=lib.expression(ci,state.reference)
    near=.015*np.mean(np.maximum(.15-used,0)**2,axis=0)
    direction=state.goal-state.pos;direction=direction/max(np.linalg.norm(direction),1e-9)
    crowded=any(o.id!=state.id and np.linalg.norm(o.pos-state.pos)<2.5 and np.dot(o.pos-state.pos,direction)>.2 for o in snapshot)
    preferred=.6 if crowded else 0.
    navigation=.15*(opts[:,2]-preferred)**2
    score=progress+continuity+near+navigation+p_weight*expression
    safe=np.where(feasible)[0]
    chosen=int(safe[np.argmin(score[safe])]) if len(safe) else None
    entries=[]
    traces=[]
    if log:
        for i in range(k):
            entries.append({'clip':lib.ids[ci[i]],'scale':float(opts[i,1]),'steer':float(opts[i,2]),'phase_offset':float(opts[i,3]),
                            'clearance':float(minimum[i]),'feasible':bool(feasible[i]),'progress':float(progress[i]),
                            'continuity':float(continuity[i]),'expression':float(expression[i]),'navigation':float(navigation[i]),'deformation':float(deformation[i]),'score':float(score[i]),
                            'reason':'safe' if feasible[i] else ('transition_deformation_limit' if deformation[i]>.4 else 'predicted_body_overlap'), 'selected':i==chosen})
        trace_indices=set(sorted(range(k),key=lambda i:score[i])[:2])
        if chosen is not None:trace_indices.add(chosen)
        trace_indices.add(int(np.argmax(minimum)))
        for i in sorted(trace_indices):
            traces.append({'index':i,'selected':i==chosen,'clip':lib.ids[ci[i]],'pos':paths['pos'][:,i].round(6).tolist(),
                           'yaw':paths['yaw'][:,i].round(6).tolist(),'half':shape[2][:,i].round(6).tolist(),
                           'center':shape[0][:,i].round(6).tolist(),'feasible':bool(feasible[i])})
    return (None if chosen is None else opts[chosen:chosen+1]),{'safe_count':len(safe),'candidate_count':k,'best_unsafe_clearance':float(minimum.max()),'candidates':entries,'traces':traces}


def frame(states,lib,t):
    return {'t':round(t,6),'agents':[{'id':s.id,'pos':s.pos.tolist(),'yaw':s.yaw,'travel':s.travel,'speed':s.speed,'clip':lib.ids[s.clip],
            'phase':s.phase,'pose':s.pose.round(6).tolist(),'hold':s.hold,'arrived':s.arrived} for s in states]}


def simulate(lib,spec,mode,p_weight=0,reverse=False):
    states=initial(lib,spec);frames=[frame(states,lib,0)];decisions=[];cpu=[];edges=set();switches=0;holds=0;arrival={}
    for step in range(round(spec['duration']/.2)):
        start=time.perf_counter();snapshot=states;plans={}
        order=list(reversed(snapshot)) if reverse else snapshot
        for s in order:
            if s.arrived:plans[s.id]=(None,None);continue
            opt,decision=choose(lib,s,snapshot,spec['walls'],mode,p_weight,log=(len(states)==1 or (step%10==0 and s.id==0)))
            plans[s.id]=(opt,decision)
            decisions.append({'t':round(step*.2,6),'id':s.id,**decision})
            for o in snapshot:
                if s.id<o.id and np.linalg.norm(s.pos-o.pos)<1.5:edges.add((s.id,o.id))
        cpu.append(time.perf_counter()-start)
        paths={}
        for s in snapshot:
            opt,decision=plans[s.id]
            if opt is not None:paths[s.id]=rollout(lib,s,opt,np.arange(1,5)*.05)
            elif not s.arrived:holds+=1
        next_states=[]
        for substep in range(4):
            rendered=[]
            for s in snapshot:
                if s.id in paths:
                    p=paths[s.id];j=substep;opt=plans[s.id][0];clip=int(opt[0,0])
                    prev=s.pose if j==0 else p['pose'][j-1,0]
                    new=State(s.id,p['pos'][j,0],s.goal,float(p['yaw'][j,0]),float(p['travel'][j,0]),float(p['speed'][j,0]),clip,s.reference,float(p['phase'][j,0]),p['pose'][j,0],(p['pose'][j,0]-prev)/.05)
                    if j==3:
                        switches+=int(s.clip!=clip)
                        if np.linalg.norm(new.pos-new.goal)<.22:
                            new.arrived=True;arrival.setdefault(s.id,(step+1)*.2)
                else:
                    new=State(**{**vars(s),'hold':not s.arrived,'speed':0.,'pose_velocity':np.zeros_like(s.pose)})
                rendered.append(new)
            frames.append(frame(rendered,lib,step*.2+(substep+1)*.05))
            if substep==3:next_states=rendered
        states=next_states
    return {'spec':spec,'mode':mode,'p_weight':p_weight,'frames':frames,'decisions':decisions,
            'runtime':{'planning_seconds':sum(cpu),'planning_step_ms_p50':float(np.median(cpu)*1000),'planning_step_ms_p95':float(np.quantile(cpu,.95)*1000),
                       'agent_count':len(states),'switches':switches,'emergency_hold_agent_steps':holds,'arrival_times':arrival,'interaction_edges':sorted(edges)}}
