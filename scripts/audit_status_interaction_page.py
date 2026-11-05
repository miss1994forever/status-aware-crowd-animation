"""Package the local-only replay page without touching the shared server."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_status_interaction_lab import library,OUT,DATA,save

def main():
    lib=library();pairs=[]
    candidates=[('开发：共享十人','dev-v3-ten-C1','dev-v3-ten-C2'),('诊断：双人相遇','dev-final-pair-C1','dev-v3-pair-C2')]
    for seed in [62003,62011,62017]:
        scene=f'shared-10-{seed}'
        candidates.append((f'评价：共享十人 · {seed}',f'eval_{scene}_C1',f'eval_{scene}_C2'))
        candidates.append((f'辅助：响应时序 · {seed}',f'eval_{scene}_C2',f'eval_{scene}_C2-yoked'))
        candidates.append((f'辅助：估计置信 · {seed}',f'eval_{scene}_C2',f'eval_{scene}_C2-no-confidence'))
    candidates.append(('空间变化：双向通道', 'eval_corridor-62023_C1','eval_corridor-62023_C2'))
    candidates.extend([('诊断：先后顺序','dev-yield-C1','dev-yield-C2'),('诊断：相反私有值','dev-role-C1','dev-role-C2'),('诊断：镜像起点','dev-mirror-C1','dev-mirror-C2'),('压力扩展：30人','stress-30-C1','stress-30-C2')])
    for title,a,b in candidates:
        paths=[OUT/'runs'/f'{key}.json' for key in [a,b]];metrics=[DATA/'metrics'/f'{key}.json' for key in [a,b]]
        if not all(p.exists() for p in paths+metrics):continue
        pairs.append(dict(title=title,files=[f'runs/{a}.json',f'runs/{b}.json'],swapped=len(pairs)%2==1,metrics=[json.loads(p.read_text()) for p in metrics]))
    save(OUT/'catalog.json',dict(pairs=pairs));save(OUT/'skeleton.json',dict(names=lib.names,parents=lib.parents,lengths=lib.lengths.tolist()))
    for name in ['index.html','ui.js']:(OUT/name).write_bytes((ROOT/'status-interaction-lab'/name).read_bytes())
    print('Packaged',len(pairs),'pairs')
if __name__=='__main__':main()
