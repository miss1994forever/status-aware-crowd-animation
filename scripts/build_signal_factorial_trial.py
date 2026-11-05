"""Fixed-amplitude 2x2 diagnostic: height suppression x left-arm adduction."""
from pathlib import Path
import json,re
import numpy as np
R=Path(__file__).resolve().parents[1]; O=R/'outputs/social-signal-review'
a,_,combined=json.loads((O/'ablation-trial-clips.json').read_text())
height=next(c for c in json.loads((O/'posture-trial-clips.json').read_text()) if c['name']=='D-height-suppressed')
p=np.array(a['positions']); h=np.array(height['positions']); both=np.array(combined['positions']); names=a['names']; parents=a['parents']
# Height intervention translates all upper-body joints equally. Thus the stored
# arm displacement relative to that condition also applies to original upper body.
arm=names.index('b_l_arm'); subtree=[]
for j in range(len(names)):
 k=j
 while k>=0 and k!=arm:k=parents[k]
 if k==arm:subtree.append(j)
upper=[names.index(n) for n in ['b_l_arm','b_r_arm','b_neck0','b_root']]
assert np.max(np.abs((h-p)[:,upper]-(h-p)[:,upper[:1]]))<2e-6
q=p.copy();q[:,subtree]+=(both-h)[:,subtree];q=q.round(6)
others=[j for j in range(len(names)) if j not in subtree]
assert np.array_equal(q[:,others],p[:,others])
clips=[a,dict(height,name='D-height'),dict(a,name='D-arm',positions=q.tolist()),dict(combined,name='D-both')]
reports=[]
feet=[names.index('b_'+side+'_'+part) for side in ['l','r'] for part in ['foot','ball']]
for c in clips:
 v=np.array(c['positions']);assert v.shape==p.shape and c['dt']==a['dt'] and np.isfinite(v).all()
 err=max(float(np.abs(np.linalg.norm(v[:,j]-v[:,par],axis=1)-np.linalg.norm(p[:,j]-p[:,par],axis=1)).max()) for j,par in enumerate(parents) if par>=0 and not names[j].endswith('_ball'))
 foot=float(np.abs(v[:,feet]-p[:,feet]).max());assert err<4e-6 and foot==0
 reports.append({'condition':c['name'],'segment_error_m':err,'foot_error_m':foot})
(O/'factorial-trial-clips.json').write_text(json.dumps(clips,separators=(',',':')))
(O/'factorial-trial-checks.json').write_text(json.dumps({'design':'2x2 fixed height suppression and arm adduction, no added pitch or retiming','checks':reports,'arm_only_other_joints_exact':True,'limits':['Single performance and unblinded formative review, no general status mapping.','Height factor includes leg IK and knee changes, not height alone.','Combination effects require repeated ratings to estimate; visual impression alone does not establish statistical interaction.','Joint positions only; mesh contact and perceptual naturalness unverified.']},ensure_ascii=False,indent=2)+'\n')
s=(O/'ablation-trial.html').read_text()
s=s.replace('R2 · 前倾消融','R2 · 高度与左臂拆分').replace('去掉新增前倾，人物印象还会改变吗？','身体降低、左臂内收，分别改变了什么？')
s=s.replace('三版使用同一时刻、视角和原片节奏。先对比中间与右侧，再用原片作参照。右侧仅撤去新增的躯干前倾与低头；保留身体降低、腿部IK和左臂内收规则。','四版使用同一原片、时刻、视角与节奏，均无新增低头或前倾。可先看四版，也可选择两版放大比较；幅度与上一轮完全相同。')
s=s.replace('grid-template-columns:repeat(3,1fr)','grid-template-columns:repeat(2,1fr)').replace('height:470px','height:340px').replace('max-width:1800px','max-width:1400px')
s=s.replace('<label>原片 <select id="variant"><option value="D">D 三版同步对照</option></select></label>','<select id="variant" hidden><option value="D">D</option></select><label>对照 <select id="comparison"><option value="all">四版总览</option><option value="left,third">原片 / 仅左臂</option><option value="left,right">原片 / 仅降低身体</option><option value="third,fourth">仅左臂 / 两者结合</option><option value="right,fourth">仅降低身体 / 两者结合</option></select></label>')
s=s.replace('上一版：完整组合','仅降低身体＋双腿IK').replace('本版：撤去新增前倾','仅左臂内收')
s=s.replace('</canvas></section></div><div class="bar timeline">','</canvas></section><section class="panel"><div class="label"><strong>两者结合（上一轮右侧）</strong></div><canvas id="fourth" aria-label="降低身体与左臂内收"></canvas></section></div><div class="bar timeline">')
s=s.replace('ablation-trial-clips.json','factorial-trial-clips.json').replace('ablation-trial-checks.json','factorial-trial-checks.json')
s=s.replace("let el=$(id),rect=", "let el=$(id);if(el.closest('.panel').hidden)return;let rect=")
s=s.replace("let c=current(),edit=clips.find(x=>x.name===c.name+'-combination');drawOne('left',c);drawOne('right',edit);drawOne('third',clips.find(x=>x.name==='D-no-pitch'));", "drawOne('left',clips[0]);drawOne('right',clips[1]);drawOne('third',clips[2]);drawOne('fourth',clips[3]);")
s=s.replace('右侧保留：骨盆最多降低2.06cm＋双腿IK、左臂向内12°；移除：躯干前倾8°、颈部前倾5°。原片自身的姿态变化仍保留。','固定幅度：身体最多降低2.06cm；左臂向内12°。修改从招呼开始到主要手势逐渐加入，之后保持。原片本身的动作仍保留。')
s=s.replace('这次只看两个问题','先看自然度，再看人物印象')
s=s.replace('与中间相比，右侧“精神不好、邋遢”的感觉是否减弱？与左侧原片相比，右侧的地位感是否仍有降低？若差别不明显或动作不自然，也直接记录；不要求选出高低排序。','哪种修改单独就能改变人物印象？“两者结合”是否比单独修改更明显？请区分地位感、拘束感和精神状态；差不多也可以，不必强行排序。')
s=re.sub(r'<details><summary>修改范围与验证边界</summary>.*?</details>','<details><summary>修改范围与验证边界</summary><p>“降低身体”包含保持足部轨迹的双腿IK，因此同时改变膝部姿态，并非只改绝对高度。“左臂”是非招呼侧；招呼右手保留原局部动作。只有左臂版的其余关节与原片完全相同。两者结合版复用上一轮右侧数据。</p><p>本轮是单个表演的非盲探索，不是正式用户实验；即使组合更明显，也不能直接证明统计上的协同效应。骨长和足部检查不能代替自然度评价。</p><a href="factorial-trial-checks.json">计算检查</a></details>',s)
s=s.replace("window.onresize=draw;", "$('comparison').onchange=()=>{let v=$('comparison').value;document.querySelectorAll('.panel').forEach(p=>{p.hidden=v!=='all'&&!v.split(',').includes(p.querySelector('canvas').id)});draw()};window.onresize=draw;")
s=s.replace('aria-label="姿态修改"','aria-label="仅降低身体"').replace('aria-label="撤去头与躯干前倾"','aria-label="仅左臂内收"')
(O/'factorial-trial.html').write_text(s)
Path('/tmp/animation-factorial-check.js').write_text(re.search(r'<script>(.*?)</script>',s,re.S).group(1))
print(json.dumps(reports,indent=2))
