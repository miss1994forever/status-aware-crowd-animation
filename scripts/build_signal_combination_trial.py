"""Coordinated geometric contraction hypothesis, not a learned status mapping."""
from pathlib import Path
import json,re
import numpy as np
R=Path(__file__).resolve().parents[1];O=R/'outputs/social-signal-review'
sources=json.loads((O/'clips.json').read_text())[1:];c=next(x for x in sources if x['name']=='D');p=np.array(c['positions']);legs=next(x for x in json.loads((O/'posture-trial-clips.json').read_text()) if x['name']=='D-height-suppressed');q=np.array(legs['positions']);names=c['names'];parents=c['parents'];events=json.loads((R/'data/research/annotations/ad-confirmed-2026-11-02.json').read_text())['events']['D'];t=np.arange(len(p))*c['dt'];u=np.clip((t-events['onset'])/(events['gesture']-events['onset']),0,1);w=u*u*(3-2*u)
idx=lambda n:names.index(n)
def descendants(root):
 result=[]
 for j in range(len(names)):
  k=j
  while k>=0 and k!=root:k=parents[k]
  if k==root:result.append(j)
 return result
spine=idx('b_spine0');neck=idx('b_neck0');arm=idx('b_l_arm');elbow=idx('b_l_forearm');trunk=descendants(spine);head=descendants(neck);left=descendants(arm)
def unit(v):return v/np.linalg.norm(v)
def matrix(axis,angle):
 a=unit(axis);K=np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]]);return np.eye(3)+np.sin(angle)*K+(1-np.cos(angle))*(K@K)
def rotate(frame,ids,pivot,axis,angle):frame[ids]=(frame[ids]-pivot)@matrix(axis,angle).T+pivot
for f in range(len(q)):
 side=unit(p[f,idx('b_r_arm')]-p[f,idx('b_l_arm')]);side[1]=0;side=unit(side)
 # Resolve pitch sign using anatomical foot direction; no hard-coded camera forward.
 forward=unit((p[f,idx('b_l_ball')]-p[f,idx('b_l_foot')]+p[f,idx('b_r_ball')]-p[f,idx('b_r_foot')])*np.array([1,0,1]))
 sign=1 if np.dot(np.cross(side,[0,1,0]),forward)>0 else -1
 rotate(q[f],trunk,q[f,spine].copy(),side,sign*np.radians(8)*w[f])
 rotate(q[f],head,q[f,neck].copy(),side,sign*np.radians(5)*w[f])
 # Choose a fixed side rotation direction from geometry to bring the left elbow inward.
 shoulder=q[f,arm].copy();right=q[f,idx('b_r_arm')]-shoulder;right=unit(right);up=unit(q[f,neck]-q[f,0]);front=unit(np.cross(right,up));v=q[f,elbow]-shoulder;angle=np.radians(12)*w[f]
 candidates=[matrix(front,a)@v for a in [angle,-angle]];chosen=angle if np.dot(candidates[0],right)>np.dot(candidates[1],right) else -angle
 rotate(q[f],left,shoulder,front,chosen)
assert np.isfinite(q).all()
errs=[]
for j,par in enumerate(parents):
 if par<0:continue
 # Raw ball hierarchy branches from knee; this is a foot rig helper relation, not anatomical segment.
 if names[j].endswith('_ball'):continue
 errs.append(np.max(np.abs(np.linalg.norm(q[:,j]-q[:,par],axis=1)-np.linalg.norm(p[:,j]-p[:,par],axis=1))))
feet=[idx('b_'+side+'_'+part) for side in ['l','r'] for part in ['foot','ball']];assert np.max(abs(q[:,feet]-p[:,feet]))==0;assert max(errs)<3e-6
edit=dict(c);edit['name']='D-combination';edit['positions']=q.round(6).tolist();(O/'combination-trial-clips.json').write_text(json.dumps([c,edit],separators=(',',':')))
checks={'purpose':'Visible coordinated contraction candidate, no status labels or learned parameter claims.','parameters':{'pelvis':'existing D height-suppression plus two-bone leg IK, max 2.06cm','torso_forward_deg':8,'neck_forward_deg':5,'left_arm_inward_deg':12,'timing':'original; smoothstep onset 1.016 to main gesture 1.974, then maintain; no forced recovery'},'max_segment_error_m':float(max(errs)),'foot_position_error_m':0,'max_head_displacement_m':float(np.linalg.norm(q[:,idx('Head')]-p[:,idx('Head')],axis=1).max()),'limitations':['Joint center positions, no mesh collision validation.','Right-hand local gesture preserved but world trajectory changes with torso.','Head/neck geometry does not measure gaze or facial expression.','Left-arm inward rotation is geometric, not muscle relaxation.','Several factors changed together: cannot attribute impressions to one feature.','No perceptual status or naturalness validation; selected amplitudes are engineering hypotheses, not measured universal status parameters.']}
(O/'combination-trial-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
s=(O/'posture-trial.html').read_text();s=s.replace('R2 · 身体升降对照','R2 · 协调姿态组合').replace('原节奏不变，减弱身体升降','原节奏不变，试验整体收拢').replace('左侧原片，右侧逐渐减弱招呼开始后的骨盆升降。双腿重新求解，脚踝与前脚掌保持原片位置；上身相对姿态、手势顺序和播放时序保留。不是“高低status”两个版本。','左侧原片D；右侧同时降低身体、略向前倾、略低头，并让左臂更靠近身体。脚部位置与原节奏保留。先看自然度，再看整体印象；不预设右侧就是低status。')
s=s.replace('<option value="D">D：降低升高幅度</option><option value="A">A：抬高受限，仅诊断</option>','<option value="D">D 原片与组合修改</option>').replace('减弱身体升降＋双腿IK','协调收拢（候选）').replace('posture-trial-clips.json','combination-trial-clips.json').replace("c.name+'-height-suppressed'","c.name+'-combination'").replace('posture-trial-checks.json','combination-trial-checks.json')
s=re.sub(r"\$\('summary'\).textContent=`[^`]+`", "$('summary').textContent='候选改动：骨盆最多降低2.06cm，躯干前倾8°、颈部前倾5°、左臂向内12°。这些是本次实验设定，不是status公式。'",s)
s=s.replace('修改只有约1–2cm量级，不要求一定能看出差别，也不会为显眼而任意加大。','如果动作自然，再判断整体是否更拘束、放松或有其他印象；看得到姿态变化不等于地位表达有效。')
s=re.sub(r'<details><summary>修改范围与验证边界</summary>.*?</details>','<details><summary>修改范围与验证边界</summary><p>从你标记的开始到主要手势逐渐增加修改，之后保持；没有额外设计恢复姿态。脚踝和前脚掌保持原片轨迹，主要骨段长度检查通过。右手局部手势保留，但世界空间轨迹随躯干变化。尚未检查网格碰撞或感知自然度。</p><p>这是多因素组合的可行性对照。即使人物印象变化，也不能直接归因于某个单一参数，更不能据此确立status等级映射。</p><a href="combination-trial-checks.json">计算检查与限制</a></details>',s)
s=s.replace('若仍自然，再看A的拘束感、D的从容感是否变化。','').replace('scale=Math.min(w*.38,h*.39)','scale=Math.min(w*.48,h*.44)')
(O/'combination-trial.html').write_text(s);print(json.dumps(checks,ensure_ascii=False,indent=2))
