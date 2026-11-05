"""Raw sequence inspection only: no cycling, retargeting, or status labels."""
import numpy as np


def positions(motion, translation_mode='offset_plus_channels'):
    """Batched FK matching src.bvh.Motion.positions, in original coordinates."""
    if translation_mode not in ('offset_plus_channels','channels_replace_offset'):
        raise ValueError(translation_mode)
    data=np.asarray(motion.frames);n=len(data);worlds=[]
    for joint in motion.joints:
        local=np.broadcast_to(np.eye(4),(n,4,4)).copy()
        offset=np.array(joint.offset,dtype=float)
        if translation_mode=='channels_replace_offset':
            seen=False
            for channel in joint.channels:
                if channel.endswith('rotation'):seen=True
                else:
                    if seen:raise ValueError('Replacement requires translations before rotations')
                    offset['XYZ'.index(channel[0])]=0
        local[:,:3,3]=offset
        for k,channel in enumerate(joint.channels):
            axis='XYZ'.index(channel[0]);value=data[:,joint.channel_start+k]
            transform=np.broadcast_to(np.eye(4),(n,4,4)).copy()
            if channel.endswith('position'):transform[:,axis,3]=value
            else:
                angle=np.deg2rad(value);a,b=(axis+1)%3,(axis+2)%3
                transform[:,a,a]=transform[:,b,b]=np.cos(angle)
                transform[:,a,b]=-np.sin(angle);transform[:,b,a]=np.sin(angle)
            local=local@transform
        worlds.append(local if joint.parent is None else worlds[joint.parent]@local)
    return np.stack([w[:,:3,3] for w in worlds],axis=1)


def low_speed_intervals(world,dt,hips,height,min_seconds=.35,threshold=.10):
    """Review candidates, NOT stop/interaction annotations.

    Moving-average root velocity suppresses cyclic pelvis sway. Threshold is an
    explicit development heuristic in reference heights per second.
    """
    v=np.gradient(world[:,hips][:,[0,2]],dt,axis=0)/height
    width=min(len(v),max(1,round(.25/dt)))
    v=np.stack([np.convolve(v[:,i],np.ones(width)/width,mode='same') for i in range(2)],-1)
    speed=np.linalg.norm(v,axis=-1);mask=speed<threshold
    edges=np.diff(np.r_[False,mask,False].astype(int))
    spans=[dict(start_frame=int(a),end_frame_exclusive=int(b),start_seconds=float(a*dt),end_seconds=float(b*dt))
           for a,b in zip(np.where(edges==1)[0],np.where(edges==-1)[0]) if (b-a)*dt>=min_seconds]
    return dict(threshold=threshold,min_seconds=min_seconds,smoothing_seconds=width*dt,
                intervals=spans,speed_p05_p50_p95=np.quantile(speed,[.05,.5,.95]).tolist(),
                note='Low root speed only: not validated stopping, weight transfer, interaction or status.')
