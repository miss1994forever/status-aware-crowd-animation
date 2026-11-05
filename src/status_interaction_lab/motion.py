"""Constrained adapter around frozen synthesis; identical in every condition.

Source-relative bone direction cones are engineering kinematic bounds, not a
complete anatomical joint model. No foot locking or phase matching is used.
"""
import numpy as np
from src.predictive_motion_lab.controller import rollout as source_rollout

MAX_RATE=8.0
TOE_RATE=12.0
MAX_SOURCE_ANGLE=.75


def rollout(lib,state,opts,times):
    p=source_rollout(lib,state,opts,times)
    previous=np.broadcast_to(state.pose,p['pose'][0].shape).copy();previous_time=0.
    lifts=[];corrections=[];cone_errors=[]
    for k,t in enumerate(times):
        dt=t-previous_time;previous_time=t;raw=p['pose'][k];source=p['source'][k];out=raw.copy()
        joints=np.array([j for j,parent in enumerate(lib.parents) if parent is not None and lib.lengths[j]>1e-8])
        parents=np.array([lib.parents[j] for j in joints])
        def norm(v):return v/np.maximum(np.linalg.norm(v,axis=-1,keepdims=True),1e-12)
        target=norm(raw[:,joints]-raw[:,parents]);ref=norm(source[:,joints]-source[:,parents]);prior=norm(previous[:,joints]-previous[:,parents])
        angle=np.arccos(np.clip(np.sum(ref*target,axis=-1),-1,1))
        target=rotate_towards(ref,target,np.minimum(angle,MAX_SOURCE_ANGLE))
        change=np.arccos(np.clip(np.sum(prior*target,axis=-1),-1,1))
        rates=np.array([TOE_RATE if 'Toes' in lib.names[j] else MAX_RATE for j in joints])
        direction=rotate_towards(prior,target,np.minimum(change,rates*dt))
        for index,j in enumerate(joints):out[:,j]=out[:,lib.parents[j]]+direction[:,index]*lib.lengths[j]
        deviations=np.arccos(np.clip(np.sum(ref*direction,axis=-1),-1,1))
        # Common nonpenetration correction of vertical root offset, not leg IK.
        lift=np.maximum(0.,-out[:,:,1].min(axis=1));out[:,:,1]+=lift[:,None]
        lifts.append(lift);corrections.append(np.linalg.norm(out-raw,axis=-1).max(1));cone_errors.append(np.max(deviations,axis=1))
        p['pose'][k]=out;previous=out
    p['floor_lift']=np.array(lifts);p['constraint_correction']=np.array(corrections);p['cone_error']=np.array(cone_errors)
    return p


def rotate_towards(a,b,angle):
    dot=np.clip(np.sum(a*b,axis=-1),-1,1);tangent=b-dot[...,None]*a
    length=np.linalg.norm(tangent,axis=-1)
    axis=np.eye(3)[np.argmin(np.abs(a),axis=-1)];fallback=axis-np.sum(axis*a,axis=-1)[...,None]*a
    fallback/=np.maximum(np.linalg.norm(fallback,axis=-1)[...,None],1e-12)
    tangent=np.where((length>1e-9)[...,None],tangent/np.maximum(length[...,None],1e-12),fallback)
    return np.cos(angle)[...,None]*a+np.sin(angle)[...,None]*tangent
