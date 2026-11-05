"""Mechanism/contract checks; not animation naturalness or status validation."""
import copy
import json
from pathlib import Path
import unittest
import numpy as np
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab import controller as old
from src.crowd_mobility_lab.reciprocal import project,halfplanes,velocity
from src.crowd_mobility_lab.controller import choose,simulate,DEFAULT,root_only,candidates
from src.expression_layer import personal_library

ROOT=Path(__file__).resolve().parents[1]


class MobilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
        cls.spec=next(s for s in json.loads((ROOT/'data/predictive-motion-lab/configs.json').read_text())['train'] if s['kind']=='shared')

    def test_projection_exact_small_problems(self):
        n=np.array([[1.,0],[0,1.]])
        v,ok=project(np.array([-.2,.2]),n,np.array([.3,.4]),1.)
        self.assertTrue(ok);np.testing.assert_allclose(v,[.3,.4],atol=1e-9)
        v,ok=project(np.array([2.,0]),np.zeros((0,2)),np.zeros(0),1.)
        np.testing.assert_allclose(v,[1,0]);self.assertTrue(ok)
        v,ok=project(np.zeros(2),np.array([[1.,0],[-1.,0]]),np.array([.8,.8]),1)
        self.assertFalse(ok);self.assertLessEqual(np.linalg.norm(v),1.+1e-9)

    def test_symmetric_pair_reciprocal_constraints(self):
        states=old.initial(self.lib,self.spec)[:2]
        a,b=states;a.pos=np.array([-1.,0]);b.pos=np.array([1.,0]);a.yaw=np.pi/2-a.travel;b.yaw=-np.pi/2-b.travel;a.speed=b.speed=1.
        na,ba,_=halfplanes(a,[a,b]);nb,bb,_=halfplanes(b,[a,b])
        va,_=project(np.array([1.,0]),na,ba,1.1);vb,_=project(np.array([-1.,0]),nb,bb,1.1)
        self.assertTrue(np.all(na@va>=ba-1e-8));self.assertTrue(np.all(nb@vb>=bb-1e-8))
        np.testing.assert_allclose(va,-vb,atol=1e-8)

    def test_hidden_neighbor_metadata_not_read(self):
        states=old.initial(self.lib,self.spec);s=states[0]
        a,da=choose(self.lib,s,states,[],'long_cv',DEFAULT,True)
        for o in states[1:]:o.reference=99999;o.clip=99999;o.goal=np.array([np.nan,np.nan])
        b,db=choose(self.lib,s,states,[],'long_cv',DEFAULT,True)
        np.testing.assert_array_equal(a,b);self.assertEqual(da,db)

    def test_root_preselection_matches_real_synthesis(self):
        s=old.initial(self.lib,self.spec)[0];opts=candidates(self.lib,s,np.array([.4,-.6]),DEFAULT)
        p=old.rollout(self.lib,s,opts[:10],np.arange(1,21)*.05)
        np.testing.assert_allclose(root_only(self.lib,s,opts[:10]),p['pos'][-1]-s.pos,atol=1e-12)

    def test_direction_bounds_and_layer_used_before_collision(self):
        s=old.initial(self.lib,self.spec)[1]
        opts=candidates(self.lib,s,np.array([1.,0]),DEFAULT);ci=opts[:,0].astype(int)
        self.assertTrue(np.all(np.abs((self.lib.angles[ci]-self.lib.angles[s.clip]+np.pi)%(2*np.pi)-np.pi)<=.7))
        self.assertTrue(np.all(s.speed/self.lib.speeds[ci]<=1.6+1e-10))
        layered=personal_library(self.lib,s.reference,1.)
        p=old.rollout(self.lib,s,opts[:10],np.arange(1,21)*.05)
        q=old.rollout(layered,s,opts[:10],np.arange(1,21)*.05)
        np.testing.assert_array_equal(p['pos'],q['pos'])
        # Ensure at least one non-reference candidate is actually affected by synthesis.
        other=opts[ci!=s.reference][:1]
        p=old.rollout(self.lib,s,other,np.arange(1,21)*.05);q=old.rollout(layered,s,other,np.arange(1,21)*.05)
        self.assertGreater(np.abs(p['pose']-q['pose']).max(),.01)

    def test_snapshot_order_determinism_and_no_globals_patched(self):
        spec={**self.spec,'duration':.4};original=old.choose
        a=simulate(self.lib,spec,'long_cv');b=simulate(self.lib,spec,'long_cv',reverse=True)
        self.assertEqual(a['frames'],b['frames']);self.assertIs(old.choose,original)

    def test_no_candidate_retains_explicit_failure(self):
        spec={**self.spec,'duration':.2,'walls':[[-10,-10,10,10]]}
        run=simulate(self.lib,spec,'long_cv')
        self.assertEqual(run['runtime']['arrival_times'],{})
        self.assertTrue(all(a['hold'] for a in run['frames'][-1]['agents']))


if __name__=='__main__':unittest.main()
