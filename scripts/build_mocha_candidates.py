from pathlib import Path
import json
import numpy as np
from pymotion.io.bvh import BVH
from pymotion.ops.skeleton import fk
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'data/stymo-pilot/mocha-candidates.json').read_text())
rows=sorted(manifest['files'],key=lambda r:('Neutral' not in r['name'],'Walk' not in r['name'],r['name']))
clips=[];checks=[]
for entry in rows:
 b=BVH();b.load(entry['path']);b.set_scale(.01)
 r,p,parents,offsets,_,_=b.get_data();world,_=fk(r,p[:,0],offsets,parents)
 assert np.isfinite(world).all()
 name=Path(entry['path']).stem;action='Walk' if 'Walk' in name else 'Run';style=name.split('_')[2]
 clips.append(dict(name=name,action=action,style=style,dt=float(b.data['frame_time']),names=list(map(str,b.data['names'])),parents=parents.tolist(),positions=world.round(5).tolist(),baseline=0 if action=='Walk' else 1))
 checks.append(dict(file=name,frames=len(p),seconds=len(p)*b.data['frame_time'],finite=True,unit_conversion=.01,paired=False))
out=ROOT/'outputs/stymo-pilot/mocha-candidates';out.mkdir(exist_ok=True)
(out/'clips.json').write_text(json.dumps(clips,separators=(',',':')));(out/'checks.json').write_text(json.dumps(checks,indent=2))
s=(ROOT/'outputs/stymo-pilot/training.html').read_text()
s=s.replace('STyMo · 原始训练动作','MOCHA · 补充原片筛选').replace('模型实际学习的两段原动作','先挑动作，再决定训练')
a=s.index('<p>左侧');z=s.index('</p>',a)+4
s=s[:a]+'<p>新取得的 AverageJoe 行走与跑步素材。左侧为同类中性动作，右侧为情绪候选；均未训练、未对齐。按各自原始时间播放，较短片段结束后保持末帧。每边各自跟随髋部，不比较位移速度。</p>'+s[z:]
s=s.replace('training-pair/clips.json','mocha-candidates/clips.json').replace("'source':'训练源 neutral'","'source':'训练源 neutral'")
s=s.replace('训练片段','候选原片').replace('训练源 neutral</strong>','同动作中性原片</strong>').replace('原始训练素材','未对齐的候选素材')
s=s.replace("clips.slice(1).forEach","clips.slice(2).forEach").replace('o.value=i+1','o.value=i+2').replace('o.textContent=labels[c.name]||c.name',"o.textContent=(c.action==='Walk'?'行走':'跑步')+' · '+({Angry:'愤怒',Happy:'快乐',Sad:'悲伤',Scared:'害怕'}[c.style]||c.style)")
s=s.replace("$('variant').value=clips.length-1","$('variant').value=2")
s=s.replace("drawOne('left',clips[0]);", "drawOne('left',clips[c.baseline]);")
s=s.replace("$('rightTitle').textContent=labels[c.name]||c.name", "$('rightTitle').textContent=(c.action==='Walk'?'行走':'跑步')+' · '+c.style")
s=s.replace('||par===0','')
s=s.replace("$('variant').onchange=draw", "$('variant').onchange=()=>{t=0;playing=false;$('play').textContent='播放';setDuration();draw()}")
s=s.replace("$('time').max=((clips[0].positions.length-1)*clips[0].dt).toFixed(3)","setDuration()")
s=s.replace('function draw(){',"function setDuration(){let c=clips[Number($('variant').value)],b=clips[c.baseline];$('time').max=Math.max((c.positions.length-1)*c.dt,(b.positions.length-1)*b.dt).toFixed(3)}\nfunction draw(){")
a=s.index('<p><a href="index.html">');z=s.index('</p>',a)+4
s=s[:a]+'<p><a href="mocha-candidates/checks.json">帧数与检查记录</a> · <a href="https://github.com/DK-Jang/MOCHA_SIGASIA2023">MOCHA 官方来源</a> · CC BY-NC 4.0。已按作者预处理约定从厘米换算成米；没有修改姿态或时间。情绪名不是 status 标签。</p>'+s[z:]
(ROOT/'outputs/stymo-pilot/candidates.html').write_text(s)
print(json.dumps(checks,indent=2))
