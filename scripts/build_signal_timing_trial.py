"""Build isolated smooth time remapping: no pose offsets or joint edits."""
from pathlib import Path
import json,re
R=Path(__file__).resolve().parents[1];O=R/'outputs/social-signal-review'
a=json.loads((R/'data/research/annotations/ad-confirmed-2026-11-02.json').read_text())['events']
s=(O/'index.html').read_text();css=re.search(r'<style>([\s\S]*?)</style>',s).group(1)
render=s[s.index('function drawOne('):s.index('function setDuration(')]
render=render.replace('p=pose(c),s=pose(clips[0]),origin=p[0]','p=pose(c,id===\'right\'?warp(t):t),origin=p[0]').replace("+(id==='right'?Math.PI/2:0)",'')
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R2 · 时序隔离对照</title><style>'''+css+'''</style><main><p><a href="extraction.html">返回证据核验</a></p><h1>同一套姿态，只改变招呼节奏</h1><p>左侧原片，右侧交换A/D两个招呼阶段的时长。没有添加姿态、改变关节或混入另一个人物的动作。两边按真实秒数同步开始；动作进度不同是本次改动。先看自然度，再判断犹豫、从容或地位印象。</p><div class="bar"><button id="play">播放</button><button id="reset">回到开始</button><label>原片 <select id="variant"><option value="A">A：缩短招呼</option><option value="D">D：延长招呼</option></select></label><label>视角 <select id="angle"><option value="0.7">斜侧</option><option value="0">角度二</option><option value="1.57">角度三</option></select></label><label>速度 <select id="speed"><option value="1">正常</option><option value="0.5">半速</option></select></label><label><input id="loop" type="checkbox">循环</label></div><div class="pair"><section class="panel"><div class="label"><strong>原片</strong><span id="originalClock"></span></div><canvas id="left" aria-label="原片动作"></canvas></section><section class="panel"><div class="label"><strong>仅改变时间</strong><span id="editedClock"></span></div><canvas id="right" aria-label="时序修改动作"></canvas></section></div><div class="bar timeline"><input id="time" aria-label="播放时间" type="range" min="0" max="1" step="0.001" value="0"><output id="clock"></output></div><p id="summary"></p><p id="error" role="alert"></p><h2>怎样判断这次改动</h2><p>先观察右侧是否仍自然。如果A变快后仍拘束，或D变慢后仍从容，时长就不足以单独解释原有差异。如果右侧变得机械，则先记录为时间修改造成的自然度问题，不能把不自然当成低status。</p><details><summary>具体改了什么与实验边界</summary><p>采用你的开始、主要手势、结束标注；A的两个阶段从1.492/2.017秒变为0.958/1.393秒，D反向调整。起始时间保持原片不变，结束后的动作仍完整播放，只在时间线上提前或延后。较短一侧播完后会停在末帧，标题会明确提示。</p><p>每个阶段采用平滑、单调的时间映射，边界播放速度回到原速，不倒放、不跳姿态。修改作用于全身，包括躯干、手指与根节点，因此不能声称只改变招呼手速度；姿态次序保持，速度和加速度会变化。尚未验证自然度、status效果或跨动作泛化。</p><a href="timing-trial-checks.json">计算与边界检查</a></details></main><script>'''
js='''const $=id=>document.getElementById(id);const events=EVENTS;let clips=[],t=0,playing=false,last=0;
function config(){let id=$('variant').value,e=events[id],other=events[id==='A'?'D':'A'];return {id,e,d1:other.gesture-other.onset,d2:other.offset-other.gesture}}
function warp(time){let {e,d1,d2}=config();if(time<=e.onset)return time;let targetEnd=e.onset+d1+d2;if(time>=targetEnd)return time+e.offset-targetEnd;let first=time<e.onset+d1,ts=first?e.onset:e.onset+d1,td=first?d1:d2,ss=first?e.onset:e.gesture,sd=first?e.gesture-e.onset:e.offset-e.gesture;let u=(time-ts)/td;return ss+(time-ts)+(sd-td)*(3*u*u-2*u*u*u)}
function current(){return clips.find(c=>c.name===$('variant').value)}
function pose(c,time){let f=Math.max(0,Math.min(c.positions.length-1,time/c.dt)),a=Math.floor(f),b=Math.min(a+1,c.positions.length-1),q=f-a;return c.positions[a].map((p,j)=>p.map((v,k)=>v*(1-q)+c.positions[b][j][k]*q))}
RENDER
function ends(){let c=current(),{e,d1,d2}=config(),original=(c.positions.length-1)*c.dt;return {original,edited:original-(e.offset-e.onset)+d1+d2}}
function setup(){if(!clips.length)return;let en=ends(),{id,e,d1,d2}=config();$('time').max=Math.max(en.original,en.edited).toFixed(3);$('summary').textContent=`${id}：招呼 ${(e.offset-e.onset).toFixed(3)}秒 → ${(d1+d2).toFixed(3)}秒。开始 ${e.onset.toFixed(3)}秒保持不变。`;draw()}
function draw(){if(!clips.length)return;let c=current(),en=ends();drawOne('left',c);drawOne('right',c);$('time').value=t;$('clock').textContent=t.toFixed(2)+'秒';$('originalClock').textContent=t>=en.original?'已播完 · 保持末帧':t.toFixed(2)+'秒';$('editedClock').textContent=t>=en.edited?'已播完 · 保持末帧':'对应原片 '+warp(t).toFixed(2)+'秒'}
function tick(now){if(playing&&clips.length){t+=(now-last)/1000*Number($('speed').value);let end=Number($('time').max);if(t>=end){if($('loop').checked)t%=end;else{t=end;playing=false;$('play').textContent='播放'}}draw()}last=now;requestAnimationFrame(tick)}
$('play').onclick=()=>{if(t>=Number($('time').max))t=0;playing=!playing;$('play').textContent=playing?'暂停':'播放'};$('reset').onclick=()=>{t=0;draw()};$('variant').onchange=()=>{t=0;playing=false;$('play').textContent='播放';setup()};$('angle').onchange=draw;$('time').oninput=()=>{playing=false;$('play').textContent='播放';t=Number($('time').value);draw()};window.onresize=draw;
fetch('clips.json').then(r=>{if(!r.ok)throw Error('动作数据加载失败');return r.json()}).then(d=>{clips=d.slice(1);setup()}).catch(e=>$('error').textContent=e.message);requestAnimationFrame(tick);
'''.replace('EVENTS',json.dumps(a,ensure_ascii=False)).replace('RENDER',render)
(O/'timing-trial.html').write_text(html+js+'</script></html>')
checks=[]
for id in ['A','D']:
 e=a[id];other=a['D' if id=='A' else 'A'];ph=[]
 for k,l in [('onset','gesture'),('gesture','offset')]:
  sd=e[l]-e[k];td=other[l]-other[k];minimum=min(1,1+1.5*(sd/td-1));assert minimum>0
  ph.append({'source_duration_s':sd,'edited_duration_s':td,'min_source_time_rate':minimum,'endpoint_rate':1,'source_endpoint_error':abs(td+(sd-td)-sd)})
 checks.append({'clip':id,'phases':ph})
(O/'timing-trial-checks.json').write_text(json.dumps({'method':'Within phase source_time=source_start+target_elapsed+(source_duration-target_duration)*smoothstep(target_elapsed/target_duration). C1 temporal mapping, not C2; full body resampled from original same ordered poses.','checks':checks,'not_tested':['Perceived naturalness','Status expression','Contact velocity quality','Cross-action generalization']},indent=2)+'\n')
print('Built timing trial; both mappings strictly monotone, boundary rate 1')
