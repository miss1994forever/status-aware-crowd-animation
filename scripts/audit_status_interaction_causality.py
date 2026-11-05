"""Controlled social-channel interventions with real geometry held fixed."""
import json,sys
from dataclasses import replace
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.build_status_interaction_lab import library,scene,save,DATA
from src.predictive_motion_lab.controller import initial
from src.expression_layer import personal_library
from src.status_interaction_lab.social import *
from src.status_interaction_lab.navigation import choose,DEFAULT
from src.status_interaction_lab.motion import rollout


def main():
    l=library();spec=scene(51001,kind='pair',duration=4);states=initial(l,spec)
    states[0].pos=np.array([0.,0.]);states[1].pos=np.array([.7,1.2]);own=states[0]
    geometry=[visible(s) for s in states];personal=personal_library(l,own.reference,CONFIG['personal_strength'])
    rows=[]
    for pitch,turn in [(-.15,0),(.15,0),(0,-.2),(0,.2)]:
        observed=[geometry[0],replace(geometry[1],pose=transform(l,geometry[1].pose,pitch,turn))]
        h={};r=None
        for _ in range(5):r=respond(geometry[0],observed,l.names,h,0.,'C2',CONFIG)
        lib=controlled_library(personal,PrivateSelf(1),r.applied,CONFIG)
        opt,d=choose(lib,own,geometry,[], 'long_cv',DEFAULT)
        p=None if opt is None else rollout(lib,own,opt,np.arange(1,5)*.05)
        rows.append(dict(pitch=pitch,turn=turn,social=r.social,geometric=r.geometric,applied=r.applied,safe_count=d['safe_count'],selected=None if opt is None else opt.tolist(),end_pose=None if p is None else p['pose'][-1,0].tolist()))
    hidden=[]
    for x in [0,1]:
        states[1].goal=np.array([100*x,-100*x]);states[1].reference=x;states[1].clip=x;states[1].status=2*x-1
        h={}
        for _ in range(5):r=respond(visible(own),[visible(s) for s in states],l.names,h,0.,'C2',CONFIG)
        hidden.append(dict(social=r.social,applied=r.applied))
    result=dict(geometry_sha256=__import__('hashlib').sha256(np.array([g.pose for g in geometry]).tobytes()).hexdigest(),
       interventions=rows,hidden_equal=hidden[0]==hidden[1],hidden=hidden,
       fixed_geometric_response=len(set(r['geometric'] for r in rows))==1,
       visible_pitch_effect=abs(rows[0]['social']-rows[1]['social']),visible_torso_effect=abs(rows[2]['social']-rows[3]['social']),
       note='Social observations changed; geometry list passed to real safety chooser unchanged. Different candidate shape is still checked. No counterfactual hidden value enters observer.')
    save(DATA/'causal-interventions.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['interventions']}))
if __name__=='__main__':main()
