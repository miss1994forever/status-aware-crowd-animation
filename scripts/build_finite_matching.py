"""Reproducible development replay, fixed inputs before inspecting results.

Reuses the local coverage viewer, leaving its source display untouched.
No parameter sweep or status labels. Runtime is offline Python, not realtime UI.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from src.bvh import load
from src.finite_motion import FiniteSequence
from src.finite_matching import Database, Matcher


def command(t, height, changing):
    if not changing or t < 3: return np.array([0., .6*height]), 0., '向前移动'
    if t < 6: return np.zeros(2), 0., '停止移动，保持朝向'
    if t < 9: return np.array([.6*height, 0.]), 0., '向右移动，保持朝向'
    return np.array([0., .6*height]), 0., '恢复向前'


def build():
    out = ROOT/'outputs/finite-matching'; out.mkdir(parents=True, exist_ok=True)
    record = ROOT/'data/main-review/finite-matching'; record.mkdir(parents=True, exist_ok=True)
    spec = json.loads((ROOT/'data/main-review/motion-coverage/preview-plan.json').read_text())
    provenance = json.loads((ROOT/'outputs/motion-coverage/evidence.json').read_text())
    expected = {r['id']:r['sha256'] for r in provenance['reports']}
    seqs = []; sources = []
    for entry in spec['clips']:
        path = ROOT/entry['path']; sha = hashlib.sha256(path.read_bytes()).hexdigest()
        assert sha == expected[entry['id']]
        seqs.append(FiniteSequence(load(path)))
        sources.append(dict(id=entry['id'],path=entry['path'],sha256=sha))
    config = dict(duration=12.,fps=60,replan_seconds=.4,first_replan_seconds=.4,candidate_stride_frames=12,
                  initial_source='E01',initial_source_time=1.,
                  phases=['0–3s forward','3–6s stop','6–9s right with fixed facing','9–12s forward'],
                  target_speed_reference_heights_per_second=.6,weights=Matcher.weights,
                  blend_seconds=Matcher.blend_seconds,switch_penalty=Matcher.switch_penalty,
                  sources=sources,status='Development inputs, not held-out trials or tuned status parameters',
                  code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                               ['src/finite_matching.py','src/finite_motion.py','scripts/build_finite_matching.py']})
    # Save the trial settings BEFORE running, retain the full decision logs.
    (record/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    began=time.perf_counter(); db=Database(seqs); times=np.arange(721)/60
    changing=Matcher(db); constant=Matcher(db); baseline=Matcher(db)
    frames={k:[] for k in ['C0','C1','C2','C3']}; cues={k:[] for k in frames}
    for frame,t in enumerate(times):
        v,face,label=command(t,db.height,True)
        vc,fc,lc=command(t,db.height,False)
        if frame%24==0 and 0<frame<720:
            changing.choose(float(t),v,face); constant.choose(float(t),vc,fc)
        frames['C0'].append(baseline.pose(t))
        frames['C1'].append(changing.pose(t))
        frames['C2'].append(changing.pose(t,blend=False))
        frames['C3'].append(constant.pose(t))
        for key in frames:
            cues[key].append(dict(text=lc if key=='C3' else label,velocity=(vc if key=='C3' else v).tolist()))
    frames={k:np.array(v) for k,v in frames.items()}
    for p in frames.values():
        np.testing.assert_allclose(p[0],frames['C0'][0],atol=1e-12)
    # Shared camera scale/floor across variants, not independently autoscaled bodies.
    allposes=np.concatenate(list(frames.values())); bounds=np.stack([allposes.min((0,1)),allposes.max((0,1))],axis=-1)
    radius=float(np.abs(allposes-allposes[:,:1])[:,:,[0,2]].max())
    titles={'C0':'原片继续 · 不响应输入','C1':'目标响应 · 旋转混合','C2':'同选片日志 · 不混合硬切','C3':'对照 · 始终向前输入'}
    clips=[]; measurements={}
    for key,p in frames.items():
        logs=[] if key=='C0' else constant.log if key=='C3' else changing.log
        clips.append(dict(id=key,content=titles[key],style='无status',duration=12.,frameTime=1/60,
                          names=seqs[0].names,parents=seqs[0].parents,hips=0,poses=p.round(6).tolist(),
                          bounds=bounds.tolist(),hipsBounds=np.stack([p[:,0].min(0),p[:,0].max(0)],axis=-1).tolist(),
                          radius=radius,cues=cues[key],decisions=logs,window=[0.,12.]))
        jump=np.linalg.norm(np.diff(p,axis=0),axis=-1)/db.height
        vel=np.diff(p[:,0][:,[0,2]],axis=0)*60
        error=[]
        for a,b in [(0,3),(3,6),(6,9),(9,12)]:
            indices=np.arange(int((a+.6)*60),int(b*60))
            target=np.array([cues[key][i]['velocity'] for i in indices])
            error.append(float(np.sqrt(np.mean((vel[indices]-target)**2))/db.height))
        bone=max(float(np.max(np.abs(np.linalg.norm(p[:,j]-p[:,pa],axis=-1)-np.linalg.norm(seqs[0].offsets[j]))))
                 for j,pa in enumerate(seqs[0].parents) if pa is not None)
        measurements[key]=dict(switches=sum(r['switched'] for r in logs),
                               max_frame_joint_displacement_reference_heights=float(jump.max()),
                               p99_frame_joint_displacement_reference_heights=float(np.quantile(jump,.99)),
                               phase_velocity_rmse_reference_heights_per_second=error,bone_length_error=bone)
        assert np.isfinite(p).all() and bone<1e-9
    prefix=int(3*60)
    assert np.max(np.abs(frames['C1'][:prefix]-frames['C3'][:prefix]))<1e-10
    difference=float(np.sqrt(np.mean((frames['C1'][prefix:]-frames['C3'][prefix:])**2)))
    assert difference>0
    payload=dict(config=config,candidates=len(db.times),height_reference=db.height,
                 elapsed_seconds=time.perf_counter()-began,measurements=measurements,
                 identical_input_prefix_max_error=float(np.max(np.abs(frames['C1'][:prefix]-frames['C3'][:prefix]))),
                 changed_input_later_world_rms=difference,
                 limits=['No status/obstacles/other agents','Offline development replay, not realtime benchmark',
                         'Root velocity error is not naturalness; bone preservation is not contact preservation',
                         'Hard-cut replay uses identical selected segments, not an independently replanned controller'],
                 decisions={'C1':changing.log,'C3':constant.log})
    (record/'audit.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    (out/'evidence.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    html=(ROOT/'outputs/motion-coverage/index.html').read_text()
    data=json.dumps(dict(clips=clips),ensure_ascii=False,separators=(',',':'))
    html=re.sub(r'const DATA = .*?;\n',lambda _: 'const DATA = '+data+';\n',html,count=1)
    html=html.replace('完整动作过程 · 素材检查','有限动作 · 输入响应检查')
    html=html.replace('EMM 源素材窗口 / 未接入算法 / 无 status 标签','自主实现的匹配基线 / 非循环序列 / 尚无 status 或多人互动')
    html=html.replace('隐藏原始风格标签','隐藏补充标签')
    html=html.replace('标签仅是素材原始风格名，无 status 标注。隐藏标签便于初步观看，不构成盲测或感知验证。',
        '所有版本初态相同。C1与C3仅输入日程不同；C1与C2共享选片日志，仅混合开关不同。C0不响应输入。均为开发诊断，不是盲测。')
    html=re.sub(r'<p class="note" style="margin:0 0 14px">.*?</p>',
        '<p class="note" style="margin:0 0 14px">0–3秒向前 → 3–6秒停止 → 6–9秒向右（保持朝向）→ 9–12秒向前。箭头是请求速度，不是实际路径。每0.4秒比较一秒真实未来、姿态与速度，并允许原片继续；切换用0.25秒旋转混合。未加入环境避碰、status或身体接触约束。</p>',html,count=1)
    html=html.replace('selected=0, seconds=0','selected=1, seconds=0')
    html=html.replace("$('details').textContent=", "const decision=c.decisions.filter(d=>d.time<=seconds).at(-1); $('details').textContent=`请求：${c.cues[frame()].text} · ${decision?('目标源 E0'+(decision.source_id+1)+' 时间 '+(decision.source_time+seconds-decision.time).toFixed(2)+'秒'+(decision.switched&&seconds-decision.time<.25&&c.id!=='C2'?'（过渡混合中）':'')):'E01 从1秒连续播放'}\\n`+")
    html=html.replace(' · 源时间 ${c.window[0].toFixed(2)}–${c.window[1].toFixed(2)}秒',' · 回放')
    marker='  // View orientation indicator'
    arrow="""  const request=c.cues[frame()],a=[pose[0][0],floor+.015,pose[0][2]],b=[a[0]+request.velocity[0]*.8,a[1],a[2]+request.velocity[1]*.8];
  line(a,b,'#278568',3);const tip=project(b);ctx.fillStyle='#278568';ctx.beginPath();ctx.arc(tip[0],tip[1],4,0,Math.PI*2);ctx.fill();
  ctx.font='13px -apple-system,sans-serif';ctx.fillText(request.text,16,h-18);
"""
    html=html.replace(marker,arrow+marker)
    html=html.replace('默认不循环；片尾停住仅是播放器终止，不是生成的停步。','默认不循环；12秒为实验截断。停止指令发生在3–6秒，不以回放结束冒充停步。')
    html=html.replace('本页只做BVH正向运动学与时间窗展示；不是作者算法输出或本项目生成结果。','本页为本项目有限动作匹配基线的离线输出，不是EMM作者算法复现；旋转混合不保证足部接触。')
    html=html.replace('来源、窗口与检查记录','配置、指标与完整选片日志')
    (out/'index.html').write_text(html)
    print(json.dumps({k:payload[k] for k in ['candidates','elapsed_seconds','measurements']},ensure_ascii=False,indent=2))


if __name__=='__main__': build()
