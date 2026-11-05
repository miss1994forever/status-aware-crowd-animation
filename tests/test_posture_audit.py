import math
from pathlib import Path
import unittest
from src.bvh import parse, load
from scripts.audit_pilot_posture import quaternion_positions, percentile

ROOT = Path(__file__).resolve().parents[1]


class TranslationConventionTests(unittest.TestCase):
    def test_replacement_preserves_end_sites_and_unanimated_axes(self):
        motion = parse('''HIERARCHY ROOT R { OFFSET 1 2 3 CHANNELS 1 Zrotation
JOINT C { OFFSET 0 10 0 CHANNELS 3 Xposition Yposition Zrotation
End Site { OFFSET 2 0 0 } } } MOTION Frames: 1 Frame Time: .1 90 3 4 90''')
        for actual, expected in zip(motion.positions(0, translation_mode='channels_replace_offset'), [(1,2,3),(-3,5,3),(-5,5,3)]):
            for x, y in zip(actual, expected):
                self.assertAlmostEqual(x, y)

    def test_replacement_rejects_interleaved_translation(self):
        motion = parse('HIERARCHY ROOT R { OFFSET 0 0 0 CHANNELS 2 Zrotation Xposition } MOTION Frames: 1 Frame Time: .1 90 1')
        with self.assertRaises(ValueError):
            motion.positions(0, translation_mode='channels_replace_offset')
        with self.assertRaises(ValueError):
            motion.positions(0, translation_mode='guess')

    def test_real_source_hips_matches_channels_not_doubled_offset(self):
        motion = load(ROOT / 'data/raw/bandai-pilot/dataset-1_walk_normal_001.bvh')
        positions = motion.positions(0, translation_mode='channels_replace_offset')
        for x, y in zip(positions[1], (-1.71443, 90.2704, -407.123)):
            self.assertAlmostEqual(x, y)
        # Spine's source local translation is ~15.7357, not 2 × OFFSET.
        self.assertAlmostEqual(math.dist(positions[1], positions[2]), 15.7357, places=5)

    def test_quaternion_reference_on_noncommuting_rotations(self):
        motion = parse('''HIERARCHY ROOT R { OFFSET 0 0 0 CHANNELS 3 Zrotation Xrotation Yrotation
JOINT C { OFFSET 0 10 0 CHANNELS 3 Xrotation Yrotation Zrotation
End Site { OFFSET 2 0 0 } } } MOTION Frames: 1 Frame Time: .1 30 90 -15 12 -37 2''')
        for p, q in zip(motion.positions(0, translation_mode='channels_replace_offset'), quaternion_positions(motion, 0)):
            for x, y in zip(p, q):
                self.assertAlmostEqual(x, y, places=9)

    def test_percentiles_interpolate(self):
        self.assertEqual(percentile([3, 1, 2], .5), 2)
        self.assertAlmostEqual(percentile([0, 10], .05), .5)


if __name__ == '__main__':
    unittest.main()
