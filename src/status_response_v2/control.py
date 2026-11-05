"""Explicit encounter controller. All semantic mappings are testable hypotheses.

Private own style affects response timing and accommodation, never right of way.
Only public skeleton/kinematics are accepted for neighbors. Existing v1 remains frozen.
"""
from dataclasses import dataclass, field, asdict
import copy
import math
import numpy as np
from src.status_interaction_lab.social import feature, transform, VisibleNeighbor
from src.crowd_mobility_lab.reciprocal import velocity
from src.predictive_motion_lab.motion import wrap

CONFIG = dict(range=3., horizon=2.4, conflict_distance=.9, switch_ratio=1.35,
              min_samples=3, release_tau=.65, personal_strength=.35,
              cue_pitch=.045, max_turn=.42, max_compact=.55,
              max_turn_rate=.8, max_compact_rate=1., dt=.2)


@dataclass
class Memory:
    target: int | None = None
    samples: dict = field(default_factory=dict)
    turn: float = 0.
    compact: float = 0.


def candidates(own, neighbors, names, memory, cfg):
    rows=[]; present=set()
    for o in sorted(neighbors, key=lambda o: tuple(o.pos)):
        if o.id==own.id: continue
        d=o.pos-own.pos; distance=float(np.linalg.norm(d))
        bearing=float(wrap(math.atan2(d[0],d[1])-own.yaw))
        if distance>cfg['range'] or abs(bearing)>2.094: continue
        present.add(o.id)
        values=(memory.samples.get(o.id,[])+[feature(o.pose,names)])[-5:]
        memory.samples[o.id]=values
        relative=velocity(o)-velocity(own)
        vv=float(relative@relative); dot=float(d@relative)
        ttc=float(np.clip(-dot/max(vv,1e-8),0,cfg['horizon']))
        clearance=float(np.linalg.norm(d+ttc*relative))
        approaching=dot<-.01
        close_pressure=max(0.,1-distance/1.1)
        anticipated=(math.exp(-.5*(clearance/cfg['conflict_distance'])**2)
                     * max(0.,1-ttc/cfg['horizon']) if approaching else 0.)
        risk=max(close_pressure,anticipated)*max(0.,min(1.,(cfg['range']-distance)/.6))
        enough=len(values)>=cfg['min_samples']
        confidence=(math.exp(-float(np.std(values))/.10)*min(1,len(values)/5)
                    if enough else 0.)
        estimate=float(np.tanh(np.mean(values)/.16)) if enough else None
        rows.append(dict(id=o.id,distance=distance,bearing=bearing,ttc=ttc,
                         predicted_clearance=clearance,risk=risk,
                         confidence=confidence,estimate=estimate))
    # Once no longer visible, discard observations: no cross-encounter history.
    for key in list(memory.samples):
        if key not in present: del memory.samples[key]
    return rows


def step(own: VisibleNeighbor, neighbors, names, own_status, memory, mode='C2', cfg=None):
    cfg={**CONFIG,**(cfg or {})}
    if mode not in ('C1','C2','C2-no-self','C2-sum'): raise ValueError(mode)
    if not -1<=own_status<=1: raise ValueError('Own experimental value must be [-1,1]')
    rows=candidates(own,neighbors,names,memory,cfg)
    ranked=sorted(rows,key=lambda r:-r['risk'])
    best=ranked[0] if ranked and ranked[0]['risk']>.03 else None
    current=next((r for r in rows if r['id']==memory.target and r['risk']>.03),None)
    if current and best and best['risk']<current['risk']*cfg['switch_ratio']: best=current
    memory.target=best['id'] if best else None
    # The same responsive geometric body baseline is available in all conditions.
    weights=[max(0.,1-r['distance']/cfg['range']) for r in rows]
    geometric=.10*math.fsum(w*float(np.clip(r['bearing'],-1,1)) for w,r in zip(weights,rows))/max(1.,sum(weights))
    pressure=max((r['risk'] for r in rows),default=0.)
    desired_turn=geometric; desired_compact=.06*pressure
    own_value=0. if mode=='C2-no-self' else own_status
    phase='geometric'; accommodation=None
    if mode!='C1' and best and best['confidence']>0:
        # Signed relative tendency affects amplitude and timing, not navigation priority.
        accommodation=.5+.5*math.tanh(best['estimate']-own_value)
        strength=best['risk']*best['confidence']
        # Nonzero anatomical right-side convention in the exact frontal singularity.
        # Outside a small deadband, direction is towards the selected encounter side.
        side=1. if best['bearing']>=-.08 else -1.
        extra=side*strength*(.24+.13*accommodation)
        if mode=='C2-sum':
            # Alternative aggregation; same response budget, no single-object direction.
            mass=sum(r['risk']*r['confidence'] for r in rows)
            extra=(math.fsum(r['risk']*r['confidence']*float(np.clip(r['bearing'],-1,1))
                             for r in rows)/max(mass,1e-8)) * strength*(.24+.13*accommodation)
        desired_turn+=extra
        desired_compact+=strength*(.20+.30*accommodation)
        phase='responding'
    elif not best and (abs(memory.turn)>.015 or memory.compact>.015): phase='recovering'
    elif best: phase='observing'
    tau=(.27+.16*(own_value+1)/2) if phase=='responding' else cfg['release_tau']
    # C1 must not acquire a hidden extra social effect through smoothing.
    if mode=='C1': tau=cfg['release_tau']
    blend=1-math.exp(-cfg['dt']/tau)
    targets=(float(np.clip(desired_turn,-cfg['max_turn'],cfg['max_turn'])),
             float(np.clip(desired_compact,0,cfg['max_compact'])))
    memory.turn+=float(np.clip((targets[0]-memory.turn)*blend,-cfg['max_turn_rate']*cfg['dt'],cfg['max_turn_rate']*cfg['dt']))
    memory.compact+=float(np.clip((targets[1]-memory.compact)*blend,-cfg['max_compact_rate']*cfg['dt'],cfg['max_compact_rate']*cfg['dt']))
    return dict(target=memory.target,phase=phase,turn=memory.turn,compact=memory.compact,
                desired_turn=targets[0],desired_compact=targets[1],geometric=geometric,
                accommodation=accommodation,observations=rows)


def descendants(lib,root):
    mask=[]
    for j,parent in enumerate(lib.parents): mask.append(j==root or (parent is not None and mask[parent]))
    return np.array(mask)


def body_library(personal,own_status,turn,compact,cfg=None):
    """Torso rotation plus arm adduction; never bends or rescales bones.

    Adduction rotates each upper-arm subtree toward the torso/down direction,
    preserving the captured elbow/wrist configuration and existing swing.
    """
    cfg={**CONFIG,**(cfg or {})};lib=copy.copy(personal)
    p=personal.poses.copy()
    for name in ('UpperArm_L','UpperArm_R'):
        root=lib.names.index(name); child=lib.names.index(name.replace('UpperArm','LowerArm'))
        origin=p[...,root:root+1,:]; direction=p[...,child,:]-p[...,root,:]
        direction/=np.maximum(np.linalg.norm(direction,axis=-1,keepdims=True),1e-12)
        down=np.zeros_like(direction);down[...,1]=-1
        axis=np.cross(direction,down);length=np.linalg.norm(axis,axis=-1,keepdims=True)
        unit=axis/np.maximum(length,1e-12)
        angle=np.minimum(np.arccos(np.clip(np.sum(direction*down,axis=-1),-1,1)),.8)*compact
        c=np.cos(angle)[...,None,None];s=np.sin(angle)[...,None,None]
        mask=descendants(lib,root);x=p[...,mask,:]-origin;u=unit[...,None,:]
        rotated=x*c+np.cross(u,x)*s+u*np.sum(u*x,axis=-1,keepdims=True)*(1-c)
        # Parallel or antiparallel vectors have no defined bend axis: retain capture.
        p[...,mask,:]=np.where((length>1e-8)[...,None],rotated,x)+origin
    lib.poses=transform(lib,p,cfg['cue_pitch']*own_status,turn)
    return lib
