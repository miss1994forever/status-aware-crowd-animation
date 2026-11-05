"""Original SFU take review. Display-only constant scaling, no style/status edits."""
from pathlib import Path
import json,re,hashlib
import numpy as np
from pymotion.io.bvh import BVH
from pymotion.ops.skeleton import fk
R=Path(__file__).resolve().parents[1];O=R/'outputs/cross-action-review';O.mkdir(exist_ok=True)
source=Path('/Volumes/Samsung-SSD/AnimationLab/motion-expansion/locomotion/SFU')
files=['0008_Walking002.bvh','0008_Walking001.bvh','0018_Walking001.bvh','0018_Catwalk001.bvh']
manifest=json.loads((R/'data/research/motion-expansion/locomotion.json').read_text())['datasets'][0]
records={Path(x['path']).name:x for x in manifest['files']}
loaded=[];scales={};checks=[]
for file in files:
 b=BVH();b.load(str(source/file));r,p,parents,offsets,_,_=b.get_data();world,_=fk(r,p[:,0],offsets,parents);names=list(map(str,b.data['names']));assert np.isfinite(world).all()
 errors=[float(np.abs(np.linalg.norm(world[:,j]-world[:,par],axis=1)-np.linalg.norm(offsets[j])).max()) for j,par in enumerate(parents) if j>0 and par>=0]
 assert max(errors)<1e-4
 actor=file.split('_')[0]
 if actor not in scales:scales[actor]=1.7/float(np.quantile(world[:,:,1].max(axis=1)-world[:,:,1].min(axis=1),.95))
 scale=scales[actor];feet=[i for i,n in enumerate(names) if n.endswith('Foot') or n.endswith('ToeBase')];floor=float(np.min(world[:,feet,1]));world[:,:,1]-=floor;world*=scale
 # Preserve acquisition timing; decimate visualization only. Raw file remains complete.
 stride=4;shown=world[::stride];dt=float(b.data['frame_time'])*stride
 clip={'name':str(len(loaded)+1),'dt':dt,'names':names,'parents':parents.tolist(),'positions':shown.round(6).tolist(),'source_file':file,'actor':actor,'source_frames':len(world),'source_dt':float(b.data['frame_time']),'source_description':records[file].get('description',''),'display_scale':scale}
 loaded.append(clip);checks.append({'source':str(source/file),'sha256':hashlib.sha256((source/file).read_bytes()).hexdigest(),'frames':len(world),'display_frames':len(shown),'max_fk_bone_length_error_source_units':max(errors),'display_scale':scale,'floor_translation_source_units':floor,'time_preserved':True,'no_expression_edit':True})
(O/'clips.json').write_text(json.dumps(loaded,separators=(',',':')))
(O/'checks.json').write_text(json.dumps({'method':'Native BVH local rotations with FK; no retargeting or expression edits. Every fourth frame shown at original elapsed time. One constant display scale per actor shared across their two takes; one constant floor shift per take. Native physical units not yet certified; do not compare meters/second from this viewer.','checks':checks,'limits':['Separate takes, not aligned matched events or paired interactions.','Source labels do not define status.','Floor shift does not remove native foot sliding.','Last preview sample can precede final source frame by up to 3 native frames.']},ensure_ascii=False,indent=2)+'\n')
s=(R/'outputs/social-signal-review/combination-trial.html').read_text()
s=s.replace('R2 · 协调姿态组合','R1/R2 · 非招呼原片筛选').replace('原节奏不变，试验整体收拢','先看行走中的人物表达')
s=s.replace('左侧原片D；右侧同时降低身体、略向前倾、略低头，并让左臂更靠近身体。脚部位置与原节奏保留。先看自然度，再看整体印象；不预设右侧就是低status。','两侧是同一原片、同一时刻的两个相差90°的视角，并非修改前后。①②来自同一演员；③④来自另一演员。均未加入我们的收缩、时序或status控制。')
s=s.replace('<option value="D">D 原片与组合修改</option>',''.join(f'<option value="{i}">原片 {i} · 演员 {loaded[i-1]["actor"]}</option>' for i in range(1,5)))
s=s.replace('<strong>原片</strong>','<strong>原片 · 视角一</strong>').replace('协调收拢（候选）','同一原片 · 视角二').replace('aria-label="姿态修改"','aria-label="同一原片第二视角"')
s=s.replace('combination-trial-clips.json','clips.json').replace('combination-trial-checks.json','checks.json')
s=s.replace("let c=current(),edit=clips.find(x=>x.name===c.name+'-combination');drawOne('left',c);drawOne('right',edit);","let c=current();drawOne('left',c);drawOne('right',c);")
s=s.replace("yaw=Number($('angle').value)","yaw=Number($('angle').value)+(id==='right'?Math.PI/2:0)")
s=re.sub(r'const reports=\[.*?\];','',s)
s=s.replace("let r=reports.find(r=>r.id===c.name);",'')
s=re.sub(r"\$\('summary'\).textContent='[^']+'","$('summary').textContent='原片 '+c.name+' · '+c.source_file+' · '+((c.source_frames-1)*c.source_dt).toFixed(2)+'秒。两视角同步；镜头随人物平移，保留原朝向。'",s)
s=s.replace('先判断动作是否自然','先分清动作任务与人物印象').replace('如果出现膝盖僵直、腿部奇怪或整体不协调，请先记录这个问题。如果动作自然，再判断整体是否更拘束、放松或有其他印象；看得到姿态变化不等于地位表达有效。','先看①②：是否自然，人物印象有什么区别？如果有地位感，来自身体哪里，还是更像情绪、性格或表演姿态？③④是补充，先不用给四段强行排序。这里没有真正的互动伙伴。')
s=re.sub(r'<details><summary>修改范围与验证边界</summary>.*?</details>','<details><summary>来源与显示边界</summary><p>SFU官方原始BVH。①普通绕圈行走，②swagger行走及姿态，③步幅变化行走，④catwalk走姿（含摆臂/叉腰）。这些是作者动作描述，不是地位标签。两组演员不同，不据此比较人的原始身高。</p><p>为便于显示，同一演员两段采用同一常数缩放；每段只做常数地面平移，未逐帧锁脚。物理单位尚未独立确认，本页不提供米/秒指标。保留原始朝向与时间，预览抽帧至约30fps，完整源文件仍在SSD。</p><p>仅研究用途，不可直接用于商业产品；尚未验证自然度或status表达。</p><a href="checks.json">源文件与FK检查</a> · <a href="https://mocap.cs.sfu.ca/">官方来源与许可</a></details>',s)
s=s.replace('href="timing-trial.html"','href="../motion-expansion/index.html"').replace('时序对照</a>','数据获取清单</a>').replace('href="extraction.html"','href="../../progress/index.html#research-route"').replace('证据核验</a>','研究路线</a>')
s=s.replace('<label><input id="loop" type="checkbox">循环</label>', '<label><input id="loop" type="checkbox">循环</label><label><input id="helpers" type="checkbox" checked>显示手部末端参考线（虚线）</label>')
s=s.replace("let color=/left|_l/.test(n)?'#176eaf':/right|_r/.test(n)?'#bf593b':'#19334e';line(p[par],p[j],color,3.5);", "let helper=/wrist_end/.test(n);if(helper&&!$('helpers').checked)return;let color=/left|^l_|_l/.test(n)?'#176eaf':/right|^r_|_r/.test(n)?'#bf593b':'#19334e';ctx.setLineDash(helper?[4,4]:[]);line(p[par],p[j],color,helper?2:3.5);ctx.setLineDash([]);")
s=s.replace("window.onresize=draw;", "$('helpers').onchange=draw;window.onresize=draw;")
s=s.replace('这里没有真正的互动伙伴。', '这里没有真正的互动伙伴。虚线是BVH手部末端参考线，不是完整手掌/手指；演员0008的右侧参考线持续偏斜，暂不将其作为人物表达证据。')
(O/'index.html').write_text(s)
Path('/tmp/cross-action-check.js').write_text(re.search(r'<script>(.*?)</script>',s,re.S).group(1))
print(json.dumps(checks,indent=2))
