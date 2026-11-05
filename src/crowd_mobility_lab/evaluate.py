"""Independent replay metrics extend frozen 120 Hz body audit, never chooser costs."""
import numpy as np
from src.predictive_motion_lab.evaluate import audit
from src.predictive_motion_lab.geometry import world_pose
from src.expression_layer import personal_library,upper_mask


def evaluate(run,base):
    m=audit(run,base)
    frames=run['frames'];n=len(frames[0]['agents']);dt=.05
    pos=np.array([[a['pos'] for a in f['agents']] for f in frames])
    poses=np.array([[a['pose'] for a in f['agents']] for f in frames])
    yaw=np.array([[a['yaw'] for a in f['agents']] for f in frames])
    world=world_pose(poses,pos,yaw)
    length=np.linalg.norm(np.diff(pos,axis=0),axis=-1).sum(0)
    direct=np.linalg.norm(np.array(run['spec']['goals'])-np.array(run['spec']['starts']),axis=-1)
    arrived=np.array([str(i) in run['runtime']['arrival_times'] or i in run['runtime']['arrival_times'] for i in range(n)])
    speed=np.linalg.norm(np.diff(pos,axis=0),axis=-1)/dt
    active=np.array([[not a['arrived'] for a in f['agents']] for f in frames[:-1]])
    slow=(speed<.05)&active
    v=np.diff(world,axis=0)/dt;jump=np.linalg.norm(np.diff(v,axis=0),axis=-1)
    jmask=active[1:]&active[:-1]
    refs=np.array([base.ids.index(run['spec'].get('reference','M02')) if n==1 else base.ids.index(['M01','M02','M03'][i%3]) for i in range(n)])
    personal={r:personal_library(base,int(r),run.get('layer_strength',0)) for r in set(refs)}
    upper=np.where(upper_mask(base))[0];directions=[];moving_directions=[];residual=[]
    for i in range(n):
        phases=np.array([f['agents'][i]['phase'] for f in frames]);clips=np.array([base.ids.index(f['agents'][i]['clip']) for f in frames])
        reference=base.sample(refs[i],phases);source=personal[refs[i]].sample(clips,phases)
        residual.append(float(np.linalg.norm(poses[:,i]-source,axis=-1).max()))
        err=[]
        for j in upper:
            p=base.parents[j]
            if p is not None and base.lengths[j]>1e-6:err.append(np.sum(((poses[:,i,j]-poses[:,i,p])-(reference[:,j]-reference[:,p]))**2,axis=-1)/base.lengths[j]**2)
        error=np.mean(err,axis=0);directions.extend(error.tolist())
        moving_directions.extend(error[:-1][(speed[:,i]>.05)&active[:,i]].tolist())
    m.update(path_length_per_agent=length.tolist(),path_stretch_per_agent=(length/direct).tolist(),
        completed_path_stretch_mean=float(np.mean((length/direct)[arrived])) if arrived.any() else None,
        actual_slow_active_agent_seconds=float(slow.sum()*dt),moving_active_fraction=float(((speed>.05)&active).sum()/max(1,active.sum())),
        completed_arrival_time_mean=float(np.mean(list(run['runtime']['arrival_times'].values()))) if arrived.any() else None,
        active_joint_velocity_change_p99=float(np.quantile(jump[jmask],.99)) if jmask.any() else None,
        active_joint_velocity_change_max=float(jump[jmask].max()) if jmask.any() else None,
        upper_reference_direction_rms=float(np.sqrt(np.mean(directions))),upper_reference_direction_rms_moving=float(np.sqrt(np.mean(moving_directions))) if moving_directions else None,
        synthesized_source_residual_max=max(residual),
        evaluation_note='120Hz body hull audit; path/active motion and direction metrics 20Hz. Direction closeness is not status or naturalness.')
    return m
