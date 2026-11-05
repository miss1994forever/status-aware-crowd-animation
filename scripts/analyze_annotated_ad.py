"""Descriptive A/D comparison using user event boundaries, not inferred events."""
from pathlib import Path
import json
import numpy as np
R=Path(__file__).resolve().parents[1];O=R/'outputs/social-signal-review'
ann=json.loads((R/'data/research/annotations/ad-confirmed-2026-11-02.json').read_text())
post=json.loads((O/'posture-analysis.json').read_text());space=json.loads((O/'space-analysis.json').read_text())
rows=[]
for ident in ['A','D']:
 e=ann['events'][ident];on,g,off=[e[k] for k in ['onset','gesture','offset']];assert 0<=on<g<off
 p=next(x for x in post['rows'] if x['id']==ident);s=next(x for x in space['rows'] if x['id']==ident);t=np.array(p['times_s'])
 series={k:np.array(v['series']) for k,v in p['metrics'].items()}
 for k in ['l_elbow_outward_from_midline_m','l_wrist_outward_from_midline_m']:series[k]=np.array(s['series'][k])
 m={}
 for k,v in series.items():
  at={n:float(np.interp(tm,t,v)) for n,tm in [('onset',on),('gesture',g),('offset',off)]}
  m[k]={'at_events':at,'gesture_minus_onset':at['gesture']-at['onset'],'offset_minus_onset':at['offset']-at['onset']}
  for name,a,b in [('pre',max(0,on-.5),on),('greeting',on,off),('post',off,min(t[-1],off+.5))]:
   mask=(t>=a)&(t<b);tt=t[mask];vv=v[mask];i=int(np.argmax(vv));j=int(np.argmin(vv));m[k][name]={'window_s':[a,b],'mean':float(vv.mean()),'min':float(vv[j]),'max':float(vv[i]),'min_time_s':float(tt[j]),'max_time_s':float(tt[i])}
 rows.append({'id':ident,'events':e,'durations_s':{'onset_to_gesture':g-on,'gesture_to_offset':off-g,'total':off-on},'metrics':m})
result={'source':'data/research/annotations/ad-confirmed-2026-11-02.json','limitations':['Single observer single takes; no independent evaluation or causal conclusion.','Main gesture is a user-selected instant, not beginning/end of a hold.','Pre-onset 0.5s can include preparatory movements; not neutral baseline.','Endpoint values linearly interpolated from 24fps; millisecond annotations do not imply millisecond motion accuracy.','Post window is 0.5s after user offset; joint flexion is not confidence or muscle tension.'],'rows':rows}
(O/'annotated-ad-analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
for r in rows:
 print(r['id'],r['durations_s'])
 for k in ['r_knee_flexion_deg','pelvis_height_m','root_neck_tilt_deg','l_wrist_outward_from_midline_m']:
  z=r['metrics'][k];print(k,{q:round(z[q],4) for q in ['gesture_minus_onset','offset_minus_onset']},'peak',z['greeting']['max_time_s'])
