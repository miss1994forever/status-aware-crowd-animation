"""Development-only response experiment. Existing frozen data is read-only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_status_interaction_lab import library, scene
from src.status_response_v2.simulation import simulate
from src.status_response_v2.control import CONFIG
from src.crowd_mobility_lab.evaluate import evaluate

OUT=ROOT/'outputs/status-response-v2'
DATA=ROOT/'data/main-review/status-response-v2'


def save(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n')


def run(key,spec,mode):
    path=OUT/'runs'/f'{key}.json'
    if path.exists():raise RuntimeError('Keep previous iterations; choose a new key: '+key)
    core=list((ROOT/'src/status_response_v2').glob('*.py'))
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in core}
    save(DATA/'plans'/f'{key}.json',dict(spec=spec,mode=mode,config=CONFIG,source_sha256=sources,
                                     scope='development, not held-out; no perception claims'))
    start=time.perf_counter();lib=library();r=simulate(lib,spec,mode)
    save(path,r);m=evaluate(r,lib);m.update(key=key,mode=mode,elapsed_seconds=time.perf_counter()-start)
    save(DATA/'metrics'/f'{key}.json',m)
    print(json.dumps({k:m.get(k) for k in ('key','arrived_fraction','max_proxy_penetration','elapsed_seconds')}),flush=True)


def compare(a,b):
    ra,rb=[json.loads((OUT/'runs'/f'{k}.json').read_text()) for k in (a,b)]
    pa,pb=[np.array([[a['pose'] for a in f['agents']] for f in r['frames']]) for r in (ra,rb)]
    root=[np.array([[a['pos'] for a in f['agents']] for f in r['frames']]) for r in (ra,rb)]
    distance=np.linalg.norm(pa-pb,axis=-1)
    moving=np.array([[a['speed']>.05 for a in f['agents']] for f in ra['frames']])
    upper=np.sqrt(np.mean(distance[:,:,1:16]**2,axis=-1))
    peak=np.unravel_index(np.argmax(upper),upper.shape)
    return dict(pair=[a,b],same_initial=ra['frames'][0]==rb['frames'][0],
                joint_max=float(distance.max()),upper_rms_active_p50=float(np.median(upper[moving])),
                upper_rms_active_p95=float(np.quantile(upper[moving],.95)),
                root_max=float(np.linalg.norm(root[0]-root[1],axis=-1).max()),
                peak_time=ra['frames'][peak[0]]['t'],peak_agent=int(peak[1]),
                note='Development effect diagnostic, not human visibility or status validation.')


def page():
    lib=library();pairs=[];audits=[]
    for prefix,title in [('pair-r2','局部相遇 · 不同自身设定'),('pair-swapped','局部相遇 · 交换自身设定'),('ten-r1','十人交汇 · 开发'),('pair-r1','归档 · 同值初版')]:
        a=prefix+'-C1';b=prefix+'-C2'
        if not (OUT/'runs'/f'{b}.json').exists():continue
        metrics=[json.loads((DATA/'metrics'/f'{k}.json').read_text()) for k in (a,b)]
        audits.append(compare(a,b))
        pairs.append(dict(title=title,files=[f'runs/{a}.json',f'runs/{b}.json'],metrics=metrics,start=0,swapped=False))
    if (OUT/'runs/pair-r1-C2-sum.json').exists():
        keys=['pair-r1-C2-sum','pair-r1-C2']
        pairs.append(dict(title='局部相遇 · 汇总与对象选择',files=[f'runs/{k}.json' for k in keys],
                          metrics=[json.loads((DATA/'metrics'/f'{k}.json').read_text()) for k in keys],start=0,swapped=False))
    if (OUT/'runs/pair-r2-C2-no-self.json').exists():
        keys=['pair-r2-C2-no-self','pair-r2-C2']
        audits.append(compare(*keys))
        pairs.append(dict(title='局部相遇 · 自身影响消融',files=[f'runs/{k}.json' for k in keys],
                          metrics=[json.loads((DATA/'metrics'/f'{k}.json').read_text()) for k in keys],start=0,swapped=False))
    save(OUT/'catalog.json',dict(pairs=pairs));save(DATA/'paired.json',audits)
    save(OUT/'skeleton.json',dict(names=lib.names,parents=lib.parents,lengths=lib.lengths.tolist()))
    # Reuse unchanged, tested viewer; isolated output uses its own catalog/data.
    html=(ROOT/'status-interaction-lab/index.html').read_text()
    html=html.replace('相遇中的身体回应','互动回应 · 对象与时序')
    html=html.replace('同步观看两段全身动作。先看人物如何应对彼此，再按需要打开技术信息。两侧共用初始任务，后续路径可能不同。',
                      '第二版开发候选：比较当前对象选择、响应时序与连续身体调整。不是已验证的 status 模型；默认正常速度，旧版保留。两侧路径可能分岔。')
    html=html.replace('../../docs/status互动原型验收.md','../../docs/任务协调.md')
    html=html.replace('完整技术报告','机制、进度与限制')
    html=html.replace('<pre id="logs">', '<p>C1：共同的几何响应；C2：再加入可见姿态估计、自身设定、当前对象选择和响应时序。C2-no-self 仅关闭自身设定对回应的影响，基础身体表达保留；C2-sum 仅替换转身方向的对象聚合，不是完全无对象选择。所有映射均为开发假设。</p><pre id="logs">')
    (OUT/'index.html').write_text(html)
    (OUT/'ui.js').write_text((ROOT/'status-interaction-lab/ui.js').read_text())
    print(json.dumps(audits,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=['pair','ten','page'],default='pair')
    parser.add_argument('--mode',default='C2');parser.add_argument('--revision',default='r1');args=parser.parse_args()
    if args.kind=='page':page()
    else:
        spec=scene(51001 if args.kind=='pair' else 13,kind='pair' if args.kind=='pair' else 'shared',duration=8 if args.kind=='pair' else 26)
        if args.kind=='pair' and args.revision in ('r2','swapped'):
            spec['private_values']=[-1,1] if args.revision=='r2' else [1,-1]
        run(f'{args.kind}-{args.revision}-{args.mode}',spec,args.mode)
