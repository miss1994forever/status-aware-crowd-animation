"""Autonomous ORCA-form velocity halfplanes and exhaustive 2-D projection.

Neighbor-line equations follow reciprocal velocity-obstacle geometry (van den
Berg et al.). This solver enumerates boundary projections/intersections rather
than importing RVO2 or its incremental LP code. The downstream nonholonomic
motion tracker does NOT inherit ORCA's holonomic collision-free guarantee.
"""
import math
import numpy as np


def det(a,b):return float(a[0]*b[1]-a[1]*b[0])


def unit(a):
    return a/max(np.linalg.norm(a),1e-12)


def velocity(s):
    return np.zeros(2) if s.hold or s.arrived else s.speed*np.array([math.sin(s.yaw+s.travel),math.cos(s.yaw+s.travel)])


def radius(s):
    # Global source envelope .38 is never reduced; actual observed body can enlarge it.
    return max(.38,float(np.linalg.norm(s.pose[:,[0,2]],axis=1).max()+.04))


def halfplanes(s,visible,tau=3.,step=.2):
    v=velocity(s);lines=[];neighbors=[]
    for o in visible:
        if o.id==s.id or np.linalg.norm(o.pos-s.pos)>5.:continue
        p=o.pos-s.pos;rv=v-velocity(o);r=radius(s)+radius(o)+.03;d2=float(p@p)
        if d2>r*r:
            w=rv-p/tau;w2=float(w@w);wp=float(w@p)
            if wp<0 and wp*wp>r*r*w2:
                n=unit(w);u=(r/tau-math.sqrt(w2))*n
                direction=np.array([n[1],-n[0]])
            else:
                leg=math.sqrt(max(d2-r*r,0))
                if det(p,w)>0:direction=np.array([p[0]*leg-p[1]*r,p[0]*r+p[1]*leg])/d2
                else:direction=-np.array([p[0]*leg+p[1]*r,-p[0]*r+p[1]*leg])/d2
                u=(rv@direction)*direction-rv
        else:
            w=rv-p/step;n=unit(w) if np.linalg.norm(w)>1e-10 else -unit(p)
            u=(r/step-np.linalg.norm(w))*n;direction=np.array([n[1],-n[0]])
        normal=np.array([-direction[1],direction[0]])
        point=v+.5*u
        lines.append((normal,float(normal@point)));neighbors.append(o.id)
    return (np.array([x[0] for x in lines]).reshape(-1,2),np.array([x[1] for x in lines]),neighbors)


def project(preferred,normals,bounds,max_speed):
    """Closest feasible velocity in disk; explicit minimax grid fallback if empty."""
    p=preferred.copy()
    if np.linalg.norm(p)>max_speed:p=unit(p)*max_speed
    candidates=[p,np.zeros(2)]
    for n,b in zip(normals,bounds):
        candidates.append(p+(b-n@p)*n)
        if abs(b)<=max_speed:
            t=np.array([-n[1],n[0]])*math.sqrt(max(max_speed**2-b*b,0))
            candidates.extend([b*n+t,b*n-t])
    for i,n in enumerate(normals):
        for j in range(i):
            matrix=np.array([n,normals[j]])
            if abs(np.linalg.det(matrix))>1e-9:candidates.append(np.linalg.solve(matrix,[bounds[i],bounds[j]]))
    a=np.array(candidates);inside=np.linalg.norm(a,axis=1)<=max_speed+1e-9
    violation=np.maximum(bounds[None]-a@normals.T,0)
    valid=inside&(violation.max(1,initial=0)<=1e-8)
    if valid.any():
        indices=np.where(valid)[0];i=indices[np.argmin(np.sum((a[indices]-p)**2,axis=1))]
        return a[i],True
    grid=[np.zeros(2)]
    for speed in [.25,.5,.75,1.]:
        grid.extend(max_speed*speed*np.stack([np.sin(np.arange(64)*2*np.pi/64),np.cos(np.arange(64)*2*np.pi/64)],axis=1))
    a=np.array(grid);violation=np.maximum(bounds[None]-a@normals.T,0)
    score=100*violation.max(1,initial=0)**2+np.sum((a-p)**2,axis=1)
    return a[int(np.argmin(score))],False


def preferred_velocity(s,visible,speed=1.,circulation=.8):
    d=unit(s.goal-s.pos);risk=0.
    # Predict our desired motion against observed neighbor velocity, not their goals/plans.
    for o in visible:
        if o.id==s.id:continue
        p=o.pos-s.pos;rv=speed*d-velocity(o)
        t=float(p@rv/max(rv@rv,1e-9))
        if 0<t<3.5:
            miss=np.linalg.norm(p-rv*t)
            r=radius(s)+radius(o)+.3
            risk=max(risk,max(0,1-miss/r)*max(0,1-t/4))
    right=np.array([d[1],-d[0]])
    out=unit(d+circulation*risk*right)
    return out*min(speed,np.linalg.norm(s.goal-s.pos)*2),risk
