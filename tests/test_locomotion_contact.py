from pathlib import Path
import unittest
from src.bvh import load
from src.locomotion import build_cycle
from src.locomotion_contact import infer_contacts,runs

ROOT=Path(__file__).resolve().parents[1]


class ContactInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.motion=load(ROOT/'data/raw/bandai-pilot/dataset-1_walk_normal_001.bvh')
        cls.cycle=build_cycle(cls.motion)
        cls.contacts=infer_contacts(cls.motion,cls.cycle)

    def test_circular_interval_crosses_phase_seam_without_reanchor(self):
        self.assertEqual(runs([True,True,False,False,True],True),[(4,7)])
        left=self.contacts['feet'][0]['intervals'][0]
        self.assertGreater(left['start']+left['duration'],1)

    def test_candidates_require_height_speed_and_duration(self):
        t=self.contacts['thresholds']
        self.assertEqual(t['min_consecutive_source_frames'],3)
        for f in self.contacts['feet']:
            raw=self.contacts['raw_diagnostics'][f['side']]
            self.assertLess(raw['raw_candidate_toe_speed_max'],t['toe_speed_body_heights_per_second'])
            self.assertGreater(raw['raw_candidate_count'],20)
            self.assertLess(f['ground_reference'],.01)
            self.assertTrue(all(self.cycle.bone_lengths[j]==0 for j in f['descendants']))
            self.assertGreater(raw['raw_full_cycle_toe_speed']['max'],1)  # Low swing samples cannot become support solely by height.

    def test_contacts_do_not_mutate_cycle_or_source(self):
        before=self.cycle.sample(.23)
        again=infer_contacts(self.motion,self.cycle)
        self.assertEqual(again,self.contacts)
        self.assertEqual(before,self.cycle.sample(.23))
