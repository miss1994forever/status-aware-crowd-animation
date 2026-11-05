"""Fixed downward displacement plus left-arm adduction, C/D transfer pilot."""
from pathlib import Path
import json,re
import numpy as np
R=Path(__file__).resolve().parents[1];O=R/'outputs/social-signal-review'
clips=json.loads((O/'clips.json').read_text())[1:];events=json.loads((R/'data/research/annotations/cd-confirmed-2026-11-02.json').read_text())['events']
output=[];reports=[]
for ident in ['C','D']:
 c=next(c for c in clips if c['name']==ident);p=np.array(c['positions']);q=p.copy();names=c['names'];ts=np.arange(len(p))*c['dt'];e=events[ident];root=names.index('b_root');base=np.interp(e['onset'],ts,p[:,root,1]);u=np.clip((ts-e['onset'])/(e['gesture']-e['onset']),0,1);w=u*u*(3-2*u)
 requested=-0.02060136*w # New operator; fixed target equals prior D maximum, not retuned for C.
 legs=[];fixed=set()
 for side in ['l','r']:
  hip,knee,ankle=[names.index('b_'+side+'_'+n) for n in ['upleg','leg','foot']];ball=names.index('b_'+side+'_ball');fixed.update([knee,ankle,ball]);legs.append((hip,knee,ankle))
 actual=[];clamped=0
 for f,dy0 in enumerate(requested):
  low=-float('inf');high=float('inf')
  for hip,knee,ankle in legs:
   h,k,a=p[f,[hip,knee,ankle]];l1=np.linalg.norm(k-h);l2=np.linalg.norm(a-k);v=h-a;original_angle=np.arccos(np.clip(np.dot(k-h,a-k)/(l1*l2),-1,1));minimum_angle=min(original_angle,np.radians(5));reach=np.sqrt(l1*l1+l2*l2+2*l1*l2*np.cos(minimum_angle));vertical=np.sqrt(max(0,reach**2-v[0]**2-v[2]**2));low=max(low,-vertical-v[1]);high=min(high,vertical-v[1])
  dy=float(np.clip(dy0,low,high));actual.append(dy);clamped+=abs(dy-dy0)>1e-7
  for j in range(len(names)):
   if j not in fixed:q[f,j,1]+=dy
  for hip,knee,ankle in legs:
   h=q[f,hip];a=p[f,ankle];old=p[f,knee];l1=np.linalg.norm(p[f,knee]-p[f,hip]);l2=np.linalg.norm(p[f,ankle]-p[f,knee]);v=a-h;dist=np.linalg.norm(v);axis=v/dist
   x=(l1*l1-l2*l2+dist*dist)/(2*dist);radius=np.sqrt(max(0,l1*l1-x*x));bend=old-h-axis*np.dot(old-h,axis);norm=np.linalg.norm(bend)
   if norm<1e-8:raise ValueError('Undefined knee plane')
   q[f,knee]=h+x*axis+radius*bend/norm
 bone_error=max(float(np.max(np.abs(np.linalg.norm(q[:,a]-q[:,b],axis=1)-np.linalg.norm(p[:,a]-p[:,b],axis=1)))) for hip,knee,ankle in legs for a,b in [(hip,knee),(knee,ankle)])
 foot_error=max(float(np.max(np.abs(q[:,i]-p[:,i]))) for i in fixed if i not in [k for h,k,a in legs]);assert bone_error<1e-6 and foot_error==0 and np.isfinite(q).all()
 changed=dict(c);changed['name']=ident+'-height-suppressed';changed['positions']=q.round(6).tolist();output.extend([c,changed]);reports.append({'id':ident,'max_requested_translation_m':float(np.max(np.abs(requested))),'max_actual_translation_m':float(np.max(np.abs(actual))),'clamped_frames':int(clamped),'frames':len(p),'max_leg_length_error_before_rounding_m':bone_error,'max_foot_position_error_m':foot_error,'modified_pose_naturalness_verified':False})

# Apply the same 12-degree non-greeting arm rule to each lowered version.
def unit(v):return v/np.linalg.norm(v)
def matrix(axis,angle):
 a=unit(axis);K=np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]])
 return np.eye(3)+np.sin(angle)*K+(1-np.cos(angle))*(K@K)
for n in range(0,len(output),2):
 c=output[n];edit=output[n+1];p=np.array(c['positions']);q=np.array(edit['positions']);names=c['names'];parents=c['parents'];idx=names.index
 arm=idx('b_l_arm');elbow=idx('b_l_forearm');neck=idx('b_neck0');left=[]
 for j in range(len(names)):
  k=j
  while k>=0 and k!=arm:k=parents[k]
  if k==arm:left.append(j)
 e=events[c['name']];t=np.arange(len(q))*c['dt'];u=np.clip((t-e['onset'])/(e['gesture']-e['onset']),0,1);w=u*u*(3-2*u)
 for f in range(len(q)):
  shoulder=q[f,arm].copy();right=unit(q[f,idx('b_r_arm')]-shoulder);up=unit(q[f,neck]-q[f,0]);front=unit(np.cross(right,up));v=q[f,elbow]-shoulder;angle=np.radians(12)*w[f]
  plus=matrix(front,angle)@v;minus=matrix(front,-angle)@v;chosen=angle if np.dot(plus,right)>np.dot(minus,right) else -angle
  q[f,left]=(q[f,left]-shoulder)@matrix(front,chosen).T+shoulder
 q=q.round(6);edit['name']=c['name']+'-transfer';edit['positions']=q.tolist()
 feet=[idx('b_'+side+'_'+part) for side in ['l','r'] for part in ['foot','ball']]
 errors=[float(np.abs(np.linalg.norm(q[:,j]-q[:,par],axis=1)-np.linalg.norm(p[:,j]-p[:,par],axis=1)).max()) for j,par in enumerate(parents) if par>=0 and not names[j].endswith('_ball')]
 assert max(errors)<4e-6 and np.max(abs(q[:,feet]-p[:,feet]))==0 and np.isfinite(q).all()
 assert np.array_equal(q[t<=e['onset']],p[t<=e['onset']])
 reports[n//2].update({'max_segment_error_after_rounding_m':max(errors),'max_adjacent_joint_step_m':float(np.linalg.norm(np.diff(q,axis=0),axis=2).max()),'source_max_adjacent_joint_step_m':float(np.linalg.norm(np.diff(p,axis=0),axis=2).max()),'events':e})
(O/'transfer-trial-clips.json').write_text(json.dumps(output,separators=(',',':')))
checks={'operator':'dy=-0.02060136*smoothstep((t-onset)/(gesture-onset)); bilateral leg IK preserving source feet; left arm inward 12 degrees with same ramp. Hold after main gesture, no added recovery.', 'new_operator':True,'rows':reports,'limits':['D differs from previously rated height-suppression operator; old feedback is not validation.','Phase ramp has same normalized shape, different physical duration due to user annotations.','Same greeting task, different original take; not evidence for cross-action or crowd generalization.','No added torso/head pitch. Local right-hand motion retained, world height shifts.','No mesh/contact or perceptual naturalness validation.']}
(O/'transfer-trial-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
s=(O/'combination-trial.html').read_text()
s=s.replace('R2 · 协调姿态组合','R2 · C/D迁移试验').replace('原节奏不变，试验整体收拢','相同收缩目标，在C与D上是否都成立？')
s=s.replace('左侧原片D；右侧同时降低身体、略向前倾、略低头，并让左臂更靠近身体。脚部位置与原节奏保留。先看自然度，再看整体印象；不预设右侧就是低status。','左侧原片，右侧采用固定向下位移与左臂内收。使用你标注的各自招呼阶段加入修改，保持原节奏和脚部轨迹，不新增低头或前倾。D也已重新生成，并非上一轮版本。')
s=s.replace('<option value="D">D 原片与组合修改</option>','<option value="C">C：新片段迁移</option><option value="D">D：新算子重新检查</option>')
s=s.replace('协调收拢（候选）','固定降低＋左臂内收').replace('combination-trial-clips.json','transfer-trial-clips.json').replace("c.name+'-combination'","c.name+'-transfer'").replace('combination-trial-checks.json','transfer-trial-checks.json')
s=re.sub(r'const reports=\[.*?\];', lambda m:'const reports='+json.dumps(reports)+';',s)
s=re.sub(r"\$\('summary'\).textContent='[^']+'", "$('summary').textContent=c.name+'：最大实际降低 '+(r.max_actual_translation_m*100).toFixed(2)+'cm，左臂向内12°；开始 '+r.events.onset+'秒 → 主要手势 '+r.events.gesture+'秒。'",s)
s=s.replace('如果动作自然，再判断整体是否更拘束、放松或有其他印象；看得到姿态变化不等于地位表达有效。','先判断修改是否自然，再看更像不自在、低地位，还是没有明显区别。分别评价C和D，不需要把两个原片排序。')
s=re.sub(r'<details><summary>修改范围与验证边界</summary>.*?</details>','<details><summary>新旧方法区别与验证边界</summary><p>旧方法压住原片的起身变化；新方法在原轨迹上逐渐叠加最多2.060136cm的向下位移，并用双腿IK保持原脚位置。两者不是同一算子，所以D也重新评价。左臂规则、目标角度均不重新调节。</p><p>C：1.473 → 3.904 → 6.217秒；D：1.016 → 1.974 → 3.367秒。开始到主要手势使用相同形状的渐变，实际时长不同；之后保持，不在结束处强行恢复。</p><p>这是同一招呼任务内的迁移检查，不是非招呼、行走或群组验证。骨长与足部检查不代表动作已自然或status已有效。</p><a href="transfer-trial-checks.json">计算检查</a></details>',s)
(O/'transfer-trial.html').write_text(s)
Path('/tmp/animation-transfer-check.js').write_text(re.search(r'<script>(.*?)</script>',s,re.S).group(1))
print(json.dumps(checks,ensure_ascii=False,indent=2))
