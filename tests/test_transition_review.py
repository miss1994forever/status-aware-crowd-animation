import json
from pathlib import Path
import unittest
import numpy as np
from scripts.build_transition_review import sequence
from src.predictive_motion_lab.motion import Library

ROOT = Path(__file__).resolve().parents[1]


class TransitionReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))

    def test_paired_roots_and_switch_boundary(self):
        a, b = [sequence(self.lib, 'M11', .125, m) for m in ['local', 'matched']]
        self.assertEqual(len(a['frames']), 81)
        self.assertEqual(a['frames'][-1]['t'], 4.)
        self.assertEqual(a['frames'][:25], b['frames'][:25])
        for i, (fa, fb) in enumerate(zip(a['frames'], b['frames'])):
            aa, bb = fa['agents'][0], fb['agents'][0]
            self.assertEqual(aa['clip'], 'M02' if i <= 24 else 'M11')
            for key in ['pos', 'yaw', 'travel', 'speed']:
                self.assertEqual(aa[key], bb[key])
        self.assertNotEqual(a['entry_offset'], b['entry_offset'])

    def test_reference_has_no_switch_or_phase_reset(self):
        a = sequence(self.lib, 'M03', .5, 'continue')
        self.assertIsNone(a['entry_offset'])
        self.assertTrue(all(f['agents'][0]['clip'] == 'M02' for f in a['frames']))
        self.assertTrue(all(np.isfinite(v) for v in a['metrics'].values()))

    def test_serialized_bone_lengths(self):
        a = sequence(self.lib, 'M03', .25, 'matched')
        poses = np.array([f['agents'][0]['pose'] for f in a['frames']])
        for j, parent in enumerate(self.lib.parents):
            if parent is not None:
                error = np.abs(np.linalg.norm(poses[:, j]-poses[:, parent], axis=-1)-self.lib.lengths[j])
                self.assertLess(error.max(), 3e-6)


if __name__ == '__main__':
    unittest.main()
