import json,unittest
from dataclasses import replace
from pathlib import Path
import numpy as np
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.controller import initial
from src.status_interaction_lab.social import *
from src.status_interaction_lab.simulation import simulate

class InteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.lib=Library(json.loads(Path('data/predictive-motion-lab/library.json').read_text()))
    def setup_pair(self):
        spec=dict(seed=51001,starts=[[0,0],[.6,1]],goals=[[0,3],[0,-3]],walls=[],duration=.8)
        states=initial(self.lib,spec)
        return spec,states
    def response(self,states,mode='C2'):
        h={};r=None
        for _ in range(5):r=respond(visible(states[0]),[visible(s) for s in states],self.lib.names,h,0.,mode,CONFIG)
        return r
    def test_hidden_information(self):
        _,s=self.setup_pair();before=self.response(s)
        s[1].goal[:]=[999,-999];s[1].reference=8;s[1].clip=8;s[1].status=123
        self.assertEqual(before,self.response(s))
        self.assertEqual(set(vars(visible(s[1]))),{'id','pos','yaw','travel','speed','pose','hold','arrived'})
    def test_visible_intervention_fixed_geometry(self):
        _,s=self.setup_pair();a=self.response(s)
        t=replace(s[1],pose=transform(self.lib,s[1].pose,.2,0))
        b=self.response([s[0],t])
        self.assertEqual(a.geometric,b.geometric);self.assertGreater(abs(a.social-b.social),.001)
        # Geometry sees original s in both cases; this function is purely social channel.
    def test_off_and_low_confidence(self):
        _,s=self.setup_pair();self.assertEqual(self.response(s,'C1'),self.response(s,'C2-off'))
        r=respond(visible(s[0]),[visible(x) for x in s],self.lib.names,{},0.,'C2',CONFIG)
        self.assertEqual(r.social,0);self.assertIsNone(r.observations[0]['estimate'])
    def test_numbering_and_order(self):
        _,s=self.setup_pair();a=self.response(s)
        t=[replace(s[0],id=92),replace(s[1],id=3)]
        b=self.response(t);self.assertEqual(a.social,b.social);self.assertEqual(a.applied,b.applied)
    def test_bone_and_legs(self):
        p=self.lib.sample(0,.1);q=transform(self.lib,p,.045,.25)
        self.assertTrue(np.array_equal(q[~upper_mask(self.lib)],p[~upper_mask(self.lib)]))
        for j,parent in enumerate(self.lib.parents):
            if parent is not None:self.assertAlmostEqual(np.linalg.norm(q[j]-q[parent]),self.lib.lengths[j],places=8)
    def test_rate_and_forget(self):
        _,s=self.setup_pair();h={};previous=0.
        for _ in range(10):
            r=respond(visible(s[0]),[visible(x) for x in s],self.lib.names,h,previous,'C2',CONFIG)
            self.assertLessEqual(abs(r.applied-previous),CONFIG['max_rate']*.2+1e-12);previous=r.applied
        respond(visible(s[0]),[],self.lib.names,h,previous,'C2',CONFIG);self.assertEqual(h,{})
    def test_simultaneous_and_off(self):
        spec,_=self.setup_pair();spec['starts']=[[-2,0],[2,0]]
        a=simulate(self.lib,spec,'C1');b=simulate(self.lib,spec,'C2-off');c=simulate(self.lib,spec,'C1',reverse=True)
        self.assertEqual(a['frames'],b['frames']);self.assertEqual(a['frames'],c['frames'])
if __name__=='__main__':unittest.main()

class ConstraintTests(unittest.TestCase):
    def test_prediction_execution_and_bounds(self):
        from scripts.build_status_interaction_lab import library,scene
        from src.status_interaction_lab.motion import rollout,MAX_RATE,TOE_RATE
        lib=library();s=initial(lib,scene(51001,kind='pair'))[0];opt=np.array([[s.clip,1.15,0.,0.]])
        full=rollout(lib,s,opt,np.arange(1,21)*.05);short=rollout(lib,s,opt,np.arange(1,5)*.05)
        self.assertTrue(np.array_equal(full['pose'][:4],short['pose']))
        self.assertGreaterEqual(full['pose'][:,:,:,1].min(),-1e-12)
        p=np.concatenate([s.pose[None,None],full['pose']],axis=0)
        for j,parent in enumerate(lib.parents):
            if parent is None or lib.lengths[j]<1e-8:continue
            bone=p[:,:,j]-p[:,:,parent];length=np.linalg.norm(bone,axis=-1)
            self.assertLess(abs(length-lib.lengths[j]).max(),1e-10)
            unit=bone/length[...,None];rate=np.arccos(np.clip((unit[1:]*unit[:-1]).sum(-1),-1,1))/.05
            self.assertLessEqual(rate.max(),(TOE_RATE if 'Toes' in lib.names[j] else MAX_RATE)+1e-7)
    def test_yoke_other_person_and_energy_record(self):
        from src.status_interaction_lab.yoke import matched_yoke
        run=json.loads(Path('outputs/status-interaction-lab/runs/dev-v3-pair-C2.json').read_text())
        signal,rows=matched_yoke(run)
        self.assertTrue(all(r['recipient']!=r['donor'] for r in rows));self.assertEqual(len(signal),80)

class MultipleNeighborTests(unittest.TestCase):
    def test_current_object_and_permutation(self):
        from scripts.build_status_interaction_lab import library
        lib=library();s=initial(lib,dict(seed=1,starts=[[0,0],[-.8,1],[.8,1]],goals=[[0,3],[0,-3],[0,-3]]))
        own=replace(visible(s[0]),yaw=0)
        a=visible(s[1]);b=visible(s[2])
        def compute(neighbors):
            h={}
            for _ in range(5):r=respond(own,neighbors,lib.names,h,0.,'C2',CONFIG)
            return r
        p=transform(lib,a.pose,.18,0);q=transform(lib,a.pose,-.18,0)
        one=[replace(a,pose=p),replace(b,pose=q)]
        two=[replace(a,pose=q),replace(b,pose=p)]
        x=compute(one);y=compute(two);z=compute(one[::-1])
        self.assertEqual(x.geometric,y.geometric);self.assertGreater(abs(x.social-y.social),.002)
        self.assertEqual(x,z)
    def test_social_full_reverse(self):
        from scripts.build_status_interaction_lab import library
        lib=library();spec=dict(seed=1,starts=[[0,0],[-.8,1],[.8,1]],goals=[[0,3],[0,-3],[0,-3]],walls=[],duration=.8)
        a=simulate(lib,spec,'C2');b=simulate(lib,spec,'C2',reverse=True)
        self.assertEqual(a['frames'],b['frames'])
        self.assertEqual(sorted(a['decisions'],key=lambda d:(d['t'],d['id'])),sorted(b['decisions'],key=lambda d:(d['t'],d['id'])))

class NavigationIsolationTests(unittest.TestCase):
    def test_real_crowd_neighbor_order_and_identifier(self):
        from scripts.build_status_interaction_lab import library
        from src.predictive_motion_lab.controller import State
        from src.status_interaction_lab.navigation import choose,DEFAULT
        from src.expression_layer import personal_library
        lib=library();run=json.loads(Path('outputs/status-interaction-lab/runs/dev-v3-ten-C2.json').read_text())
        f=run['frames'][60];prev=run['frames'][59];states=[]
        for i,(a,b) in enumerate(zip(f['agents'],prev['agents'])):
            states.append(State(i,np.array(a['pos']),np.array(run['spec']['goals'][i]),a['yaw'],a['travel'],a['speed'],lib.ids.index(a['clip']),lib.ids.index(['M01','M02','M03'][i%3]),a['phase'],np.array(a['pose']),(np.array(a['pose'])-np.array(b['pose']))/.05))
        observed=[visible(s) for s in states]
        for s in states:
            personal=personal_library(lib,s.reference,CONFIG['personal_strength'])
            own=controlled_library(personal,PrivateSelf(run['private_experiment'][str(s.id)]['status']),0.,CONFIG)
            a,da=choose(own,s,observed,[],'long_cv',DEFAULT)
            renumber=lambda i:97-i*3
            other=[replace(o,id=renumber(o.id)) for o in observed[::-1]]
            b,db=choose(own,replace(s,id=renumber(s.id)),other,[],'long_cv',DEFAULT)
            self.assertEqual(a is None,b is None)
            if a is not None:self.assertTrue(np.allclose(a,b,atol=1e-10))
            self.assertTrue(np.allclose(da['desired'],db['desired'],atol=1e-10))
