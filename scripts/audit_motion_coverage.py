"""Compare original pilot coverage with the actual cyclic runtime library."""
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.bvh import load
from src.motion_coverage import positions,low_speed_intervals


def main():
    manifest=json.loads((ROOT/'data/pilot_manifest.json').read_text())
    payload=json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text())
    active={c['id']:c for c in payload['clips']};rows=[];height=None
    for i,e in enumerate(manifest['entries']):
        path=ROOT/e['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==e['sha256']
        m=load(path);w=positions(m,'channels_replace_offset');names=[j.name for j in m.joints]
        hips=names.index('Hips');head=names.index('Head');feet=[names.index(x) for x in ('Toes_L','Toes_R')]
        if height is None:height=float(np.median(w[:,head,1]-w[:,feet,1].min(axis=1)))
        key=f'M{i+1:02}';c=active.get(key);low=low_speed_intervals(w,m.frame_time,hips,height)
        row=dict(id=key,source=e['file'],sha256=e['sha256'],content=e['source_content'],style=e['source_style'],
                 status_label=None,source_frames=len(m.frames),source_duration=m.duration,
                 low_speed_candidates=low,runtime_cycle=None)
        if c:
            start,end=c['closure']['start'],c['closure']['end']
            row['runtime_cycle']=dict(start_frame=start,end_frame=end,period=c['period'],
                                     retained_time_fraction=(end-start)/len(m.frames))
        rows.append(row)
    usage=[]
    run_path=ROOT/'outputs/status-response-v2/runs/ten-r1-C2.json'
    if run_path.exists():
        run=json.loads(run_path.read_text())
        for i,agent in enumerate(run['frames'][0]['agents']):
            samples=[f['agents'][i] for f in run['frames'] if not f['agents'][i]['arrived']]
            usage.append(dict(id=agent['id'],initial_clip=agent['clip'],
                              sampled_prearrival_frames=len(samples),
                              source_clip_counts=dict(Counter(s['clip'] for s in samples))))
    result=dict(scope='Development coverage audit, not semantic or perceptual validation',rows=rows,
                v2_source_usage=usage,
                v2_usage_note='Source clip IDs, not final expression labels. A 0.35 upper-body reference blend remains; switching clips does not imply all own-style influence disappears.',
                pipeline_findings=[
                    'prepare() extracts one repeating cycle per accepted source, samples it into 128 phases.',
                    'Library.sample() wraps phase modulo one; it cannot represent a finite action end.',
                    'Current runtime has no separate start/stop/encounter transition clips.',
                    'Source low-speed intervals do not establish valid stop/interaction actions.',
                    'No original source file was edited; discarded means not represented in runtime cycles.'])
    dest=ROOT/'data/main-review/motion-coverage';dest.mkdir(parents=True,exist_ok=True)
    (dest/'bandai-coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for r in rows:
        print(r['id'],round(r['source_duration'],2),'cycle',r['runtime_cycle'],
              'low-speed spans',r['low_speed_candidates']['intervals'])


if __name__=='__main__':main()
