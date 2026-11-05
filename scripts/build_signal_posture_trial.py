"""Root-height suppression with fixed original ankles and two-bone leg IK."""
from pathlib import Path
import json,re
import numpy as np
R=Path(__file__).resolve().parents[1];O=R/'outputs/social-signal-review'
clips=json.loads((O/'clips.json').read_text())[1:];events=json.loads((R/'data/research/annotations/ad-confirmed-2026-11-02.json').read_text())['events']
output=[];reports=[]
for ident in ['A','D']:
 c=next(c for c in clips if c['name']==ident);p=np.array(c['positions']);q=p.copy();names=c['names'];ts=np.arange(len(p))*c['dt'];e=events[ident];root=names.index('b_root');base=np.interp(e['onset'],ts,p[:,root,1]);u=np.clip((ts-e['onset'])/(e['gesture']-e['onset']),0,1);w=u*u*(3-2*u)
 requested=(base-p[:,root,1])*w
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
(O/'posture-trial-clips.json').write_text(json.dumps(output,separators=(',',':')))
(O/'posture-trial-checks.json').write_text(json.dumps({'method':'From user onset to main gesture, smoothstep ramps suppression of pelvis vertical change relative to onset. Full suppression then remains until source ends: no artificial recovery transition. Translate upper body including hips vertically; solve each knee in its original bend-plane direction, keeping original ankle and forefoot coordinates and per-frame original leg lengths. Clamp common height to bilateral reach, retaining at least 5 degrees of knee bend unless source knee is already straighter. No retiming.','limitations':['This changes knee flexion and height together; not independent knee or confidence control.','Upper-body world height shifts while relative upper-body pose is preserved.','Fixed source feet preserve source motion, not guaranteed zero original foot sliding.','Only a geometric IK demonstration; unvalidated naturalness/status, no mesh/contact dynamics.','Original per-frame varying bone lengths retained, rather than replaced with a canonical rig.'], 'rows':reports},ensure_ascii=False,indent=2)+'\n')
s=(O/'timing-trial.html').read_text();css=re.search(r'<style>([\s\S]*?)</style>',s).group(1);render=s[s.index('function drawOne('):s.index('function ends(')]
render=render.replace("pose(c,id==='right'?warp(t):t)","pose(c,t)")
html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>R2 · 身体升降对照</title><style>'''+css+'''</style><main><p><a href="timing-trial.html">时序对照</a> · <a href="extraction.html">证据核验</a></p><h1>原节奏不变，减弱身体升降</h1><p>左侧原片，右侧逐渐减弱招呼开始后的骨盆升降。双腿重新求解，脚踝与前脚掌保持原片位置；上身相对姿态、手势顺序和播放时序保留。不是“高低status”两个版本。</p><div class="bar"><button id="play">播放</button><button id="reset">回到开始</button><label>原片 <select id="variant"><option value="D">D：降低升高幅度</option><option value="A">A：抬高受限，仅诊断</option></select></label><label>视角 <select id="angle"><option value="0.7">斜侧</option><option value="0">角度二</option><option value="1.57">角度三</option></select></label><label>速度 <select id="speed"><option value="1">正常</option><option value="0.5">半速</option></select></label><label><input id="loop" type="checkbox">循环</label></div><div class="pair"><section class="panel"><div class="label"><strong>原片</strong></div><canvas id="left" aria-label="原片"></canvas></section><section class="panel"><div class="label"><strong>减弱身体升降＋双腿IK</strong></div><canvas id="right" aria-label="姿态修改"></canvas></section></div><div class="bar timeline"><input id="time" aria-label="播放时间" type="range" min="0" max="1" step="0.001"><output id="clock"></output></div><p id="summary"></p><p id="error" role="alert"></p><h2>先判断动作是否自然</h2><p>如果出现膝盖僵直、腿部奇怪或整体不协调，请先记录这个问题。若仍自然，再看A的拘束感、D的从容感是否变化。修改只有约1–2cm量级，不要求一定能看出差别，也不会为显眼而任意加大。</p><details><summary>修改范围与验证边界</summary><p>从你标记的开始到主要手势逐渐增加抑制，之后持续保留，不额外设计恢复动作。A受到双腿可达范围限制，不能完成同等强度修改；此版本只作可行性诊断，不作为对称的A/D结论。下肢骨长在求解精度内保持，脚踝和前脚掌位置不变。保留的是原片脚部运动，并非宣称原片完全不滑脚。骨盆升降与膝关节姿态同时改变，无法把结果仅归因于其中一项。</p><a href="posture-trial-checks.json">计算检查与限制</a></details></main><script>'''
js='''const $=id=>document.getElementById(id);let clips=[],t=0,playing=false,last=0;const reports=REPORTS;
function current(){return clips.find(c=>c.name===$('variant').value)}
function pose(c,time){let f=Math.max(0,Math.min(c.positions.length-1,time/c.dt)),a=Math.floor(f),b=Math.min(a+1,c.positions.length-1),q=f-a;return c.positions[a].map((p,j)=>p.map((v,k)=>v*(1-q)+c.positions[b][j][k]*q))}
RENDER
function setup(){if(!clips.length)return;let c=current();$('time').max=((c.positions.length-1)*c.dt).toFixed(3);let r=reports.find(r=>r.id===c.name);$('summary').textContent=`${c.name}：骨盆最大调整 ${(r.max_actual_translation_m*100).toFixed(2)}cm。自然度和人物印象尚未验收。`;draw()}
function draw(){if(!clips.length)return;let c=current(),edit=clips.find(x=>x.name===c.name+'-height-suppressed');drawOne('left',c);drawOne('right',edit);$('time').value=t;$('clock').textContent=t.toFixed(2)+'秒'}
function tick(now){if(playing&&clips.length){t+=(now-last)/1000*Number($('speed').value);let end=Number($('time').max);if(t>=end){if($('loop').checked)t%=end;else{t=end;playing=false;$('play').textContent='播放'}}draw()}last=now;requestAnimationFrame(tick)}
$('play').onclick=()=>{if(t>=Number($('time').max))t=0;playing=!playing;$('play').textContent=playing?'暂停':'播放'};$('reset').onclick=()=>{t=0;draw()};$('variant').onchange=()=>{t=0;playing=false;$('play').textContent='播放';setup()};$('angle').onchange=draw;$('time').oninput=()=>{playing=false;$('play').textContent='播放';t=Number($('time').value);draw()};window.onresize=draw;
fetch('posture-trial-clips.json').then(r=>{if(!r.ok)throw Error('动作加载失败');return r.json()}).then(d=>{clips=d;setup()}).catch(e=>$('error').textContent=e.message);requestAnimationFrame(tick);
'''.replace('REPORTS',json.dumps(reports)).replace('RENDER',render)
(O/'posture-trial.html').write_text(html+js+'</script></html>');print(json.dumps(reports,indent=2))
