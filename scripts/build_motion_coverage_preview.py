"""Inspect finite source windows using the existing raw-motion viewer.

No cycle extraction, pose edits, retargeting, or interaction controller. Original
sample rate/root path retained; source window and provenance accompany each clip.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.bvh import load
from src.motion_coverage import positions,low_speed_intervals


def build(spec_path):
    spec=json.loads(spec_path.read_text());clips=[];reports=[]
    for entry in spec['clips']:
        path=ROOT/entry['path'];m=load(path);names=[j.name for j in m.joints]
        mode=entry['translation_mode'];world=positions(m,mode)
        hips=names.index('Hips') if 'Hips' in names else 0
        # Verify vectorized FK on this actual source, not only synthetic fixtures.
        error=max(float(np.abs(world[k]-np.array(m.positions(k,translation_mode=mode))).max())
                  for k in sorted({0,len(m.frames)//2,len(m.frames)-1}))
        assert error<1e-8
        a=round(entry['start']/m.frame_time);b=min(len(world),round(entry['end']/m.frame_time))
        if not 0<=a<b<=len(world):raise ValueError(entry)
        w=world[a:b];body=w[:,1:] if hips!=0 else w
        bounds=np.stack([body.min(axis=(0,1)),body.max(axis=(0,1))],axis=-1)
        hip_bounds=np.stack([w[:,hips].min(0),w[:,hips].max(0)],axis=-1)
        head=next((i for i,n in enumerate(names) if n=='Head'),None)
        height=float(np.median(world[:,head,1]-world[:,:,1].min(axis=1))) if head is not None else float(bounds[1,1]-bounds[1,0])
        radius=float(np.abs(w-w[:,hips:hips+1])[:,:,[0,2]].max())
        report=dict(**entry,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    original_frames=len(m.frames),original_duration=m.duration,
                    selected_start_frame=a,selected_end_exclusive=b,
                    actual_window=[a*m.frame_time,b*m.frame_time],fps=1/m.frame_time,
                    fk_reference_max_error=error,status_label=None,
                    low_speed_candidates=low_speed_intervals(world,m.frame_time,hips,height))
        reports.append(report)
        clips.append(dict(id=entry['id'],content=entry['label'],style='无status标签',
                          source=path.name,sourceUrl=spec['source_page'],sha256=report['sha256'],
                          frameTime=m.frame_time,duration=(b-a)*m.frame_time,hips=hips,
                          names=names,parents=[j.parent for j in m.joints],bounds=bounds.tolist(),
                          hipsBounds=hip_bounds.tolist(),radius=radius,poses=w.round(6).tolist(),
                          window=report['actual_window']))
    out=ROOT/'outputs/motion-coverage';out.mkdir(parents=True,exist_ok=True)
    html=(ROOT/'preview/index.html').read_text()
    html=html.replace('动作检查台 · 离线 BVH 预览','完整动作过程 · 素材检查')
    html=html.replace('<h1>动作检查台</h1>','<h1>完整动作过程 · 素材检查</h1>')
    html=html.replace('12 段身体动作 / 本地离线 / 位移读取已修正 · 2026-10-24','EMM 源素材窗口 / 未接入算法 / 无 status 标签')
    html=re.sub(r'<p class="note" style="margin:0 0 14px">.*?</p>',
                '<p class="note" style="margin:0 0 14px">这里仅检查原始素材是否包含不同身体动作及其衔接。没有自动互动、没有status生成；场景障碍和另一角色未随动作录制显示。保留所选时间窗的原始采样与根路径，不抽取循环；文件名仅作来源线索，不是已确认的动作标签。</p>',html)
    html=html.replace('id="loop" type="checkbox" checked','id="loop" type="checkbox"')
    html=html.replace('const grid=20,','const grid=height*.15,')
    html=html.replace('scale*5','scale*height*.035')
    html=html.replace('[22,0,0]','[height*.15,0,0]').replace('[0,22,0]','[0,height*.15,0]').replace('[0,0,22]','[0,0,height*.15]')
    html=html.replace("b.p!==null && b.p!==0","b.p!==null && !(b.p===0 && c.hips!==0)")
    html=html.replace(".filter(b=>b.p!==null && !(b.p===0 && c.hips!==0))", ".filter(b=>b.p!==null && !(b.p===0 && c.hips!==0) && !(c.names[b.p]==='Head' && c.names[b.j].includes('EndSite')))")
    html=html.replace("const p=project(pose[head]);ctx.strokeStyle", "const end=c.parents.findIndex((p,j)=>p===head && c.names[j].includes('EndSite'));const centerHead=end>=0?pose[head].map((v,k)=>(v+pose[end][k])/2):pose[head];const p=project(centerHead);ctx.strokeStyle")
    html=html.replace("c.names[j].includes('_L')","(c.names[j].includes('_L')||c.names[j].includes('Left'))")
    html=html.replace("c.names[j].includes('_R')","(c.names[j].includes('_R')||c.names[j].includes('Right'))")
    # Replace only the bone rendering block; motion DATA and projection are unchanged.
    start=html.index('  // Do not draw the synthetic root-to-hips link')
    end=html.index('  // View orientation indicator',start)
    html=html[:start]+"  drawCoverageAnatomy(ctx,project,c,pose,scale,height,{shapes:$('anatomyShapes').checked,labels:$('jointLabels').checked,ends:$('endMarkers').checked});\n"+html[end:]
    html=html.replace('<button id="reset">', '<label><input id="anatomyShapes" type="checkbox" checked> 手脚轮廓</label><label><input id="jointLabels" type="checkbox"> 关节名称</label><label><input id="endMarkers" type="checkbox"> 末端标记◇</label><button id="reset">')
    html=html.replace("$('follow').onchange=draw;", "$('follow').onchange=draw;for(const id of ['anatomyShapes','jointLabels','endMarkers'])$(id).onchange=draw;")
    html=html.replace('深蓝躯干 · 地面为最低采样高度','深蓝躯干 · 圆点=关节，◇=末端（可开关）· 手脚轮廓仅为显示示意')
    html=html.replace('/*__PLAYER_HELPER__*/',(ROOT/'preview/coverage-anatomy.js').read_text()+'\n/*__PLAYER_HELPER__*/')
    html=html.replace('循环接缝未处理。','默认不循环；片尾停住仅是播放器终止，不是生成的停步。')
    html=html.replace('${c.id} · ${c.content}', '${c.id} · 源时间 ${c.window[0].toFixed(2)}–${c.window[1].toFixed(2)}秒 · ${c.content}')
    html=re.sub(r'<p class="note">素材：.*?</p>',
                '<p class="note">素材：Jose Luis Ponton、Sheldon Andrews、Carlos Andujar、Nuria Pelechano · <a href="https://zenodo.org/records/17220516">Environment-aware Motion Matching</a> · <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>。本页只做BVH正向运动学与时间窗展示；不是作者算法输出或本项目生成结果。<a href="evidence.json">来源、窗口与检查记录</a></p>',html)
    html=html.replace('/*__PLAYER_HELPER__*/',(ROOT/'preview/player.js').read_text())
    html=html.replace('/*__MOTION_DATA__*/',json.dumps(dict(clips=clips),ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    (out/'index.html').write_text(html)
    (out/'evidence.json').write_text(json.dumps(dict(spec=spec,reports=reports),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{k:r[k] for k in ['id','original_duration','actual_window','fps','fk_reference_max_error']} for r in reports],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('spec',type=Path);a=parser.parse_args();build(a.spec)
