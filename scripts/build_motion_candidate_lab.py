"""Rebuild only candidate-lab artifacts. Original BVH and shared outputs are read-only."""
import hashlib
import csv
import json
from pathlib import Path
import sys
import time
import platform
import numpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.bvh import load
from src.motion_candidate_lab.cycles import audit, serialize


def build():
    began=time.perf_counter()
    manifest=json.loads((ROOT/'data/pilot_manifest.json').read_text())
    dest=ROOT/'outputs/motion-candidate-lab';dest.mkdir(parents=True,exist_ok=True)
    evidence_dir=ROOT/'data/motion-candidate-lab';evidence_dir.mkdir(parents=True,exist_ok=True)
    entries=[];clips=[];reference_height=None
    for i,source in enumerate(manifest['entries']):
        path=ROOT/source['file'];digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=source['sha256']:raise ValueError(f'Hash mismatch: {path}')
        motion=load(path);info,methods,cycles=audit(motion,reference_height)
        if reference_height is None:reference_height=info['height']
        key=f'M{i+1:02}'
        result=dict(id=key,source=source,hash_verified=True,measurements=info['metadata'],methods=methods,
                    content_from_source_label=source['source_content'],
                    gaps_inferred=['未包含经验证的起步/收脚停止/转弯/方向切换过渡',
                                   '侧移和倒走不能据此当作朝向行走或连续转弯素材'],
                    decision='可供循环工程试用' if methods['improved']['accepted'] else '保留原始片段；改进循环拒绝')
        entries.append(result)
        # Source samples are unedited FK in one fixed coordinate transform; original rate and root travel retained.
        clips.append(dict(id=key,names=info['names'],parents=info['parents'],raw=info['local'].round(9).tolist(),
                          dt=motion.frame_time,methods={name:serialize(c) for name,c in cycles.items()},review=result))
        print(key,source['source_content'],{k:(v['accepted'],v.get('evidence',{}).get('period_frames'),v.get('evidence',{}).get('max_output_change')) for k,v in methods.items()},flush=True)
    report=dict(schema=1,creator=manifest['creator'],repository=manifest['repository'],revision=manifest['revision'],license=manifest['license'],
                translation_mode='channels_replace_offset',units='one fixed M01 source reference height for ALL clips, not metres',
                status_inference=False,ik=False,entries=entries,build_seconds=time.perf_counter()-began,
                engineering_gates={'max_output_change':.05,'raw_seam_position_rms':.025,'recurrence_correlation':.65,'seam_velocity_epsilon_rms':.015},
                search={'lag_seconds':[.65,2.8],'max_lag':'half observed span','peak_selection':'shortest local peak within 0.05 of strongest and correlation >=0.65','local_period_range':'selected foot recurrence peak ±15%','end_margin_frames':8,'closure_fallback':'first passing candidate among top 8 by seam score; keep first rejection if all fail'},
                implementation='Autonomous FK adapter + labelled-foot recurrence + pose/velocity/context endpoint search + cubic C1 closure + inherited fixed-bone reconstruction. No external algorithm code or new data.')
    report['environment']={'python':platform.python_version(),'numpy':numpy.__version__,'system':platform.platform(),'machine':platform.machine()}
    report['code_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['src/bvh.py','src/locomotion.py','src/locomotion_encounter.js','src/motion_candidate_lab/cycles.py','src/motion_candidate_lab/runtime.js','scripts/build_motion_candidate_lab.py','motion-candidate-lab/ui.js','motion-candidate-lab/index.html']}
    (evidence_dir/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    with (evidence_dir/'candidates.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['id','source_content','source_style','sha256','source_url','sample_span_seconds','travel_relative_facing_degrees','period_frames','native_speed','max_output_change','accepted','reason'])
        for e in entries:
            s=e['source'];m=e['measurements'];v=e['methods']['improved'];x=v.get('evidence',{})
            writer.writerow([e['id'],s['source_content'],s['source_style'],s['sha256'],s['source_url'],m['sample_span_seconds'],m['travel_relative_facing_degrees'],x.get('period_frames'),x.get('native_speed'),x.get('max_output_change'),v['accepted'],';'.join(v['reasons'])])
    payload=dict(report=report,clips=clips)
    (dest/'lab.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n')
    (dest/'LICENSE.txt').write_bytes((ROOT/'data/raw/bandai-pilot/LICENSE').read_bytes())
    template=ROOT/'motion-candidate-lab/index.html'
    if template.exists():
        html=template.read_text().replace('/*__DATA__*/',json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
        for marker,path in [('/*__CYCLE__*/','locomotion/runtime.js'),('/*__ENCOUNTER__*/','src/locomotion_encounter.js'),('/*__LAB__*/','src/motion_candidate_lab/runtime.js'),('/*__UI__*/','motion-candidate-lab/ui.js')]:
            html=html.replace(marker,(ROOT/path).read_text())
        (dest/'index.html').write_text(html)
    return payload


if __name__=='__main__':build()
