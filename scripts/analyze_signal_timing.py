"""R1 relative-height threshold sensitivity; not semantic greeting segmentation."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'outputs/social-signal-review'

def intervals(mask,dt):
    # Boundary at half a sample between observed classifications, clamped to clip.
    edges=np.diff(np.r_[False,mask,False].astype(int))
    starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)-1
    result=[]
    for a,b in zip(starts,ends):
        start=max(0.,(a-.5)*dt);end=min((len(mask)-1)*dt,(b+.5)*dt)
        result.append({'start_s':round(start,6),'end_s':round(end,6),
                       'duration_s':round(end-start,6),'first_frame':int(a),'last_frame':int(b)})
    return result

def main():
    clips=json.loads((FOLDER/'clips.json').read_text())[1:]
    absolute={r['id']:r for r in json.loads((FOLDER/'greeting-analysis.json').read_text())['rows']}
    rows=[]
    for c in clips:
        p=np.asarray(c['positions']);names=c['names'];dt=c['dt'];times=np.arange(len(p))*dt
        root=p[:,names.index('b_root')]
        row={'id':c['name'],'duration_s':round(float(times[-1]),6),'hands':{}}
        for side in ['l','r']:
            height=p[:,names.index(f'b_{side}_wrist'),1]-root[:,1]
            baseline=float(np.mean(height[times<.5]));rise=float(height.max()-baseline)
            hand={'baseline_height_above_pelvis_m':round(baseline,6),
                  'peak_rise_from_baseline_m':round(rise,6),
                  'full_height_range_m':round(float(np.ptp(height)),6),
                  'applicable':rise>=.02,
                  'reason':None if rise>=.02 else 'Peak rise from initial reference is under 2 cm; relative uplift timing not applicable, not zero-duration greeting.',
                  'thresholds':[]}
            if rise>=.02:
                for fraction in [.3,.5,.7]:
                    threshold=baseline+fraction*rise
                    spans=intervals(height>threshold,dt)
                    hand['thresholds'].append({'fraction_of_rise':fraction,'height_above_pelvis_threshold_m':round(threshold,6),
                        'intervals':spans,'total_duration_s':round(sum(i['duration_s'] for i in spans),6),
                        'interval_count':len(spans)})
            else:
                hand['total_duration_s']=None
            row['hands'][side]=hand
        row['prior_absolute_right_wrist_thresholds']=absolute[c['name']]['height_thresholds']
        rows.append(row)
    result={'method':{
        'reference':'Mean wrist height relative to pelvis over 0 <= t < 0.5 s. Not an annotated pre-greeting baseline.',
        'amplitude':'Maximum upward height minus initial reference, independently per hand. No body-height normalization.',
        'applicability':'Peak rise < 0.02 m is marked not applicable; this excludes uplift timing only, not wrist rotation, finger movement, or greeting occurrence.',
        'thresholds':'30%, 50%, 70% of each hand own positive rise, added to its own reference. All contiguous supra-threshold runs retained without merging or minimum-duration filtering.',
        'boundaries':'Half-sample crossings, clamped to clip start/end; 24Hz source. These are approximate observed-height intervals, not semantic preparation/hold/retraction phases.',
        'comparison':'Absolute thresholds confound amplitude with duration. Relative thresholds reduce that particular scale dependence but remain affected by path shape, initial reference, multiple events and peak choice; no clean causal timing separation.',
        'interpretation':'No status, hesitation, smoothness or intention inference. Threshold sensitivity is not observer validation.',
    },'rows':rows}
    (FOLDER/'timing-analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for r in rows:
        print(r['id'],{side: {'rise_m':h['peak_rise_from_baseline_m'],'durations_s':[(t['fraction_of_rise'],t['total_duration_s'],t['interval_count']) for t in h['thresholds']] if h['applicable'] else None} for side,h in r['hands'].items()})

if __name__=='__main__':main()
