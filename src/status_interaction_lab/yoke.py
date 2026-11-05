"""Offline auxiliary control replay: another agent's encounter, geometry stays online.

Uses a completed donor C2 run solely to construct the diagnostic signal. This is
not an online inference system and is never used in main C1/C2 comparisons.
"""
import numpy as np


def matched_yoke(run):
    n=len(run['frames'][0]['agents']);steps=round(run['spec']['duration']/.2)
    signals=np.zeros((n,steps));onsets=[];features=[]
    for i in range(n):
        rows=[d for d in run['decisions'] if d['id']==i]
        active=[d for d in rows if d['response']['observations']]
        onset=round(active[0]['t']/.2) if active else 0;onsets.append(onset)
        distances=[o['distance'] for d in active for o in d['response']['observations']]
        features.append([len(active)/steps,min(distances,default=2.5)/2.5,max([len(d['response']['observations']) for d in active],default=0)/max(n-1,1)])
        for d in rows:signals[i,round(d['t']/.2)]=d['response']['social']
    features=np.array(features);mapping={};records=[]
    for i in range(n):
        scores=np.sum((features-features[i])**2,axis=1);scores[i]=np.inf;j=int(np.argmin(scores))
        shift=onsets[i]-onsets[j];signal=np.zeros(steps)
        for k in range(steps):
            if 0<=k-shift<steps:signal[k]=signals[j,k-shift]
        # Match total squared requested response energy where possible. Cap prevents
        # amplification of nearly empty donors; residual mismatch is reported.
        ratio=float(np.sqrt(np.sum(signals[i]**2)/max(np.sum(signal**2),1e-12)))
        scale=float(np.clip(ratio,.5,2));signal*=scale
        for k,v in enumerate(signal):mapping[k,i]=float(v)
        records.append(dict(recipient=i,donor=j,geometry_feature_distance=float(scores[j]),shift_steps=shift,scale=scale,
             target_requested_energy=float(np.sum(signals[i]**2)),yoked_requested_energy=float(np.sum(signal**2))))
    return mapping,records
