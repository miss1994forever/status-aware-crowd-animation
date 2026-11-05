import hashlib
import json
import math
from pathlib import Path
import unittest

from src.bvh import load
from src.locomotion import Cycle, build_cycle

ROOT=Path(__file__).resolve().parents[1]


class CandidateLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'outputs/motion-candidate-lab/lab.json').read_text())

    def test_all_twelve_sources_and_common_scale(self):
        clips=self.data['clips'];self.assertEqual(len(clips),12)
        self.assertEqual(len({c['review']['measurements']['reference_height_source_units'] for c in clips}),1)
        for c in clips:
            s=c['review']['source']
            self.assertEqual(hashlib.sha256((ROOT/s['file']).read_bytes()).hexdigest(),s['sha256'])
            self.assertIsNone(s['status_label'])

    def test_unedited_source_transform(self):
        for c in self.data['clips']:
            motion=load(ROOT/c['review']['source']['file']);meta=c['review']['measurements']
            h=meta['reference_height_source_units'];theta=meta['anatomical_heading_radians'];co,si=math.cos(theta),math.sin(theta)
            source=[motion.positions(i,translation_mode='channels_replace_offset')[1:] for i in [0,len(motion.frames)//2,len(motion.frames)-1]]
            hips=c['names'].index('Hips');origin=source[0][hips]
            for frame,p in zip([0,len(motion.frames)//2,len(motion.frames)-1],source):
                for j,point in enumerate(p):
                    x,z=point[0]-origin[0],point[2]-origin[2]
                    self.assertAlmostEqual(c['raw'][frame][j][0],(co*x-si*z)/h,places=8)
                    self.assertAlmostEqual(c['raw'][frame][j][2],(si*x+co*z)/h,places=8)
                    self.assertAlmostEqual(c['raw'][frame][j][1]-c['raw'][0][j][1],(point[1]-source[0][j][1])/h,places=8)

    def test_baseline_matches_original_M01(self):
        c=self.data['clips'][0];old=build_cycle(load(ROOT/c['review']['source']['file']))
        new=c['methods']['baseline']
        self.assertEqual(new['evidence']['start'],old.evidence['start_frame_zero_based'])
        self.assertEqual(new['evidence']['period_frames'],old.evidence['period_frames'])
        self.assertAlmostEqual(new['evidence']['max_output_change'],old.evidence['max_final_position_correction_body_heights'],places=10)

    def test_selected_source_interval_is_unmodified(self):
        for c in self.data['clips']:
            hips=c['names'].index('Hips')
            for d in c['methods'].values():
                e=d['evidence'];start,end=e['start'],e['end'];n=end-start
                origin=c['raw'][start][hips];drift=[(b-a)/n if k!=1 else 0 for k,(a,b) in enumerate(zip(origin,c['raw'][end][hips]))]
                for f in [0,n//2,n]:
                    for j,p in enumerate(d['source_poses'][f]):
                        for k in range(3):self.assertAlmostEqual(p[k],c['raw'][start+f][j][k]-(origin[k] if k!=1 else 0)-f*drift[k],places=8)

    def test_subsets_and_harmonic_selection(self):
        clips=self.data['clips']
        self.assertTrue(all(c['review']['methods']['improved']['accepted'] for c in clips[:3]))
        self.assertEqual(clips[0]['review']['measurements']['selected_recurrence_peak']['frames'],33)
        self.assertEqual(clips[1]['methods']['improved']['evidence']['period_frames'],49)
        self.assertFalse(clips[3]['review']['methods']['improved']['accepted'])
        m08=clips[7]['review']['methods']['improved']
        self.assertTrue(m08['accepted'])
        self.assertEqual(m08['evidence']['selected_rank'],1)
        self.assertGreater(m08['closure_trials'][0]['evidence']['max_output_change'],.05)
        self.assertLess(m08['evidence']['max_output_change'],.05)

    def test_cycle_output_geometry_and_boundary(self):
        for c in self.data['clips']:
            for method,d in c['methods'].items():
                cycle=Cycle(d['poses'],d['tangents'],d['stride'],d['evidence'],d['parents'],d['bone_lengths'])
                for i in range(81):
                    pose=cycle.sample(cycle.stride*i/80)
                    self.assertTrue(all(math.isfinite(v) for p in pose for v in p))
                    for j,parent in enumerate(cycle.parents):
                        if parent is not None:self.assertAlmostEqual(math.dist(pose[j],pose[parent]),cycle.bone_lengths[j],places=10)
                self.assertLess(d['evidence']['seam_velocity_epsilon_rms'],.001)

    def test_direction_kept_and_rejected_versions_not_substituted(self):
        for c in self.data['clips'][3:]:
            for d in c['methods'].values():
                heading=d['evidence']['travel_heading_relative_body']
                content=c['review']['source']['source_content']
                if content=='walk-back':self.assertGreater(abs(heading),2.6)
                else:
                    measured=math.radians(c['review']['measurements']['travel_relative_facing_degrees'])
                    self.assertLess(abs(math.atan2(math.sin(heading-measured),math.cos(heading-measured))),.2)
                    self.assertGreater(abs(heading),.2)
        self.assertEqual(self.data['clips'][3]['methods'],{})

    def test_page_packaging_and_scope(self):
        html=(ROOT/'outputs/motion-candidate-lab/index.html').read_text()
        self.assertNotIn('/*__',html)
        self.assertNotIn('<script src=',html)
        self.assertNotIn('solveLeg',html)
        self.assertIn('不循环',html)
        self.assertIn('CC BY-NC 4.0',html)


if __name__=='__main__':unittest.main()
