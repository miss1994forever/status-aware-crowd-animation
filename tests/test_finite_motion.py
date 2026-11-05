import unittest
import numpy as np
from src.bvh import parse
from src.finite_motion import FiniteSequence, Cursor, slerp
from tests.test_motion_coverage import SAMPLE


class FiniteMotionTests(unittest.TestCase):
    def setUp(self):
        self.motion = parse(SAMPLE)
        self.sequence = FiniteSequence(self.motion)

    def test_source_samples_match_scalar_fk(self):
        ref = np.array([self.motion.positions(i) for i in range(2)])
        np.testing.assert_allclose(self.sequence.sample([0, .1]), ref, atol=1e-12)

    def test_fractional_bones_remain_fixed(self):
        p = self.sequence.sample(np.linspace(0, .1, 41))
        for j, parent in enumerate(self.sequence.parents[1:], 1):
            np.testing.assert_allclose(np.linalg.norm(p[:, j]-p[:, parent], axis=-1),
                                       np.linalg.norm(self.motion.joints[j].offset), atol=1e-12)

    def test_rejects_outside_not_loop_or_hold(self):
        for t in [-1e-5, .10001, float('nan'), float('inf')]:
            with self.assertRaises(ValueError): self.sequence.sample(t)
        np.testing.assert_allclose(self.sequence.sample(.1), self.motion.positions(1), atol=1e-12)

    def test_placement_is_rigid_and_keeps_vertical_path(self):
        seq = self.sequence; t = np.linspace(0, .1, 17)
        raw = seq.sample(t); moved = seq.placed(t, origin_xz=(10, -4), yaw=np.pi/2)
        np.testing.assert_allclose(moved[..., 1], raw[..., 1], atol=1e-12)
        np.testing.assert_allclose(moved[0, 0, [0, 2]], [10, -4], atol=1e-12)
        np.testing.assert_allclose(np.linalg.norm(np.diff(moved, axis=0), axis=-1),
                                   np.linalg.norm(np.diff(raw, axis=0), axis=-1), atol=1e-12)

    def test_cursor_exhaustion_and_unconsumed_time(self):
        cursor = Cursor(self.sequence)
        a = cursor.advance(.06); b = cursor.advance(.06)
        self.assertFalse(a.exhausted); self.assertTrue(b.exhausted)
        self.assertAlmostEqual(b.consumed, .04); self.assertAlmostEqual(b.remaining, .02)
        np.testing.assert_allclose(a.root_delta+b.root_delta,
                                   self.sequence.root[-1]-self.sequence.root[0], atol=1e-12)
        with self.assertRaises(RuntimeError): cursor.advance(.01)

    def test_cursor_nonzero_entry_and_bad_step(self):
        cursor = Cursor(self.sequence, start=.05, origin_xz=(2, 3))
        with self.assertRaises(ValueError): cursor.advance(0)
        a = cursor.advance(.05)
        self.assertTrue(a.exhausted)
        np.testing.assert_allclose(a.pose, self.sequence.placed(.1, entry=.05, origin_xz=(2, 3)))

    def test_real_horizon_only(self):
        np.testing.assert_allclose(self.sequence.eligible_starts(.1), [0])
        self.assertEqual(len(self.sequence.eligible_starts(.1001)), 0)
        self.assertEqual(len(self.sequence.eligible_starts(0)), 2)
        for h in [-1, float('nan')]:
            with self.assertRaises(ValueError): self.sequence.eligible_starts(h)

    def test_shortest_arc_and_quaternion_sign(self):
        a = np.array([1., 0, 0, 0]); b = -a
        np.testing.assert_allclose(slerp(a, b, .5), a)
        # Crossing +179/-179 degrees must go through 180, not through zero.
        h = np.deg2rad(179)/2
        q = slerp(np.array([np.cos(h), 0, np.sin(h), 0]),
                  np.array([np.cos(h), 0, -np.sin(h), 0]), .5)
        self.assertAlmostEqual(abs(q[2]), 1.)

    def test_rejects_translating_children(self):
        m = parse(SAMPLE.replace('CHANNELS 3 Yrotation Zrotation Xrotation',
                                'CHANNELS 3 Xposition Zrotation Xrotation'))
        with self.assertRaises(ValueError): FiniteSequence(m)

    def test_window_and_input_unchanged(self):
        before = [row.copy() for row in self.motion.frames]
        self.sequence.sample(.05)
        self.assertEqual(before, self.motion.frames)
        for start, end in [(0, 0), (-1, 1), (0, 2)]:
            with self.assertRaises(ValueError): FiniteSequence(self.motion, start, end)


if __name__ == '__main__': unittest.main()
