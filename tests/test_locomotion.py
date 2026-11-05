import hashlib
import json
import math
from pathlib import Path
import unittest
from src.bvh import load
from src.locomotion import build_cycle,norm,path_at,place_pose,source_positions

ROOT=Path(__file__).resolve().parents[1]


class LocomotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=ROOT/'data/raw/bandai-pilot/dataset-1_walk_normal_001.bvh'
        cls.before=hashlib.sha256(cls.path.read_bytes()).hexdigest()
        cls.motion=load(cls.path)
        cls.cycle=build_cycle(cls.motion)

    def test_explicit_dataset_translation_and_source_preserved(self):
        p=source_positions(self.motion,0)
        self.assertAlmostEqual(p[1][1],90.2704)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.before)

    def test_detected_stride_not_full_recording_and_small_boundary_error(self):
        e=self.cycle.evidence
        self.assertGreater(e['candidate_count'],2000)
        self.assertTrue(24<=e['period_frames']<=42)
        self.assertGreater(e['start_frame_zero_based'],0)
        self.assertLess(e['end_frame_zero_based'],len(self.motion.frames)-1)
        self.assertLess(e['raw_endpoint_rms_body_heights'],.02)
        self.assertLess(e['max_final_position_correction_body_heights'],.04)
        self.assertGreater(e['forward_travel_cosine'],.95)

    def test_loop_position_and_velocity_continuity(self):
        c=self.cycle;h=1e-5
        center=c.sample(0);left=c.sample(-h);right=c.sample(h)
        for p,a,b in zip(center,left,right):
            self.assertLess(norm([x-y for x,y in zip(a,b)]),.001)
            lv=[(x-y)/h for x,y in zip(p,a)]
            rv=[(x-y)/h for x,y in zip(b,p)]
            self.assertLess(norm([x-y for x,y in zip(lv,rv)]),.02)
        self.assertEqual(c.sample(0),c.sample(c.stride))

    def test_fixed_bones_and_hips_residual_not_normalized_away(self):
        c=self.cycle;ys=[];xs=[]
        for i in range(200):
            pose=c.sample(c.stride*i/200);ys.append(pose[0][1]);xs.append(pose[0][0])
            for j,p in enumerate(c.parents):
                if p is not None:
                    self.assertAlmostEqual(norm([pose[j][a]-pose[p][a] for a in range(3)]),c.bone_lengths[j],places=9)
        self.assertGreater(max(ys)-min(ys),.01)
        self.assertGreater(max(xs)-min(xs),.005)

    def test_distance_drives_phase_and_stride_repeat(self):
        c=self.cycle
        for distance in [.2,.7,1.5]:
            for a,b in zip(c.sample(distance),c.sample(distance+c.stride)):
                self.assertLess(norm([x-y for x,y in zip(a,b)]),1e-12)
        # Any speed history integrating to the same distance gives the same pose.
        distance_a=sum(speed*dt for speed,dt in [(1,.3),(.5,.6)])
        distance_b=sum(speed*dt for speed,dt in [(.2,3)])
        for a,b in zip(c.sample(distance_a),c.sample(distance_b)):
            self.assertLess(norm([x-y for x,y in zip(a,b)]),1e-12)

    def test_path_tangent_heading_and_constant_arc_length_speed(self):
        for kind in ['straight','curve']:
            for d in [0,.4,10,20.106192982974676]:
                p,heading=path_at(d,kind);q,_=path_at(d+1e-5,kind)
                tangent=[(q[a]-p[a])/1e-5 for a in (0,2)]
                self.assertAlmostEqual(norm(tangent),1,places=6)
                self.assertLess(norm([tangent[0]-math.sin(heading),tangent[1]-math.cos(heading)]),1e-5)
        # Unwrapped heading continues through each complete ring, no atan2 wrap.
        a=path_at(20.10619,'curve')[1];b=path_at(20.10620,'curve')[1]
        self.assertLess(abs(b-a),1e-4)

    def test_ten_actor_separation_and_continuous_world_pose(self):
        c=self.cycle
        for kind in ['curve','straight']:
            for d in [0,1,7,23]:
                positions=[path_at(d,kind,i,10)[0] for i in range(10)]
                self.assertGreater(min(norm([a-b for a,b in zip(positions[i],positions[j])]) for i in range(10) for j in range(i)),.8)
            for seam in [c.stride,math.pi*6.4]:
                a,ha=path_at(seam-1e-6,kind);b,hb=path_at(seam+1e-6,kind)
                pa=place_pose(c.sample(seam-1e-6),a,ha);pb=place_pose(c.sample(seam+1e-6),b,hb)
                self.assertLess(max(norm([x-y for x,y in zip(u,v)]) for u,v in zip(pa,pb)),1e-4)

    def test_known_slip_is_reported(self):
        slip=self.cycle.evidence['contact_heuristic_straight_foot_speed_body_heights_per_second']
        self.assertGreater(slip['samples'],0)
        self.assertGreater(slip['max'],.05)  # Report a limitation, never silently call it foot locking.
        self.assertTrue(math.isfinite(slip['median']))
