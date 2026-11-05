"""R1 hand-motion diagnostics from positions; no gesture/status classifier.

Usage: python scripts/analyze_signal_hands.py
No semantic event boundary is inferred. End window means final 1.0 seconds.
"""
from pathlib import Path
import json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'outputs/social-signal-review'

def angle(a,b):
    den=np.linalg.norm(a,axis=-1)*np.linalg.norm(b,axis=-1)
    if np.any(den<1e-9): raise ValueError('Degenerate direction')
    return np.degrees(np.arccos(np.clip(np.sum(a*b,axis=-1)/den,-1,1)))

def summary(x,t):
    tail=t>=t[-1]-1.0
    def part(y):
        return dict(min=float(y.min()),max=float(y.max()),range=float(np.ptp(y)),median=float(np.median(y)),total_absolute_change=float(np.abs(np.diff(y)).sum()))
    return dict(full=part(x),final_1s=part(x[tail]))

def main():
    source=json.loads((FOLDER/'clips.json').read_text())
    assert source[0]['name']==source[1]['name']=='A', 'Expected known duplicated first A'
    rows=[]
    for c in source[1:]:
        p=np.array(c['positions'],dtype=float);names=c['names'];t=np.arange(len(p))*c['dt']
        def j(n):return p[:,names.index(n)]
        sides={}
        for side in ('r','l'):
            prefix='b_'+side+'_';w=j(prefix+'wrist');elbow=j(prefix+'forearm');forearm=w-elbow
            hand=j(prefix+'middle1')-w
            normal=np.cross(j(prefix+'index1')-w,j(prefix+'pinky1')-w)
            metrics={
                'hand_forearm_bend_deg':angle(forearm,hand),
                'palm_normal_forearm_angle_deg':angle(forearm,normal),
            }
            for finger in ('index','middle','ring','pinky'):
                a,b,d=[j(prefix+finger+str(k)) for k in (1,2,3)]
                metrics[finger+'_proximal_bend_deg']=angle(a-w,b-a)
                metrics[finger+'_middle_bend_deg']=angle(b-a,d-b)
            a,b,d=[j(prefix+'thumb'+str(k)) for k in (1,2,3)]
            metrics['thumb_middle_bend_deg']=angle(b-a,d-b)
            metrics['thumb_distal_segment_vertical_angle_deg']=angle(d-b,np.broadcast_to([0.,1.,0.],d.shape))
            metrics['thumb3_index3_distance_m']=np.linalg.norm(d-j(prefix+'index3'),axis=-1)
            # Scale-normalized separation avoids raw hand-size differences, not a contact metric.
            palm_length=np.linalg.norm(hand,axis=-1)
            metrics['thumb3_index3_distance_over_palm_length']=metrics['thumb3_index3_distance_m']/palm_length
            sides[side]=dict(metrics={k:summary(v,t) for k,v in metrics.items()},series={k:np.round(v,6).tolist() for k,v in metrics.items()})
        rows.append(dict(id=c['name'],duration_s=float(t[-1]),dt=c['dt'],time_s=np.round(t,6).tolist(),sides=sides))
    out=dict(
        scope='A-E once each; duplicated preview A excluded. Descriptive diagnostics, not status or gesture classification.',
        definitions={
            'hand_forearm_bend_deg':'Angle between elbow-to-wrist and wrist-to-middle1. Translation and whole-body rotation invariant; does not capture all wrist axial rotation.',
            'palm_normal_forearm_angle_deg':'Angle between forearm and cross(wrist-to-index1,wrist-to-pinky1). Side normal sign depends on skeleton convention; compare temporal changes within side, not raw left/right values.',
            'finger_proximal_bend_deg':'Angle between wrist-to-finger1 and finger1-to-finger2; geometric proxy, not calibrated MCP anatomical flexion.',
            'finger_middle_bend_deg':'Angle between finger1-to-finger2 and finger2-to-finger3; zero means straight aligned segments.',
            'thumb_distal_segment_vertical_angle_deg':'World vertical comparison only for inspecting thumbs-up-like configurations. Includes arm and whole-body motion and is NOT a gesture label.',
            'thumb3_index3_distance_m':'Distance between retained distal joint centers, NOT fingertips or surfaces.',
            'total_absolute_change':'Sum of absolute intersample changes; duration/noise sensitive, not a naturalness or confidence score.'
        },
        limitations=[
            'Only sampled positions from 24fps FBX import, rounded to micrometers; no source mesh or rotations evaluated here.',
            'Finger end/null nodes are omitted; distal segment/end-tip orientation and fingertip contact cannot be established.',
            'Small changes can reflect tracking/import noise. No precision calibration or confidence interval available.',
            'Final 1 second is a file-tail window, not annotated post-greeting time. No causal or status inference.',
            'Pinching, fidgeting, thumbs-up intent and hand-on-hip contact require source visualization; geometric diagnostics cannot establish these alone.',
            'Wrist-center translation is deliberately not used to decide whether a greeting exists; micro wrist/finger gestures may occur without significant translation.'
        ],rows=rows)
    def rounded(o):
        if isinstance(o,float):return round(o,6)
        if isinstance(o,dict):return {k:rounded(v) for k,v in o.items()}
        if isinstance(o,list):return [rounded(v) for v in o]
        return o
    out=rounded(out)
    (FOLDER/'hand-analysis.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    for r in out['rows']:
        print(r['id'], {s:{k:r['sides'][s]['metrics'][k] for k in ('hand_forearm_bend_deg','index_middle_bend_deg','thumb3_index3_distance_m')} for s in ('r','l')})
if __name__=='__main__':main()
