"""Remove added torso/neck pitch; preserve height intervention and arm angle.
Grouped ablation, not an independent test of head versus torso effects.
"""
from pathlib import Path
import json
import numpy as np
R=Path(__file__).resolve().parents[1]; O=R/'outputs/social-signal-review'
original,full=json.loads((O/'combination-trial-clips.json').read_text())
base=next(c for c in json.loads((O/'posture-trial-clips.json').read_text()) if c['name']=='D-height-suppressed')
p=np.array(original['positions']); q=np.array(base['positions']); names=original['names']; parents=original['parents']; idx=names.index
arm=idx('b_l_arm'); elbow=idx('b_l_forearm'); neck=idx('b_neck0')
left=[]
for j in range(len(names)):
 k=j
 while k>=0 and k!=arm:k=parents[k]
 if k==arm:left.append(j)
def unit(v):return v/np.linalg.norm(v)
def matrix(axis,angle):
 a=unit(axis); K=np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]])
 return np.eye(3)+np.sin(angle)*K+(1-np.cos(angle))*(K@K)
events=json.loads((R/'data/research/annotations/ad-confirmed-2026-11-02.json').read_text())['events']['D']
t=np.arange(len(q))*original['dt']; u=np.clip((t-events['onset'])/(events['gesture']-events['onset']),0,1); weight=u*u*(3-2*u)
for f in range(len(q)):
 shoulder=q[f,arm].copy(); right=unit(q[f,idx('b_r_arm')]-shoulder); up=unit(q[f,neck]-q[f,0]); front=unit(np.cross(right,up)); v=q[f,elbow]-shoulder; angle=np.radians(12)*weight[f]
 candidates=[matrix(front,a)@v for a in [angle,-angle]]
 chosen=angle if np.dot(candidates[0],right)>np.dot(candidates[1],right) else -angle
 q[f,left]=(q[f,left]-shoulder)@matrix(front,chosen).T+shoulder
q=q.round(6); assert np.isfinite(q).all()
feet=[idx('b_'+s+'_'+part) for s in ['l','r'] for part in ['foot','ball']]
errors=[np.abs(np.linalg.norm(q[:,j]-q[:,par],axis=1)-np.linalg.norm(p[:,j]-p[:,par],axis=1)).max() for j,par in enumerate(parents) if par>=0 and not names[j].endswith('_ball')]
assert max(errors)<3e-6; assert np.max(abs(q[:,feet]-p[:,feet]))==0
# All non-left-arm joints must match the height-only condition exactly.
unmodified=[j for j in range(len(names)) if j not in left]
assert np.array_equal(q[:,unmodified],np.array(base['positions'])[:,unmodified])
edit=dict(original,name='D-no-pitch',positions=q.tolist())
(O/'ablation-trial-clips.json').write_text(json.dumps([original,full,edit],separators=(',',':')))
checks={'removed':{'added_torso_pitch_deg':8,'added_neck_pitch_deg':5},'retained':'Original timing; same height-suppression/leg IK and same 12-degree left-arm inward rule and onset ramp. Arm axis follows unpitched torso; world arm trajectories are therefore not identical.', 'max_segment_error_m':float(max(errors)), 'foot_error_m':0,'non_left_arm_matches_height_only':True,'max_adjacent_joint_step_m':float(np.linalg.norm(np.diff(q,axis=0),axis=2).max()),'limitations':['Head and torso removed together; cannot distinguish their effects.','No mesh collision or perceptual naturalness validation.','No status labels assigned to edited clips.']}
(O/'ablation-trial-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
s=(O/'combination-trial.html').read_text()
s=s.replace('R2 · 协调姿态组合','R2 · 前倾消融').replace('原节奏不变，试验整体收拢','去掉新增前倾，人物印象还会改变吗？')
s=s.replace('左侧原片D；右侧同时降低身体、略向前倾、略低头，并让左臂更靠近身体。脚部位置与原节奏保留。先看自然度，再看整体印象；不预设右侧就是低status。','三版使用同一时刻、视角和原片节奏。先对比中间与右侧，再用原片作参照。右侧仅撤去新增的躯干前倾与低头；保留身体降低、腿部IK和左臂内收规则。')
s=s.replace('grid-template-columns:1fr 1fr;','grid-template-columns:repeat(3,1fr);').replace('max-width:1400px','max-width:1800px')
s=s.replace('D 原片与组合修改','D 三版同步对照').replace('协调收拢（候选）','上一版：完整组合')
s=s.replace('</canvas></section></div><div class="bar timeline">','</canvas></section><section class="panel"><div class="label"><strong>本版：撤去新增前倾</strong></div><canvas id="third" aria-label="撤去头与躯干前倾"></canvas></section></div><div class="bar timeline">')
s=s.replace('combination-trial-clips.json','ablation-trial-clips.json').replace('combination-trial-checks.json','ablation-trial-checks.json')
s=s.replace("drawOne('right',edit);","drawOne('right',edit);drawOne('third',clips.find(x=>x.name==='D-no-pitch'));")
s=s.replace('候选改动：骨盆最多降低2.06cm，躯干前倾8°、颈部前倾5°、左臂向内12°。这些是本次实验设定，不是status公式。','右侧保留：骨盆最多降低2.06cm＋双腿IK、左臂向内12°；移除：躯干前倾8°、颈部前倾5°。原片自身的姿态变化仍保留。')
s=s.replace('先判断动作是否自然','这次只看两个问题').replace('如果出现膝盖僵直、腿部奇怪或整体不协调，请先记录这个问题。如果动作自然，再判断整体是否更拘束、放松或有其他印象；看得到姿态变化不等于地位表达有效。','与中间相比，右侧“精神不好、邋遢”的感觉是否减弱？与左侧原片相比，右侧的地位感是否仍有降低？若差别不明显或动作不自然，也直接记录；不要求选出高低排序。')
s=s.replace('右手局部手势保留，但世界空间轨迹随躯干变化。','右手局部手势保留；撤去前倾后，手的世界轨迹也会相应改变。左臂内收角度和计算规则相同，旋转轴跟随躯干，世界轨迹不完全相同。')
s=s.replace('这是多因素组合的可行性对照。即使人物印象变化，也不能直接归因于某个单一参数，更不能据此确立status等级映射。','这是将头部与躯干新增前倾一起撤去的分组消融，不能区分低头和躯干各自的作用，也不能将疲惫或仪态直接等同于地位。')
(O/'ablation-trial.html').write_text(s)
print(json.dumps(checks,ensure_ascii=False,indent=2))
