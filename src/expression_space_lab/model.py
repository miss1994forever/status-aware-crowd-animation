"""Bounded movement-quality experiment, not PERFORM reproduction or status model."""
import math
import numpy as np
from src.expression_layer import unit_slerp


def phase_map(u, strength, amount=.32):
    # C-infinity periodic derivative, >0; same cycle duration and distance.
    return u-strength*amount*np.sin(4*np.pi*u)/(4*np.pi)


def bone_project(points, parents, lengths):
    out=points.copy()
    for j,p in enumerate(parents):
        if p is None: continue
        d=points[j]-points[p]; n=np.linalg.norm(d)
        out[j]=out[p]+d*lengths[j]/max(n,1e-12)
    return out


def solve_knee(hip, ankle, source_knee, a, b, regularization=0):
    d=ankle-hip; dist=np.linalg.norm(d); e=d/max(dist,1e-12)
    x=(a*a-b*b+dist*dist)/(2*max(dist,1e-12))
    h=np.sqrt(max(0,a*a-x*x))
    pole=source_knee-hip; pole-=e*np.dot(pole,e)
    anterior=np.array([0.,0.,1.]); anterior-=e*np.dot(anterior,e)
    pole+=regularization*anterior
    pole/=max(np.linalg.norm(pole),1e-12)
    return hip+x*e+h*pole


def quality(pose, names, parents, lengths, phase, strength, *, timing=True, shape=True, version=3):
    """Apply dynamic pelvis and sagittal arm trajectories; keep ankle/toe samples.

    Timing is applied by caller to root AND all joints. Lower-chain IK anchors
    both ankles at the sampled source; no foot-lock heuristic is used.
    """
    if not np.isfinite(strength) or not 0<=strength<=1: raise ValueError('strength [0,1]')
    out=pose.copy()
    if not shape or strength==0:return out
    # No persistent lean, no lateral elbow lift. Bounded periodic shape.
    dy=strength*(.030 if version==1 else .016)*math.cos(4*math.pi*phase)
    # Feasible interval by monotone backoff, measured against both leg chains.
    legs=[]
    for side in ['L','R']:
        h,k,a=[names.index(x+'_'+side) for x in ['UpperLeg','LowerLeg','Foot']]
        legs.append((h,k,a))
    if version>=3:
        # The previous reach-only constraint allowed almost locked knees, while
        # downward bobbing could keep a naturally extending leg visibly bent.
        # Fade BOTH signs of extra bob when either source leg nears extension.
        slack=np.array([max(0,lengths[k]+lengths[a]-np.linalg.norm(pose[a]-pose[h])) for h,k,a in legs])
        dy*=float(np.prod(slack*slack/(slack*slack+.005**2)))
    if version==1:
        for _ in range(15):
            feasible=all(abs(lengths[k]-lengths[a])+1e-6 < np.linalg.norm(pose[a]-(pose[h]+[0,dy,0])) < lengths[k]+lengths[a]-.0001 for h,k,a in legs)
            if feasible:break
            dy*=.5
    elif dy>0:
        # Smooth saturation against reach, rather than discrete halving. The
        # latter caused visible knee acceleration spikes in the first round.
        limits=[]
        for h,k,a in legs:
            horizontal=np.linalg.norm((pose[a]-pose[h])[[0,2]])
            reach=lengths[k]+lengths[a]-.00001
            if version>=3:
                slack=max(0,lengths[k]+lengths[a]-np.linalg.norm(pose[a]-pose[h]))
                reach=lengths[k]+lengths[a]-.75*slack
            vertical=np.sqrt(max(0,reach**2-horizontal**2))
            limits.append(max(0,pose[a,1]+vertical-pose[h,1]))
        limit=min(limits)
        dy=limit*np.tanh(dy/max(limit,1e-12))
    out[:,1]+=dy
    for h,k,a in legs:
        pole_reference=pose[k]+[0,dy,0] if version>=3 else pose[k]
        out[k]=solve_knee(out[h],pose[a],pole_reference,lengths[k],lengths[a],abs(dy)*2.5 if version==2 else 0)
        out[a]=pose[a]
        # Preserve every foot descendant including toes/end sites exactly.
        for j,p in enumerate(parents):
            ancestor=p
            while ancestor is not None and ancestor!=a:ancestor=parents[ancestor]
            if ancestor==a:out[j]=pose[j]
    for side in ['L','R']:
        shoulder,elbow=names.index('UpperArm_'+side),names.index('LowerArm_'+side)
        v=pose[elbow]-pose[shoulder]
        angle=math.atan2(v[2],-v[1])
        # Deviation from vertical, bounded extra pitch; driven by recorded swing.
        extra=-np.clip(angle,-.65,.65)*strength*(1.1 if version==1 else .65)
        c,s=math.cos(extra),math.sin(extra)
        rot=np.array([[1,0,0],[0,c,-s],[0,s,c]])
        for j in range(shoulder+1,len(names)):
            p=parents[j]
            while p is not None and p!=shoulder:p=parents[p]
            if p==shoulder:out[j]=out[shoulder]+rot@(out[j]-out[shoulder])
    return out


def aligned_blend(base, donor, parents, lengths, weight, upper_only=False, names=None):
    """Route A bounded trial. Direction blend, no PCA, identity lengths fixed."""
    out=base.copy(); mask=[]
    for j,p in enumerate(parents):
        mask.append(names[j]=='Spine' or (p is not None and mask[p]) if upper_only else True)
        if p is None or not mask[j]:continue
        a=base[j]-base[p]; b=donor[j]-donor[p]
        a/=max(np.linalg.norm(a),1e-12); b/=max(np.linalg.norm(b),1e-12)
        out[j]=out[p]+unit_slerp(a,b,weight)*lengths[j]
    return out
