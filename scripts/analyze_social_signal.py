"""Descriptive kinematics for R1; not a status estimator or causal analysis."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'outputs/social-signal-review'
clips=json.loads((folder/'clips.json').read_text())[1:]
rows=[]
for c in clips:
 p=np.asarray(c['positions']);dt=c['dt'];names=c['names']
 def joint(n):return p[:,names.index(n)]
 root=joint('b_root');neck=joint('b_neck0');trunk=neck-root
 lean=np.degrees(np.arctan2(np.linalg.norm(trunk[:,[0,2]],axis=1),trunk[:,1]))
 # Root-relative wrist speed: avoids treating root translation as hand expression.
 wrist=joint('b_r_wrist')-root
 speed=np.linalg.norm(np.gradient(wrist,dt,axis=0),axis=1)
 span=np.linalg.norm(joint('b_r_wrist')-joint('b_l_wrist'),axis=1)
 k=int(np.argmax(span));peak=int(np.argmax(speed))
 rows.append(dict(id=c['name'],duration_s=round((len(p)-1)*dt,3),wrist_span_max_m=round(float(span[k]),3),span_peak_s=round(k*dt,3),right_wrist_speed_p95_mps=round(float(np.percentile(speed,95)),3),right_wrist_speed_peak_s=round(peak*dt,3),trunk_tilt_median_deg=round(float(np.median(lean)),2),trunk_tilt_p95_deg=round(float(np.percentile(lean,95)),2),root_vertical_range_m=round(float(np.ptp(root[:,1])),3)))
result=dict(method='Original 24fps joint positions; no smoothing. Wrist span is 3D wrist-to-wrist distance. Right wrist speed is relative to root; finite differences. Trunk tilt is root-to-neck deviation from world vertical, not head gaze, chest expansion or center of mass. Maxima are inspection markers, not semantic phases. No paired alignment, statistical inference, status score or causal claim.',rows=rows)
(folder/'kinematics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
