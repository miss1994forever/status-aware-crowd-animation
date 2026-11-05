"""Conservative support candidates from raw WORLD motion, not height alone."""
import math
import statistics
from src.locomotion import source_positions,norm


def runs(mask, circular=False):
    n=len(mask)
    starts=[i for i,v in enumerate(mask) if v and (not mask[(i-1)%n] if circular else i==0 or not mask[i-1])]
    result=[]
    for start in starts:
        end=start
        while end<start+n and (circular or end<n) and mask[end%n]:end+=1
        result.append((start,end))
    return result


def summary(values):
    values=sorted(values)
    return dict(count=len(values),mean=statistics.mean(values),median=statistics.median(values),p95=values[min(len(values)-1,int(.95*len(values)))],max=max(values))


def infer_contacts(motion,cycle):
    p=[source_positions(motion,i) for i in range(len(motion.frames))]
    names=[j.name for j in motion.joints[1:]]
    height=cycle.evidence['source_body_height'];floor=cycle.evidence['source_floor'];dt=motion.frame_time
    start=cycle.evidence['start_frame_zero_based'];period=cycle.evidence['period_frames']
    thresholds=dict(toe_height_body_heights=.012,toe_speed_body_heights_per_second=.18,
                    ankle_speed_body_heights_per_second=.25,min_consecutive_source_frames=3)
    feet=[];diagnostics={}
    for side in ['L','R']:
        hip,knee,ankle,toe=[names.index(k+'_'+side) for k in ['UpperLeg','LowerLeg','Foot','Toes']]
        mask=[];toe_speeds=[];ankle_speeds=[];heights=[]
        for f in range(len(p)):
            a,b=max(0,f-1),min(len(p)-1,f+1)
            def speed(k):return norm([(p[b][k+1][axis]-p[a][k+1][axis])/((b-a)*dt*height) for axis in (0,2)])
            ts,avs=speed(toe),speed(ankle);y=(p[f][toe+1][1]-floor)/height
            toe_speeds.append(ts);ankle_speeds.append(avs);heights.append(y)
            mask.append(y<thresholds['toe_height_body_heights'] and ts<thresholds['toe_speed_body_heights_per_second'] and avs<thresholds['ankle_speed_body_heights_per_second'])
        filtered=[False]*len(mask)
        for a,b in runs(mask):
            if b-a>=3:
                filtered[a:b]=[True]*(b-a)
        periodic=filtered[start:start+period]
        intervals=[]
        for a,b in runs(periodic,True):
            if b-a>=3:intervals.append(dict(start=a/period,duration=(b-a)/period,ramp=min(.065,(b-a)/period/3)))
        if not intervals:raise ValueError('No conservative support interval')
        descendants=[i for i,j in enumerate(motion.joints[1:]) if j.parent==toe+1]
        if any(cycle.bone_lengths[i]>1e-8 for i in descendants):raise ValueError('Contact adapter currently supports zero-length toe end sites only')
        feet.append(dict(side=side,hip=hip,knee=knee,ankle=ankle,toe=toe,ground_reference=statistics.median(heights[i] for i,v in enumerate(filtered) if v),
                         descendants=descendants,intervals=intervals))
        chosen=[i for i,v in enumerate(filtered) if v]
        diagnostics[side]=dict(raw_candidate_frames=chosen,raw_candidate_count=len(chosen),
                               raw_candidate_toe_speed_median=statistics.median(toe_speeds[i] for i in chosen),
                               raw_candidate_toe_speed_max=max(toe_speeds[i] for i in chosen),
                               raw_candidate_toe_height_median=statistics.median(heights[i] for i in chosen),
                               raw_candidate_ankle_speed_median=statistics.median(ankle_speeds[i] for i in chosen),
                               raw_full_cycle_toe_speed=summary(toe_speeds[start:start+period]),
                               raw_selected_cycle_candidate_toe_speed=summary([toe_speeds[i] for i in range(start,start+period) if filtered[i]]),
                               raw_full_recording_toe_speed=summary(toe_speeds),minimum_raw_toe_y_relative_display_ground=min(heights))
    return dict(feet=feet,thresholds=thresholds,raw_diagnostics=diagnostics,
                inference='candidate support from raw world toe height AND toe/ankle horizontal speed AND >=3 consecutive frames; no heel or ground-truth contact labels')
