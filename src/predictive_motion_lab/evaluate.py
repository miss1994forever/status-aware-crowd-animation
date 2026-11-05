"""Independent dense replay audit. Never calls chooser, box_gap or planner cost.

Evaluates rounded replay poses at 120 Hz using bone-reconstructed interpolation,
convex hulls of ALL projected joints and 0.04 thickness. Hull is still a
conservative skeleton proxy, not a mesh. SAT gap is a signed separating-axis
measure, not Euclidean distance for separated diagonal polygons.
"""
import math
import numpy as np
from .motion import rebuild


def hull(points):
    pts=sorted(set(map(tuple,points)))
    if len(pts)<3:return np.array(pts)
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lo=[];hi=[]
    for p in pts:
        while len(lo)>=2 and cross(lo[-2],lo[-1],p)<=0:lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi)>=2 and cross(hi[-2],hi[-1],p)<=0:hi.pop()
        hi.append(p)
    return np.array(lo[:-1]+hi[:-1])


def hull_gap(a,b,padding):
    ea=np.roll(a,-1,axis=0)-a;eb=np.roll(b,-1,axis=0)-b
    e=np.concatenate([ea,eb]);axes=np.stack([-e[:,1],e[:,0]],axis=-1).astype(float)
    axes/=np.maximum(np.linalg.norm(axes,axis=1)[:,None],1e-12)
    pa=a@axes.T;pb=b@axes.T
    return float(np.max(np.maximum(pb.min(0)-pa.max(0),pa.min(0)-pb.max(0)))-padding)


def audit(run,lib):
    frames=run['frames'];n=len(frames[0]['agents']);dt=1/120
    walls=[np.array([[w[0],w[1]],[w[2],w[1]],[w[2],w[3]],[w[0],w[3]]]) for w in run['spec']['walls']]
    minimum=10.;penetration=0.;collision_samples=0;total=0;worst=None
    root=[];world=[];drift=[];modification=[];bone_error=[];hold_time=0;reference_pose_drift=[];travel_warp=[];speed_ratios=[]
    reference=[lib.ids.index(run['spec'].get('reference','M02')) if n==1 else lib.ids.index(['M01','M02','M03'][i%3]) for i in range(n)]
    for index,(f,g) in enumerate(zip(frames,frames[1:])):
        for q in range(6):
            u=q/6;t=f['t']+u*.05;polys=[];centers=[];pp=[];ww=[]
            for i,(a,b) in enumerate(zip(f['agents'],g['agents'])):
                local=rebuild(np.array(a['pose'])*(1-u)+np.array(b['pose'])*u,lib.parents,lib.lengths)
                pos=np.array(a['pos'])*(1-u)+np.array(b['pos'])*u
                yaw=a['yaw']*(1-u)+b['yaw']*u
                c,s=math.cos(yaw),math.sin(yaw)
                p=local.copy();p[:,0]=c*local[:,0]+s*local[:,2]+pos[0];p[:,2]=-s*local[:,0]+c*local[:,2]+pos[1]
                polys.append(hull(p[:,[0,2]]));centers.append(pos);pp.append(pos);ww.append(p)
                hold_time+=dt*bool(a['hold'])
                if q==0:
                    clip=lib.ids.index(a['clip']);drift.append(float(lib.expression(clip,reference[i])))
                    source=lib.sample(clip,a['phase']);modification.append(float(np.linalg.norm(local-source,axis=1).max()))
                    ref=lib.sample(reference[i],a['phase'])
                    arms=[lib.names.index(x) for x in ['Chest','Head','LowerArm_L','Hand_L','LowerArm_R','Hand_R']]
                    reference_pose_drift.append(float(np.sqrt(np.mean(((local[arms]-local[0])-(ref[arms]-ref[0]))**2))))
                    travel_warp.append(abs(float((a['travel']-lib.angles[clip]+math.pi)%(2*math.pi)-math.pi)))
                    if not a['hold'] and not a['arrived']:speed_ratios.append(a['speed']/lib.speeds[clip])
                    for j,parent in enumerate(lib.parents):
                        if parent is not None and lib.lengths[j]>1e-8:bone_error.append(abs(np.linalg.norm(local[j]-local[parent])/lib.lengths[j]-1))
            root.append(pp);world.append(ww)
            hits=False
            for i in range(n):
                for w in walls:
                    if np.linalg.norm(centers[i]-w.mean(0))>np.linalg.norm(w[0]-w[2])/2+1:continue
                    gap=hull_gap(polys[i],w,.04)
                    if gap<minimum:minimum=gap;worst={'t':t,'agent':i,'wall':w.tolist(),'gap':gap}
                    penetration=max(penetration,-gap);hits|=gap<0
                for j in range(i):
                    if np.linalg.norm(centers[i]-centers[j])>1.6:continue
                    gap=hull_gap(polys[i],polys[j],.08)
                    if gap<minimum:minimum=gap;worst={'t':t,'agents':[i,j],'gap':gap}
                    penetration=max(penetration,-gap);hits|=gap<0
            collision_samples+=int(hits);total+=1
    root=np.array(root);world=np.array(world)
    velocity=np.diff(root,axis=0)/dt;accel=np.diff(velocity,axis=0)/dt
    joint_velocity=np.diff(world,axis=0)/dt;joint_accel=np.diff(joint_velocity,axis=0)/dt
    # Root progress/stagnation is computed from replay, not the selector's reward.
    start=root[0];end=root[-1];goals=np.array(run['spec']['goals'])
    remaining=np.linalg.norm(end-goals,axis=1)
    last_window=min(len(root)-1,round(3/dt))
    stagnant=(np.linalg.norm(root[-1]-root[-1-last_window],axis=1)<.1)&(remaining>.22)
    switches=[];reversals=0
    for i in range(n):
        seq=[f['agents'][i]['clip'] for f in frames]
        compressed=[seq[0]]
        for c in seq[1:]:
            if c!=compressed[-1]:compressed.append(c)
        switches.append(len(compressed)-1)
        reversals+=sum(a==c for a,b,c in zip(compressed,compressed[1:],compressed[2:]))
    return {'minimum_proxy_axis_gap':minimum,'max_proxy_penetration':penetration,'collision_time_fraction':collision_samples/max(total,1),
            'arrived_fraction':len(run['runtime']['arrival_times'])/n,'remaining_goal_distance_mean':float(remaining.mean()),'stagnant_agents':int(stagnant.sum()),
            'emergency_hold_agent_seconds':hold_time,'root_acceleration_p95':float(np.quantile(np.linalg.norm(accel,axis=-1),.95)),
            'root_acceleration_max':float(np.linalg.norm(accel,axis=-1).max()),'joint_speed_p99':float(np.quantile(np.linalg.norm(joint_velocity,axis=-1),.99)),
            'joint_acceleration_p99':float(np.quantile(np.linalg.norm(joint_accel,axis=-1),.99)),
            'max_bone_relative_error':max(bone_error,default=0),'source_pose_modification_max':max(modification,default=0),
            'source_pose_modification_p95':float(np.quantile(modification,.95)),'expression_drift_mean':float(np.mean(drift)),
            'actual_reference_pose_rms':float(np.mean(reference_pose_drift)),'travel_angle_warp_max_radians':max(travel_warp,default=0),
            'actual_speed_ratio_min':min(speed_ratios,default=0),'actual_speed_ratio_max':max(speed_ratios,default=0),
            'switches':sum(switches),'aba_clip_reversals':reversals,'worst':worst,'dense_samples':total,
            'evaluation_hz':120,'proxy':'projected-joint convex hull + radius .04; signed SAT axis gap',**run['runtime']}
