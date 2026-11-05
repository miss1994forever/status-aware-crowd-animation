import json
from pathlib import Path
import unittest
import numpy as np
from src.predictive_motion_lab import controller
from src.predictive_motion_lab.motion import Library
from src.transition_diagnostic import bounded_controller, select_bounded, matched_phase_offsets

ROOT = Path(__file__).resolve().parents[1]


class TransitionDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = Library(json.loads((ROOT/'data/predictive-motion-lab/library.json').read_text()))
        cfg = json.loads((ROOT/'data/predictive-motion-lab/configs.json').read_text())
        cls.spec = next(s for s in cfg['train'] if s.get('width') == .46)

    def test_original_bound_reproduces_frames(self):
        spec = {**self.spec, 'duration': .6}
        expected = controller.simulate(self.lib, spec, 'G')
        with bounded_controller(self.lib, .4):
            actual = controller.simulate(self.lib, spec, 'G')
        self.assertEqual(expected['frames'], actual['frames'])

    def test_gate_and_argmin(self):
        s = controller.initial(self.lib, self.spec)[0]
        opt, d = select_bounded(self.lib, controller.choose, s, [s],
                                self.spec['walls'], limit=.05)
        safe = [c for c in d['candidates'] if c['feasible']]
        self.assertTrue(safe)
        self.assertTrue(all(c['deformation'] <= .05 for c in safe))
        chosen = next(c for c in safe if c['selected'])
        self.assertEqual(chosen['score'], min(c['score'] for c in safe))
        self.assertIsNotNone(opt)

    def test_restore_on_error_and_family_filter(self):
        old_choose, old_options = controller.choose, controller.options
        with self.assertRaises(RuntimeError):
            with bounded_controller(self.lib, .1, True):
                s = controller.initial(self.lib, self.spec)[0]
                rows = controller.options(self.lib, s, 'G')
                for i in rows[:, 0].astype(int):
                    self.assertEqual(self.lib.clips[i]['source']['source_style'],
                                     self.lib.clips[s.reference]['source']['source_style'])
                raise RuntimeError('test scope cleanup')
        self.assertIs(controller.choose, old_choose)
        self.assertIs(controller.options, old_options)

    def test_no_solution_is_not_replaced_by_unsafe_candidate(self):
        s = controller.initial(self.lib, self.spec)[0]
        opt, d = select_bounded(self.lib, controller.choose, s, [s],
                                [[-4, -4, 4, 4]], limit=.05)
        self.assertIsNone(opt)
        self.assertEqual(d['safe_count'], 0)

    def test_phase_matching_preserves_budget_and_no_switch_phase(self):
        s = controller.initial(self.lib, self.spec)[0]
        old = controller.options(self.lib, s, 'G')
        with bounded_controller(self.lib, .1, phase_matching=True):
            new = controller.options(self.lib, s, 'G')
        np.testing.assert_array_equal(old[:, :3], new[:, :3])
        self.assertTrue(np.all(new[new[:, 0] == s.clip, 3] == 0))
        for clip in np.unique(new[:, 0].astype(int)):
            if clip == s.clip:
                continue
            matched = matched_phase_offsets(self.lib, s, clip)
            def costs(offsets):
                phase = (s.phase+offsets) % 1
                rate = s.speed/self.lib.speeds[clip]/self.lib.periods[clip]
                return (2*np.sqrt(np.mean((self.lib.sample(clip, phase)-s.pose)**2, axis=(1, 2)))
                        + .08*np.sqrt(np.mean((self.lib.velocity(clip, phase, rate)-s.pose_velocity)**2, axis=(1, 2))))
            self.assertLessEqual(costs(matched).sum(), costs(np.array([-.08, 0, .08])).sum()+1e-12)


if __name__ == '__main__':
    unittest.main()
