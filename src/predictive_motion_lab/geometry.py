"""Planner geometry: conservative oriented rectangle of projected skeleton + thickness.

Contains all thickened projected bone segments at each sampled instant, but
not unsampled time, mesh, or neighbors' unobserved changes of plan.
"""
import numpy as np


def world_pose(local, pos, yaw):
    c=np.cos(yaw)[...,None];s=np.sin(yaw)[...,None]
    x=local[...,0]*c+local[...,2]*s+pos[...,0,None]
    z=-local[...,0]*s+local[...,2]*c+pos[...,1,None]
    return np.stack([x,local[...,1],z],axis=-1)


def box(local,pos,yaw,radius=.04):
    lo=local[...,[0,2]].min(axis=-2)-radius
    hi=local[...,[0,2]].max(axis=-2)+radius
    mid=(lo+hi)/2;half=(hi-lo)/2
    c=np.cos(yaw);s=np.sin(yaw)
    axes=np.stack([np.stack([c,-s],-1),np.stack([s,c],-1)],-2)
    center=pos+np.einsum('...i,...ij->...j',mid,axes)
    return center,axes,np.broadcast_to(half,center.shape)


def box_gap(a,b):
    ca,aa,ha=a;cb,ab,hb=b
    batch=np.broadcast_shapes(ca.shape[:-1],cb.shape[:-1])
    ca=np.broadcast_to(ca,batch+(2,));cb=np.broadcast_to(cb,batch+(2,))
    aa=np.broadcast_to(aa,batch+(2,2));ab=np.broadcast_to(ab,batch+(2,2))
    ha=np.broadcast_to(ha,batch+(2,));hb=np.broadcast_to(hb,batch+(2,))
    axes=np.concatenate([aa,ab],axis=-2)
    d=np.abs(np.einsum('...j,...ij->...i',cb-ca,axes))
    ra=(np.abs(np.einsum('...ij,...kj->...ik',axes,aa))*ha[...,None,:]).sum(-1)
    rb=(np.abs(np.einsum('...ij,...kj->...ik',axes,ab))*hb[...,None,:]).sum(-1)
    return np.max(d-ra-rb,axis=-1)


def wall_boxes(walls):
    return [(np.array([(w[0]+w[2])/2,(w[1]+w[3])/2]),np.eye(2),np.array([(w[2]-w[0])/2,(w[3]-w[1])/2])) for w in walls]
