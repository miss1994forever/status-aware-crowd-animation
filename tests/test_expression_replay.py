import copy
import json
from pathlib import Path
import unittest
import numpy as np
from src.predictive_motion_lab.motion import Library
from src.predictive_motion_lab.controller import simulate
from src.expression_replay import resynthesize, compare_contract

ROOT = Path(__file__).resolve().parents[1]


class FixedExpressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
        full = json.loads((ROOT/'outputs/crowd-mobility-lab/runs/train_shared-10-None-13_R0.json').read_text())
        cls.replay = {**full, 'frames': full['frames'][:121]}

    def test_zero_reproduces_executed_body(self):
        out = resynthesize(self.lib, self.replay, 0)
        c = compare_contract(self.lib, self.replay, out)
        self.assertLess(c['pose_node_difference_max'], 3e-6)

    def test_layers_keep_root_actions_legs_and_bones(self):
        for strength in [.5, 1]:
            out = resynthesize(self.lib, self.replay, strength)
            c = compare_contract(self.lib, self.replay, out)
            self.assertLess(c['non_upper_node_difference_max'], 3e-6)
            self.assertLess(c['rounded_bone_length_error_max'], 3e-6)
            self.assertGreater(c['pose_node_difference_max'], .01)
            self.assertEqual(out['frames'][0], self.replay['frames'][0])

    def test_source_unchanged_and_no_stale_planner_logs(self):
        before = copy.deepcopy(self.replay)
        out = resynthesize(self.lib, self.replay, 1)
        self.assertEqual(self.replay, before)
        self.assertEqual(out['decisions'], [])
        self.assertFalse(any(k.startswith('planning_') for k in out['runtime']))
        self.assertEqual(out['mode'], 'fixed_motion_expression_diagnostic')

    def test_invalid_strength_and_incomplete_block_rejected(self):
        with self.assertRaises(ValueError): resynthesize(self.lib, self.replay, 1.01)
        with self.assertRaises(ValueError):
            resynthesize(self.lib, {**self.replay, 'frames': self.replay['frames'][:-1]}, 1)

    def test_hold_preserves_pose(self):
        spec = {'starts': [[0, 0]], 'goals': [[0, 10]], 'reference': 'M02',
                'seed': 13, 'duration': .4, 'walls': [[-10, -10, 10, 10]]}
        source = simulate(self.lib, spec, 'G')
        out = resynthesize(self.lib, source, 1)
        self.assertTrue(out['frames'][-1]['agents'][0]['hold'])
        self.assertEqual(out['frames'][0]['agents'][0]['pose'], out['frames'][-1]['agents'][0]['pose'])


if __name__ == '__main__': unittest.main()
