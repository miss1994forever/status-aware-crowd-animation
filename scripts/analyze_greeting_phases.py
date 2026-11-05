"""R1 threshold sensitivity, not semantic segmentation or a status model."""
import json
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1];folder=root/'outputs/social-signal-review'
clips=json.loads((folder/'clips.json').read_text())[1:]
rows=[]
for c in clips:
 p=np.array(c['positions']);dt=c['dt'];names=c['names'];j=lambda n:p[:,names.index(n)]
 # Body lateral axis from left to right upper-arm origins (shoulder joints).
 axis=j('b_r_arm')-j('b_l_arm');axis[:,1]=0;axis/=np.linalg.norm(axis,axis=1)[:,None]
 center=(j('b_r_arm')+j('b_l_arm'))/2
 rw=j('b_r_wrist');lw=j('b_l_wrist');pelvis=j('b_root')
 # Fixed world-height relative to pelvis; not a claim of start/end of greeting.
 height=rw[:,1]-pelvis[:,1]
 speed=np.linalg.norm(np.gradient(rw-pelvis,dt,axis=0),axis=1)
 def duration(mask):return float(np.trapz(mask.astype(float),dx=dt))
 measures=[]
 for h in [.1,.2,.3]:
  active=height>h
  inds=np.flatnonzero(active)
  measures.append(dict(wrist_above_pelvis_m=h,total_s=round(duration(active),3),first_s=round(float(inds[0]*dt),3) if len(inds) else None,last_s=round(float(inds[-1]*dt),3) if len(inds) else None,slow_s={str(v):round(duration(active&(speed<v)),3) for v in [.1,.2,.3]}))
 lateral={}
 for name,key in [('b_l_forearm','left_elbow'),('b_l_wrist','left_wrist')]:
  dist=np.abs(np.sum((j(name)-center)*axis,axis=1))
  lateral[key]=dict(median_m=round(float(np.median(dist)),3),p95_m=round(float(np.percentile(dist,95)),3),during_right_wrist_above_20cm_median_m=round(float(np.median(dist[height>.2])),3) if np.any(height>.2) else None)
 rows.append(dict(id=c['name'],height_thresholds=measures,left_side=lateral))
result=dict(method='Assumes right hand is greeting hand; body lateral axis from upper arm origins, projected horizontally. Distances from shoulder midpoint, not surface occupancy. Wrist elevation relative to pelvis; low speed relative to translating pelvis, not rotation compensated. Thresholds are diagnostics, not semantic phases. Trapezoidal sample duration; single takes, no inferential statistics.',rows=rows)
(folder/'greeting-analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for x in rows:
 if x['id'] in ['B','C','D']:print(json.dumps(x))
