import copy
import json
import unittest
from dataclasses import replace, fields
from pathlib import Path
import numpy as np
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.controller import initial
from src.status_interaction_lab.social import visible, transform, VisibleNeighbor
from src.status_response_v2.control import Memory, step, body_library, CONFIG


class ResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib=Library(json.loads(Path('data/predictive-motion-lab/library.json').read_text()))
    def setup(self):
        states=initial(self.lib,dict(seed=1,starts=[[0,0],[0,1.1]],goals=[[0,3],[0,-3]]))
        return replace(visible(states[0]),yaw=0,travel=0,speed=.6),replace(visible(states[1]),yaw=np.pi,travel=0,speed=.6)
    def respond(self,own,others,value=0,mode='C2'):
        memory=Memory()
        for _ in range(8): result=step(own,others,self.lib.names,value,memory,mode)
        return result,memory
    def test_frontal_is_not_zero(self):
        own,other=self.setup();a,_=self.respond(own,[other],mode='C1');b,_=self.respond(own,[other])
        self.assertGreater(b['turn']-a['turn'],.05)
        self.assertGreater(b['compact']-a['compact'],.05)
    def test_own_value_changes_response(self):
        own,other=self.setup();a,_=self.respond(own,[other],-1);b,_=self.respond(own,[other],1)
        self.assertGreater(abs(a['compact']-b['compact']),.05)
        self.assertEqual(a['target'],b['target'])
    def test_low_evidence_and_recovery(self):
        own,other=self.setup();m=Memory();r=step(own,[other],self.lib.names,0,m)
        self.assertIsNone(r['accommodation'])
        _,m=self.respond(own,[other]);start=abs(m.turn)+m.compact
        for _ in range(20):step(own,[],self.lib.names,0,m)
        self.assertLess(abs(m.turn)+m.compact,start*.01);self.assertFalse(m.samples)
    def test_neighbor_order(self):
        own,other=self.setup();left=replace(other,id=2,pos=np.array([-.5,1.4]))
        a,_=self.respond(own,[other,left]);b,_=self.respond(own,[left,other])
        self.assertEqual(a,b)
    def test_visible_change(self):
        own,other=self.setup()
        a,_=self.respond(own,[replace(other,pose=transform(self.lib,other.pose,-.2,0))])
        b,_=self.respond(own,[replace(other,pose=transform(self.lib,other.pose,.2,0))])
        self.assertGreater(abs(a['compact']-b['compact']),.03)
    def test_no_self_ablation(self):
        own,other=self.setup()
        a,_=self.respond(own,[other],-1,'C2-no-self')
        b,_=self.respond(own,[other],1,'C2-no-self')
        self.assertEqual(a,b)
    def test_observation_allowlist(self):
        self.assertEqual({f.name for f in fields(VisibleNeighbor)},
                         {'id','pos','yaw','travel','speed','pose','hold','arrived'})
    def test_control_rate_bounds(self):
        own,other=self.setup();m=Memory()
        for value in [-1]*8+[1]*8:
            before=(m.turn,m.compact)
            step(own,[other],self.lib.names,value,m)
            self.assertLessEqual(abs(m.turn-before[0]),CONFIG['max_turn_rate']*CONFIG['dt']+1e-12)
            self.assertLessEqual(abs(m.compact-before[1]),CONFIG['max_compact_rate']*CONFIG['dt']+1e-12)
            self.assertLessEqual(abs(m.turn),CONFIG['max_turn'])
            self.assertTrue(0<=m.compact<=CONFIG['max_compact'])
    def test_body_lengths_and_legs(self):
        base=self.lib.poses.copy();lib=body_library(self.lib,1,.35,.45)
        self.assertTrue(np.array_equal(base[:,:,16:],lib.poses[:,:,16:]))
        for j,p in enumerate(lib.parents):
            if p is not None:
                error=np.abs(np.linalg.norm(lib.poses[:,:,j]-lib.poses[:,:,p],axis=-1)-lib.lengths[j])
                # Source samples rounded to 8 decimals.
                self.assertLess(error.max(),3e-8)
        self.assertTrue(np.array_equal(base,self.lib.poses))


if __name__=='__main__':unittest.main()
