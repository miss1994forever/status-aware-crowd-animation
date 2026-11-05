import json
from pathlib import Path
import unittest
import numpy as np
from src.predictive_motion_lab import controller
from src.predictive_motion_lab.motion import Library
from src.expression_layer import layer_pose, upper_mask, unit_slerp, personal_library, layered_controller

ROOT = Path(__file__).resolve().parents[1]


class ExpressionLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
        cls.cfg = json.loads((ROOT/'data/predictive-motion-lab/configs.json').read_text())

    def test_identity_and_unmodified_lower_body(self):
        base = self.lib.poses.copy()
        ref = np.broadcast_to(base[1], base.shape)
        np.testing.assert_array_equal(layer_pose(self.lib, base, ref, 0), base)
        mixed = layer_pose(self.lib, base, ref, .5)
        np.testing.assert_array_equal(mixed[..., ~upper_mask(self.lib), :], base[..., ~upper_mask(self.lib), :])
        for j, parent in enumerate(self.lib.parents):
            if parent is not None:
                self.assertLess(np.max(np.abs(np.linalg.norm(mixed[..., j, :]-mixed[..., parent, :], axis=-1)-self.lib.lengths[j])), 3e-8)
        np.testing.assert_array_equal(self.lib.poses, base)

    def test_full_layer_own_reference_and_antipodal(self):
        lib = personal_library(self.lib, 1, 1.)
        np.testing.assert_array_equal(lib.poses[1], self.lib.poses[1])
        for j, parent in enumerate(lib.parents):
            if upper_mask(lib)[j]:
                target = self.lib.poses[1, :, j]-self.lib.poses[1, :, parent]
                actual = lib.poses[:, :, j]-lib.poses[:, :, parent]
                np.testing.assert_allclose(actual, np.broadcast_to(target, actual.shape), atol=3e-8)
        middle = unit_slerp(np.array([[1., 0, 0]]), np.array([[-1., 0, 0]]), .5)
        self.assertAlmostEqual(float(np.linalg.norm(middle)), 1.)
        self.assertLess(abs(float(middle[0, 0])), 1e-8)

    def test_zero_reproduces_controller_and_restores(self):
        spec = {**self.cfg['train'][2], 'duration': .4}
        expected = controller.simulate(self.lib, spec, 'G')['frames']
        original = controller.rollout
        with layered_controller(self.lib, 0):
            actual = controller.simulate(self.lib, spec, 'G')['frames']
        self.assertEqual(expected, actual)
        self.assertIs(controller.rollout, original)

    def test_planner_and_execution_use_same_layer(self):
        s = controller.initial(self.lib, self.cfg['train'][2])[0]
        opts = np.array([[0, 1., 0, 0]])
        with layered_controller(self.lib, 1):
            horizon = controller.rollout(self.lib, s, opts, np.arange(1, 21)*.05)
            executed = controller.rollout(self.lib, s, opts, np.arange(1, 5)*.05)
        np.testing.assert_array_equal(horizon['pose'][:4], executed['pose'])
        standard = controller.rollout(self.lib, s, opts, np.arange(1, 21)*.05)
        self.assertGreater(np.max(np.abs(horizon['pose']-standard['pose'])), .01)

    def test_neighbor_hidden_reference_not_read(self):
        states = controller.initial(self.lib, self.cfg['train'][-1])
        with layered_controller(self.lib, .5):
            a = controller.choose(self.lib, states[0], states, [], log=True)
            for neighbor in states[1:]:
                neighbor.reference = 999999
                neighbor.clip = 999999
            b = controller.choose(self.lib, states[0], states, [], log=True)
        np.testing.assert_array_equal(a[0], b[0])
        self.assertEqual(a[1], b[1])

    def test_layer_changes_collision_queries_not_only_rendering(self):
        spec = self.cfg['train'][2]
        s = controller.initial(self.lib, spec)[0]
        _, original = controller.choose(self.lib, s, [s], spec['walls'], log=True)
        with layered_controller(self.lib, 1):
            _, layered = controller.choose(self.lib, s, [s], spec['walls'], log=True)
        key = lambda d: [(c['clip'], c['scale'], c['steer'], c['phase_offset']) for c in d['candidates']]
        self.assertEqual(key(original), key(layered))
        differences = [abs(a['clearance']-b['clearance']) for a, b in zip(original['candidates'], layered['candidates'])]
        self.assertGreater(max(differences), .01)
        self.assertTrue(all('expression' not in c for c in layered['candidates']))

    def test_simultaneous_order_and_no_old_p(self):
        spec = {**self.cfg['train'][-1], 'duration': .2}
        with layered_controller(self.lib, .5):
            a = controller.simulate(self.lib, spec, 'G')['frames']
            b = controller.simulate(self.lib, spec, 'G', reverse=True)['frames']
            with self.assertRaises(ValueError):
                controller.simulate(self.lib, spec, 'G', p_weight=1)
        self.assertEqual(a, b)


if __name__ == '__main__':
    unittest.main()
