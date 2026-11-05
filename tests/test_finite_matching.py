import unittest
import numpy as np
from pathlib import Path
from src.bvh import load
from src.finite_motion import FiniteSequence
from src.finite_matching import Database, Matcher, Segment, heading, yaw_quaternion


SOURCE=Path(__file__).resolve().parents[1]/'data/raw/emm-pilot/selected/DataEMM/emm/basic_locomotion_2.bvh'


class FiniteMatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seq=FiniteSequence(load(SOURCE))
        cls.db=Database([cls.seq],stride=30)

    def test_features_have_real_future(self):
        self.assertTrue(np.all(self.db.times+1<=self.seq.duration))
        self.assertTrue(np.isfinite(self.db.future).all())

    def test_heading_roundtrip(self):
        a=np.array([-2.,-.3,0.,1.,2.9])
        np.testing.assert_allclose(heading(yaw_quaternion(a)),a,atol=1e-12)

    def test_same_inputs_same_decisions(self):
        a=Matcher(self.db);b=Matcher(self.db)
        for t in np.arange(0,2,.4):
            ra=a.choose(float(t),[0.,.7],0.);rb=b.choose(float(t),[0.,.7],0.)
            self.assertEqual(ra,rb)
            np.testing.assert_allclose(a.pose(t+.2),b.pose(t+.2),atol=1e-12)

    def test_switch_blend_start_and_end(self):
        m=Matcher(self.db); old=m.active
        root,q=m.local(.4)
        m.active=Segment(self.seq,0,10.,.4,root[[0,2]],float(heading(q[0])-heading(self.seq.local_sample(10.)[1][0])))
        m.outgoing=old;m.last_change=.4
        np.testing.assert_allclose(m.pose(.4),self.seq.forward(*old.local(.4)),atol=1e-12)
        np.testing.assert_allclose(m.pose(.65),m.pose(.65,blend=False),atol=1e-12)
        p=np.array([m.pose(t) for t in np.linspace(.4,.65,21)])
        for j,pa in enumerate(self.seq.parents):
            if pa is not None:
                np.testing.assert_allclose(np.linalg.norm(p[:,j]-p[:,pa],axis=-1),np.linalg.norm(self.seq.offsets[j]),atol=1e-12)
        with self.assertRaises(ValueError):m.choose(.5,[0,1],0.)

    def test_source_time_advances_without_modulo(self):
        m=Matcher(self.db)
        r,_=m.active.local(2.)
        expected=self.seq.placed(3.,entry=1.,yaw=m.active.yaw)[0]
        np.testing.assert_allclose(r,expected,atol=1e-12)

    def test_incompatible_skeleton_rejected(self):
        bad=FiniteSequence(load(SOURCE));bad.names=bad.names.copy();bad.names[-1]='wrong'
        with self.assertRaises(ValueError):Database([self.seq,bad])


if __name__=='__main__':unittest.main()
