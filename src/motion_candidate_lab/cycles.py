"""Kinematic recurrence search and bounded Cartesian closure, authored here.

Numpy is used only for array arithmetic. FK and cyclic interpolation reuse the
project implementation. Search bounds/acceptance limits are engineering gates,
not validated human-naturalness thresholds.
"""
import math
import numpy as np
from src.locomotion import Cycle


def describe(motion, reference_height=None):
    world = np.array([motion.positions(i, translation_mode='channels_replace_offset')
                      for i in range(len(motion.frames))])[:, 1:]
    names = [j.name for j in motion.joints[1:]]
    hips, head = names.index('Hips'), names.index('Head')
    feet = [names.index('Toes_L'), names.index('Toes_R')]
    measured_height = float(np.median(world[:, head, 1]-world[:, feet, 1].min(axis=1)))
    height = reference_height or measured_height
    lateral = (world[:, names.index('Shoulder_L')]-world[:, names.index('Shoulder_R')]).mean(axis=0)[[0, 2]]
    forward = np.array([-lateral[1], lateral[0]])
    forward /= np.linalg.norm(forward)
    heading = math.atan2(*forward)
    shoulder_delta=world[:,names.index('Shoulder_L')]-world[:,names.index('Shoulder_R')]
    shoulder_heading=np.unwrap(np.arctan2(-shoulder_delta[:,2],shoulder_delta[:,0]))
    co, si = math.cos(heading), math.sin(heading)
    rotate = np.array([[co, 0, -si], [0, 1, 0], [si, 0, co]])
    origin = world[0, hips].copy(); origin[1] = world[:, feet, 1].min()
    local = (world-origin) @ rotate.T / height
    relative = local-local[:, hips:hips+1]
    parents = [None if j.parent in (None, 0) else j.parent-1 for j in motion.joints[1:]]
    lengths = [0 if p is None else float(np.median(np.linalg.norm(local[:, j]-local[:, p], axis=1)))
               for j, p in enumerate(parents)]
    velocity = np.gradient(local, motion.frame_time, axis=0)
    travel = local[-1, hips]-local[0, hips]
    speeds = np.linalg.norm(velocity[:, hips][:, [0, 2]], axis=1)
    foot_floor = local[:,feet,1].min()
    foot_speeds = np.linalg.norm(velocity[:,feet][:,:,[0,2]],axis=2)[local[:,feet,1]<foot_floor+.025]
    # Label-preserving left/right feet prevent half-stride swaps from masquerading as a full cycle.
    features = relative[:, feet].reshape(len(local), -1)
    features -= features.mean(axis=0)
    low = max(8, round(.65/motion.frame_time))
    high = min(round(2.8/motion.frame_time), (len(local)-1)//2)
    recurrence = []
    for lag in range(low, high+1):
        a, b = features[:-lag], features[lag:]
        denominator = np.sqrt((a*a).mean()*(b*b).mean())
        corr = float((a*b).mean()/max(denominator, 1e-12))
        recurrence.append({'frames': lag, 'seconds': lag*motion.frame_time, 'correlation': corr})
    peaks = [r for i, r in enumerate(recurrence) if 0<i<len(recurrence)-1
             and r['correlation'] >= recurrence[i-1]['correlation']
             and r['correlation'] >= recurrence[i+1]['correlation']]
    peaks.sort(key=lambda r: (-r['correlation'], r['frames']))
    strong = [r for r in peaks if r['correlation'] >= max(.65,peaks[0]['correlation']-.05)] if peaks else []
    selected_peak = min(strong,key=lambda r:r['frames']) if strong else (peaks[0] if peaks else None)
    return dict(local=local, relative=relative, velocity=velocity, names=names, parents=parents,
                lengths=lengths, feet=feet, hips=hips, height=height, heading=heading,
                dt=motion.frame_time, recurrence=recurrence, peaks=peaks, selected_peak=selected_peak,
                metadata={'frame_count':len(local), 'sample_interval_seconds':motion.frame_time,
                          'sample_span_seconds':(len(local)-1)*motion.frame_time,
                          'held_playback_seconds':len(local)*motion.frame_time,
                          'reference_height_source_units':height,
                          'measured_head_to_toe_height_source_units':measured_height,
                          'anatomical_heading_radians':heading,
                          'shoulder_heading_p95_minus_p05_degrees':float(np.degrees(np.quantile(shoulder_heading,.95)-np.quantile(shoulder_heading,.05))),
                          'travel_body_heights_xz':travel[[0,2]].tolist(),
                          'travel_relative_facing_degrees':math.degrees(math.atan2(travel[0],travel[2])),
                          'hip_speed_body_heights_per_second':{'p05':float(np.quantile(speeds,.05)), 'median':float(np.median(speeds)), 'p95':float(np.quantile(speeds,.95))},
                          'source_low_toe_height_speed_proxy':{'samples':len(foot_speeds),'median':float(np.median(foot_speeds)) if len(foot_speeds) else None,'p95':float(np.quantile(foot_speeds,.95)) if len(foot_speeds) else None,'max':float(foot_speeds.max()) if len(foot_speeds) else None},
                          'recurrence_peaks':peaks[:5], 'selected_recurrence_peak':selected_peak})


def choose(info, fixed=False):
    p, rel, vel = info['local'], info['relative'], info['velocity']
    if fixed:
        periods = range(24,43)
    elif info['peaks']:
        # Dominant repeat needs two observed periods; +/-15% allows slow local rhythm drift.
        peak = info['selected_peak']['frames']
        periods = range(max(8,round(peak*.85)),round(peak*1.15)+1)
    else:
        return []
    rows=[]
    for period in periods:
        for start in range(8,len(p)-period-8):
            end=start+period
            drift=(p[end,info['hips']]-p[start,info['hips']]).copy();drift[1]=0
            delta=p[end]-p[start]-drift
            e=float(np.sqrt(np.mean(np.sum(delta*delta,axis=1))))
            v=float(np.sqrt(np.mean(np.sum((vel[end]-vel[start])**2,axis=1))))
            # Reject endpoints that match by coincidence but whose neighbouring poses do not.
            context=float(np.sqrt(np.mean((rel[start-3:start+4]-rel[end-3:end+4])**2)))
            score=e+.08*v+(0 if fixed else .5*context)
            rows.append(dict(start=start,end=end,period_frames=period,score=score,
                             raw_seam_position_rms=e, raw_seam_velocity_rms=v,
                             context_rms=context,stride=float(np.linalg.norm(drift))))
    return sorted(rows,key=lambda r:(r['score'],r['start']))


def construct(info, row):
    start,end=row['start'],row['end']; n=end-start; dt=info['dt']
    p=info['local']; origin=p[start,info['hips']].copy();origin[1]=0
    drift=(p[end,info['hips']]-p[start,info['hips']])/n;drift[1]=0
    raw=p[start:end+1]-origin-np.arange(n+1)[:,None,None]*drift
    local=raw.copy(); tangent=(info['velocity'][start:end+1]-drift/dt)*(n*dt)
    d=local[-1]-local[0];dv=tangent[0]-tangent[-1]
    u=np.linspace(0,1,n+1)[:,None,None]
    correction=(dv+2*d)*u**3+(-dv-3*d)*u**2
    local+=correction
    tangent+=(3*(dv+2*d)*u**2+2*(-dv-3*d)*u)
    evidence={**row,'period_seconds':n*dt,'native_speed':row['stride']/(n*dt),
              'travel_heading_relative_body':math.atan2(drift[0],drift[2]),
              'max_cartesian_correction':float(np.linalg.norm(correction,axis=2).max())}
    cycle=Cycle(local.tolist(),tangent.tolist(),row['stride'],evidence,info['parents'],info['lengths'])
    cycle.source_poses=raw.tolist()
    if row['stride']<1e-5:
        raise ValueError('No usable travel')
    out=np.array([cycle.sample(row['stride']*f/n) for f in range(n+1)])
    bone_error=[]; raw_bone_variation=[]
    for j,parent in enumerate(info['parents']):
        if parent is None or info['lengths'][j]<1e-6:continue
        bone_error.extend(abs(np.linalg.norm(out[:,j]-out[:,parent],axis=1)/info['lengths'][j]-1))
        raw_bone_variation.extend(abs(np.linalg.norm(raw[:,j]-raw[:,parent],axis=1)/info['lengths'][j]-1))
    changes=np.linalg.norm(out-raw,axis=2)
    eps=1e-5;stride=row['stride'];duration=n*dt
    left=np.array(cycle.sample(stride*(1-eps)));right=np.array(cycle.sample(stride*eps));zero=np.array(cycle.sample(0))
    vm=(zero-left)/(duration*eps);vp=(right-zero)/(duration*eps)
    # Canonical phase: left toe furthest forward relative hips. No pose is edited to align phase.
    left_forward=out[:,info['feet'][0],2]-out[:,info['hips'],2]
    evidence.update(max_output_change=float(changes.max()),rms_output_change=float(np.sqrt((changes**2).mean())),
                    max_output_bone_relative_error=float(max(bone_error,default=0)),
                    source_bone_relative_variation=float(max(raw_bone_variation,default=0)),
                    seam_position_epsilon_rms=float(np.sqrt(((right-left)**2).mean())),
                    seam_velocity_epsilon_rms=float(np.sqrt(((vp-vm)**2).mean())),
                    phase_offset=float(np.argmax(left_forward)/n))
    return cycle


def audit(motion, reference_height=None):
    info=describe(motion, reference_height); methods={}; cycle_objects={}
    for method,fixed in [('baseline',True),('improved',False)]:
        rows=choose(info,fixed)
        if not rows:
            methods[method]={'accepted':False,'reasons':['不足两个可测周期或未发现内部相关峰'],'candidates':[]}
            continue
        def assess(ev):
            reasons=[]
            if not fixed and (not info['selected_peak'] or info['selected_peak']['correlation']<.65):reasons.append('全片重复相关性低于0.65')
            if ev['max_output_change']>.05:reasons.append('最大节点改动超过参考身高5%')
            if ev['raw_seam_position_rms']>.025:reasons.append('原始接缝位置RMS超过身高2.5%')
            if ev['seam_velocity_epsilon_rms']>.015:reasons.append('最终重建接缝速度差超过0.015身高/秒')
            if len(info['local'])<2*ev['period_frames']+16:reasons.append('原片不含两个完整观察周期及边界余量')
            return reasons
        trials=[];cycle=None;reasons=[]
        for rank,row in enumerate(rows[:1] if fixed else rows[:8]):
            attempt=construct(info,row);failures=assess(attempt.evidence)
            trials.append({'rank':rank,'evidence':attempt.evidence.copy(),'reasons':failures})
            if rank==0:cycle=attempt;reasons=failures
            if not failures:cycle=attempt;reasons=[];break
        ev=cycle.evidence
        ev['selected_rank']=next(t['rank'] for t in trials if t['evidence']['start']==ev['start'] and t['evidence']['end']==ev['end'])
        methods[method]={'accepted':not reasons,'reasons':reasons or ['通过工程循环门槛；自然性待看'],'evidence':ev,'candidates':rows[:8],'closure_trials':trials}
        cycle_objects[method]=cycle
    return info,methods,cycle_objects


def serialize(cycle):
    return dict(poses=cycle.poses,tangents=cycle.tangents,stride=cycle.stride,
                source_poses=cycle.source_poses,
                parents=cycle.parents,bone_lengths=cycle.bone_lengths,evidence=cycle.evidence)
