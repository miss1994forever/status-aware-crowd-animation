"""Dense kinematic constraints, movement decomposition and source provenance."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.expression_space_lab.model import quality,phase_map
from src.locomotion import Cycle

def segment_distance(p,a,b):
 d=b-a;return np.linalg.norm(p-(a+np.clip(np.dot(p-a,d)/max(np.dot(d,d),1e-12),0,1)*d))
def audit():
 data=json.loads((ROOT/'outputs/expression-space-lab/experiment.json').read_text());rows=[]
 for c in data['clips']:
  z=c['cycle'];cy=Cycle(z['poses'],z['tangents'],z['stride'],z['evidence'],z['parents'],z['bone_lengths']);names=c['names'];T=c['duration'];lens=np.array(c['lengths']);parents=c['parents']
  for s in [0,.5,1]:
   u=np.linspace(0,1,1201);v=phase_map(u,s);source=np.array([cy.sample(t*cy.stride) for t in v]);p=np.array([quality(q,names,parents,lens,t,s) for q,t in zip(source,v)])
   heading=c['extraction']['travel_heading_relative_body'];travel=np.stack([v*c['stride']*np.sin(heading),np.zeros_like(v),v*c['stride']*np.cos(heading)],-1)
   world=p+travel[:,None];base_world=source+travel[:,None];foot=[names.index(n) for n in ['Toes_L','Toes_R']];hips=names.index('Hips');head=names.index('Head');chest=names.index('Chest');hands=[names.index('Hand_L'),names.index('Hand_R')]
   speeds=np.linalg.norm(np.gradient(world[:,foot],T/1200,axis=0),axis=2);heights=world[:,foot,1];floor=heights.min();mask=heights<floor+.025
   clearances=[segment_distance(q[h],q[hips],q[chest]) for q in p for h in hands]
   # Radius is a conservative diagnostic threshold, not mesh collision truth.
   row=dict(base=c['id'],strength=s,source_sha256_matches=hashlib.sha256((ROOT/c['source']['file']).read_bytes()).hexdigest()==c['source_sha256'],
    toe_floor=float(floor),low_toe_speed_p95=float(np.quantile(speeds[mask],.95)),low_toe_samples=int(mask.sum()),
    low_toe_sliding_proxy_threshold=.025,min_hand_to_torso_segment=float(min(clearances)),
    hand_torso_below_004_count=int(sum(x<.04 for x in clearances)),
    protected_foot_world_error=float(np.max(abs(world[:,foot]-base_world[:,foot]))),
    pelvis_shape_displacement_range=np.quantile(p[:,hips,1]-source[:,hips,1],[0,.5,1]).tolist(),
    head_shape_displacement_range=np.quantile(p[:,head,1]-source[:,head,1],[0,.5,1]).tolist(),
    hand_rms_shape_displacement=float(np.sqrt(np.mean((p[:,hands]-source[:,hands])**2))),
    source_time_rate_bounds=[1-.32*s,1+.32*s],native_cycle_seconds=T,native_mean_speed=c['stride']/T,
    human_naturalness=None,human_confidence=None,human_intimidation=None,human_status=None)
   rows.append(row)
 out=ROOT/'data/expression-space-lab/audit.json';out.write_text(json.dumps(rows,ensure_ascii=False,indent=2));print(out)
 print(json.dumps(rows,ensure_ascii=False,indent=2))
if __name__=='__main__':audit()
