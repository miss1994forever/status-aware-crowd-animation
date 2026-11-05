"""Mechanism checks; these assertions do not establish naturalness or status."""
import json
from pathlib import Path
import unittest
import numpy as np
from src.predictive_motion_lab.motion import Library,wrap
from src.predictive_motion_lab.geometry import box_gap,box,world_pose
from src.predictive_motion_lab.controller import initial,options,rollout,choose,simulate
from src.predictive_motion_lab.evaluate import hull,hull_gap,audit

ROOT=Path(__file__).resolve().parents[1]


class PredictiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib=Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
        cls.cfg=json.loads((ROOT/'data/predictive-motion-lab/configs.json').read_text())

    def test_rectangles_and_hulls(self):
        unit=(np.zeros(2),np.eye(2),np.ones(2))
        self.assertAlmostEqual(box_gap(unit,(np.array([3.,0]),np.eye(2),np.ones(2))),1)
        self.assertAlmostEqual(box_gap(unit,(np.array([1.,0]),np.eye(2),np.ones(2))),-1)
        square=np.array([[-1,-1],[1,-1],[1,1],[-1,1]])
        self.assertAlmostEqual(hull_gap(square,square+[3,0],.08),.92)
        self.assertEqual(len(hull(np.vstack([square,[0,0]]))),4)

    def test_pose_box_contains_projected_bones_and_radius(self):
        p=self.lib.sample(0,.27);center,axes,half=box(p,np.array([.3,-.2]),np.array(.4))
        local=p[:,[0,2]]
        # Inverse world projection recovers local bound widths.
        self.assertTrue(np.all(half>=np.ptp(local,axis=0)/2+.04-1e-9))
        for yaw in np.linspace(-np.pi,np.pi,13):
            center,axes,half=box(p,np.array([.3,-.2]),np.array(yaw))
            world=world_pose(p,np.array([.3,-.2]),np.array(yaw))[:,[0,2]]
            projected=(world-center)@axes.T
            self.assertTrue(np.all(np.abs(projected)+.04<=half+1e-9))

    def test_direction_coverage_is_not_fake_sideways(self):
        s=initial(self.lib,self.cfg['train'][1])[0]
        opts=options(self.lib,s,'G');angles=self.lib.angles[opts[:,0].astype(int)]
        self.assertTrue(np.all(np.abs(wrap(angles-s.travel))<=.7))
        self.assertNotIn('M04',self.lib.ids)
        self.assertTrue(all(abs(a)<1.1 or abs(a)>2.9 for a in self.lib.angles))

    def test_rollout_bones_phase_and_bounds(self):
        s=initial(self.lib,self.cfg['train'][1])[0];opts=options(self.lib,s,'G')
        paths=rollout(self.lib,s,opts,np.arange(1,21)*.05)
        self.assertTrue(np.all(np.abs(paths['yaw'][0]-s.yaw)<=1.4*.05+1e-10))
        self.assertTrue(np.all(np.abs(paths['speed'][0]-s.speed)<=1.2*.05+1e-10))
        for j,p in enumerate(self.lib.parents):
            if p is not None:
                self.assertLess(np.max(np.abs(np.linalg.norm(paths['pose'][:,:,j]-paths['pose'][:,:,p],axis=-1)-self.lib.lengths[j])),1e-8)
        # A small-time start has continuous position, and is not an instantaneous clip swap.
        tiny=rollout(self.lib,s,opts[:1],np.array([1e-7]))
        self.assertLess(np.linalg.norm(tiny['pose'][0,0]-s.pose),1e-5)

    def test_blend_initial_derivative_uses_actual_speed(self):
        s=initial(self.lib,self.cfg['train'][2])[0]
        opt=np.array([[s.clip,.8,0,0]])
        p=rollout(self.lib,s,opt,np.array([1e-6]))['pose'][0,0]
        rms=np.sqrt(np.mean(((p-s.pose)/1e-6-s.pose_velocity)**2))
        self.assertLess(rms,.003)

    def test_no_candidate_is_explicit_failure(self):
        spec={**self.cfg['train'][0],'walls':[[-4,-4,4,4]],'duration':.2}
        s=initial(self.lib,spec)[0];opt,decision=choose(self.lib,s,[s],spec['walls'])
        self.assertIsNone(opt);self.assertEqual(decision['safe_count'],0)
        run=simulate(self.lib,spec,'G')
        self.assertTrue(run['frames'][-1]['agents'][0]['hold'])
        self.assertFalse(run['frames'][-1]['agents'][0]['arrived'])

    def test_determinism_and_simultaneous_order(self):
        spec={**self.cfg['train'][-1],'duration':.4}
        a=simulate(self.lib,spec,'G');b=simulate(self.lib,spec,'G',reverse=True)
        self.assertEqual(a['frames'],b['frames'])
        c=simulate(self.lib,spec,'G')
        self.assertEqual(a['frames'],c['frames'])

    def test_p_same_candidates_and_safety(self):
        s=initial(self.lib,self.cfg['train'][2])[0]
        _,a=choose(self.lib,s,[s],self.cfg['train'][2]['walls'],'G',0,True)
        _,b=choose(self.lib,s,[s],self.cfg['train'][2]['walls'],'G',2,True)
        self.assertEqual([(c['clip'],c['scale'],c['steer'],c['feasible']) for c in a['candidates']],[(c['clip'],c['scale'],c['steer'],c['feasible']) for c in b['candidates']])
        if any(c['selected'] for c in b['candidates']):self.assertTrue(next(c for c in b['candidates'] if c['selected'])['feasible'])

    def test_neighbors_do_not_expose_hidden_reference_or_clip(self):
        spec=self.cfg['train'][-1];states=initial(self.lib,spec)
        _,a=choose(self.lib,states[0],states,[],log=True)
        # Keep visible pose/kinematics exactly fixed; corrupt only hidden archive metadata.
        for other in states[1:]:other.reference=999999;other.clip=999999
        _,b=choose(self.lib,states[0],states,[],log=True)
        self.assertEqual(a,b)

    def test_phase_can_change_body_without_changing_root(self):
        s=initial(self.lib,self.cfg['train'][0])[0]
        clip=self.lib.ids.index('M07')
        opts=np.array([[clip,1.15,0,-.08],[clip,1.15,0,0]])
        paths=rollout(self.lib,s,opts,np.arange(1,21)*.05)
        np.testing.assert_array_equal(paths['pos'][:,0],paths['pos'][:,1])
        self.assertGreater(np.linalg.norm(paths['pose'][:,0]-paths['pose'][:,1],axis=-1).max(),.03)

    def test_end_to_end_supported_gate_and_dense_evaluator(self):
        spec={**self.cfg['train'][3],'duration':8}
        run=simulate(self.lib,spec,'G')
        measured=audit(run,self.lib)
        self.assertEqual(measured['arrived_fraction'],1.)
        self.assertLess(measured['max_proxy_penetration'],.001)
        self.assertLess(measured['max_bone_relative_error'],1e-8)
        self.assertEqual(measured['dense_samples'],960)

    def test_prediction_and_circle_are_real_ablations(self):
        s=initial(self.lib,self.cfg['train'][2])[0]
        logs={m:choose(self.lib,s,[s],self.cfg['train'][2]['walls'],m,log=True)[1] for m in ['G','circle','no_prediction','no_continuity']}
        self.assertNotEqual([c['clearance'] for c in logs['G']['candidates']],[c['clearance'] for c in logs['circle']['candidates']])
        self.assertNotEqual([c['clearance'] for c in logs['G']['candidates']],[c['clearance'] for c in logs['no_prediction']['candidates']])
        self.assertTrue(all(c['continuity']==0 for c in logs['no_continuity']['candidates']))


if __name__=='__main__':unittest.main()
