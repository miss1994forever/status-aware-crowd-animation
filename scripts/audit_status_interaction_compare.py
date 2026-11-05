"""Paired fairness and effects from saved frames; no perception scores."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_status_interaction_lab import OUT,DATA,save

def main():
    rows=[]
    for path in sorted((OUT/'runs').glob('*C1.json')):
        other=path.with_name(path.name.replace('C1.json','C2.json'))
        if not other.exists():continue
        a=json.loads(path.read_text());b=json.loads(other.read_text())
        poses=lambda r:np.array([[v['pose'] for v in f['agents']] for f in r['frames']])
        positions=lambda r:np.array([[v['pos'] for v in f['agents']] for f in r['frames']])
        diff=np.linalg.norm(poses(a)-poses(b),axis=-1);root=np.linalg.norm(positions(a)-positions(b),axis=-1)
        rows.append(dict(pair=path.stem[:-3],same_spec=a['spec']==b['spec'],same_config=a['config']==b['config'],same_initial_frame=a['frames'][0]==b['frames'][0],same_private_experiment=a['private_experiment']==b['private_experiment'],same_frame_count=len(a['frames'])==len(b['frames']),
           local_joint_difference_max=float(diff.max()),local_joint_difference_rms=float(np.sqrt(np.mean(diff**2))),root_difference_max=float(root.max()),
           limitation='Unconstrained paired differences include later route/clip divergence. Fixed social-input intervention provides causal isolation.'))
    save(DATA/'paired-audit.json',rows);print(json.dumps(rows,ensure_ascii=False))
if __name__=='__main__':main()
