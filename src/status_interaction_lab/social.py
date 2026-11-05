"""Typed information boundary. No neighbor private state enters estimation/control.

Angles are engineering hypotheses, NOT validated status/dominance labels.
"""
from dataclasses import dataclass
import copy
import math
import numpy as np
from src.expression_layer import upper_mask
from src.predictive_motion_lab.motion import wrap

CONFIG = dict(personal_strength=.35, cue_pitch=.045, cue_scale=.16,
              social_gain=.18, geometric_gain=.10, facing_weight=.35, range=2.5,
              response_tau=.45, max_rate=.35, max_turn=.25,
              min_observations=3, confidence_distance=2.5)

@dataclass(frozen=True)
class PrivateSelf:
    status: float

@dataclass(frozen=True)
class VisibleNeighbor:
    id: int
    pos: np.ndarray
    yaw: float
    travel: float
    speed: float
    pose: np.ndarray
    hold: bool
    arrived: bool

@dataclass(frozen=True)
class Estimate:
    value: float | None
    confidence: float
    samples: int

@dataclass(frozen=True)
class Response:
    geometric: float
    social: float
    target: float
    applied: float
    observations: tuple


def visible(s):
    # Copy only the explicit allowlist. Private reference/goal/clip never exported.
    return VisibleNeighbor(s.id,s.pos.copy(),s.yaw,s.travel,s.speed,s.pose.copy(),s.hold,s.arrived)


def feature(pose,names):
    # Local trunk inclination, available from observed 3D skeleton.
    v=pose[names.index('Chest')]-pose[names.index('Hips')]
    return float(math.atan2(v[2],v[1]))


def torso_heading(pose,names):
    axis=pose[names.index('UpperArm_L')]-pose[names.index('UpperArm_R')]
    return float(math.atan2(-axis[2],axis[0]))


def estimate(o,names,history,distance,cfg):
    x=feature(o.pose,names)
    past=history.get(o.id,[])
    values=(past+[x])[-5:];history[o.id]=values
    if len(values)<cfg['min_observations'] or distance>=cfg['confidence_distance']:
        return Estimate(None,0.,len(values))
    quality=max(0.,1-distance/cfg['confidence_distance'])
    stability=math.exp(-float(np.std(values))/.08)
    c=quality*stability*min(1,len(values)/5)
    return Estimate(float(np.tanh(np.mean(values)/cfg['cue_scale'])),c,len(values))


def respond(own,neighbors,names,history,previous,mode,cfg,yoked=None):
    # Canonical geometry ordering prevents identifiers/order from setting precedence.
    neighbors=sorted((o for o in neighbors if o.id!=own.id),key=lambda o:tuple(o.pos))
    active=set();terms=[];social=[];rows=[];weights=[]
    for o in neighbors:
        d=o.pos-own.pos;distance=float(np.linalg.norm(d))
        if distance>=cfg['range']:continue
        active.add(o.id)
        bearing=float(wrap(math.atan2(d[0],d[1])-own.yaw))
        # Idealized 240 degree field of view. No occlusion model yet.
        if abs(bearing)>2.094:continue
        w=max(0.,1-distance/cfg['range'])
        e=estimate(o,names,history,distance,cfg)
        orient=float(np.clip(bearing,-1,1))
        terms.append(w*orient);weights.append(w)
        confidence=1. if mode=='C2-no-confidence' and e.value is not None else e.confidence
        # Actual torso facing relative to THIS observer; no planned gaze or label.
        to_self=math.atan2(-d[0],-d[1])
        facing=math.cos(float(wrap(o.yaw+torso_heading(o.pose,names)-to_self)))
        gain=0. if e.value is None else confidence*((1-cfg['facing_weight'])*e.value+cfg['facing_weight']*facing)
        social.append(w*orient*gain)
        rows.append(dict(id=o.id,distance=distance,bearing=bearing,feature=feature(o.pose,names),estimate=e.value,facing_current_observer=facing,confidence=e.confidence,samples=e.samples,weight=w))
    for k in list(history):
        if k not in active:del history[k]
    denom=max(1.,sum(weights))
    geometric=cfg['geometric_gain']*math.fsum(terms)/denom
    s=cfg['social_gain']*math.fsum(social)/denom if mode not in ('C1','C2-off') else 0.
    if mode=='C2-yoked':s=float(yoked or 0.)
    target=float(np.clip(geometric+s,-cfg['max_turn'],cfg['max_turn']))
    delta=(target-previous)*(1-math.exp(-.2/cfg['response_tau']))
    applied=previous+float(np.clip(delta,-cfg['max_rate']*.2,cfg['max_rate']*.2))
    return Response(geometric,s,target,applied,tuple(rows))


def transform(lib,poses,pitch,turn):
    """Rotate entire Spine subtree about its attachment; exact bone lengths.

    Pelvis/legs/root are untouched. Bounded pitch/turn are relative source DOFs.
    """
    out=poses.copy();mask=upper_mask(lib);spine=lib.names.index('Spine');parent=lib.parents[spine]
    origin=poses[...,parent:parent+1,:]
    x=poses[...,mask,:]-origin
    cp,sp=math.cos(pitch),math.sin(pitch);ct,st=math.cos(turn),math.sin(turn)
    rx=np.array([[1,0,0],[0,cp,-sp],[0,sp,cp]])
    ry=np.array([[ct,0,st],[0,1,0],[-st,0,ct]])
    out[...,mask,:]=x@(ry@rx).T+origin
    return out


def controlled_library(personal,private,turn,cfg):
    lib=copy.copy(personal)
    lib.poses=transform(personal,personal.poses,cfg['cue_pitch']*private.status,turn)
    return lib
