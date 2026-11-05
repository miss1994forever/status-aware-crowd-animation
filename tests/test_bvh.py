import unittest
from src.bvh import parse


SAMPLE = """HIERARCHY
ROOT Hips {
 OFFSET 0 0 0
 CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
 JOINT Chest {
  OFFSET 0 10 0
  CHANNELS 3 Zrotation Xrotation Yrotation
  End Site { OFFSET 0 5 0 }
 }
}
MOTION
Frames: 2
Frame Time: 0.03333333333333333
0 0 0 0 0 0 0 0 0
1 2 3 10 20 30 40 50 60
"""


class BVHTests(unittest.TestCase):
    def test_hierarchy_and_channel_order(self):
        motion = parse(SAMPLE)
        self.assertEqual([j.parent for j in motion.joints], [None, 0, 1])
        self.assertEqual(motion.joints[1].channel_start, 6)
        self.assertEqual(motion.joints[0].channels[-3:], ["Zrotation", "Xrotation", "Yrotation"])
        self.assertEqual(motion.joints[2].offset, (0, 5, 0))

    def test_summary(self):
        summary = parse(SAMPLE).summary()
        self.assertAlmostEqual(summary["fps"], 30)
        self.assertEqual(summary["root_position_bounds_source_units"]["Zposition"], [0, 3])
        self.assertIsNone(summary["status_label"])

    def test_bad_frame_count(self):
        with self.assertRaises(ValueError):
            parse(SAMPLE.replace("Frames: 2", "Frames: 3"))

    def test_bad_channel(self):
        with self.assertRaises(ValueError):
            parse(SAMPLE.replace("Zrotation", "BAD", 1))

    def test_non_finite(self):
        with self.assertRaises(ValueError):
            parse(SAMPLE.replace("1 2 3 10", "nan 2 3 10"))

    def test_non_positive_time(self):
        with self.assertRaises(ValueError):
            parse(SAMPLE.replace("0.03333333333333333", "0"))

    def test_truncated_hierarchy(self):
        with self.assertRaises(ValueError):
            parse("HIERARCHY ROOT Hips {")

    def test_trailing_values(self):
        with self.assertRaises(ValueError):
            parse(SAMPLE + "1")


if __name__ == "__main__":
    unittest.main()
