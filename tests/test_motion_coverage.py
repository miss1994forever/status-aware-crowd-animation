import unittest
import numpy as np
from src.bvh import parse
from src.motion_coverage import positions,low_speed_intervals

SAMPLE='''HIERARCHY
ROOT Hips {
 OFFSET 1 2 3
 CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
 JOINT Chest {
  OFFSET 0 10 0
  CHANNELS 3 Yrotation Zrotation Xrotation
  End Site { OFFSET 0 5 0 }
 }
}
MOTION
Frames: 2
Frame Time: 0.1
0 0 0 0 0 0 0 0 0
1 2 3 10 20 30 40 50 60
'''

class CoverageTests(unittest.TestCase):
    def test_scalar_reference_both_conventions(self):
        m=parse(SAMPLE)
        for mode in ('offset_plus_channels','channels_replace_offset'):
            ref=np.array([m.positions(i,translation_mode=mode) for i in range(2)])
            np.testing.assert_allclose(positions(m,mode),ref,atol=1e-12)
    def test_fixed_bone_lengths(self):
        m=parse(SAMPLE);p=positions(m)
        for j in [1,2]:
            np.testing.assert_allclose(np.linalg.norm(p[:,j]-p[:,m.joints[j].parent],axis=-1),
                                       np.linalg.norm(m.joints[j].offset),atol=1e-12)
    def test_stationary_candidate_not_label(self):
        d=low_speed_intervals(np.zeros((60,1,3)),1/60,0,1)
        self.assertEqual(len(d['intervals']),1)
        self.assertIn('not validated',d['note'])
    def test_constant_motion(self):
        p=np.zeros((60,1,3));p[:,0,0]=np.arange(60)/60
        self.assertEqual(low_speed_intervals(p,1/60,0,1)['intervals'],[])

if __name__=='__main__':unittest.main()
