import hashlib
import json
import math
from pathlib import Path
import unittest
from src.bvh import parse, load

ROOT = Path(__file__).resolve().parents[1]


def fixture(root_channels, child_channels, values):
    return parse(f'''HIERARCHY
ROOT Root {{ OFFSET 1 2 3 CHANNELS {len(root_channels.split())} {root_channels}
JOINT Child {{ OFFSET 0 10 0 CHANNELS {len(child_channels.split())} {child_channels}
End Site {{ OFFSET 2 0 0 }} }} }}
MOTION
Frames: 1
Frame Time: 0.1
{values}
''')


class KinematicsTests(unittest.TestCase):
    def assertPoint(self, actual, expected):
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=7)

    def test_parent_rotation_rotates_child_offset_and_end_site(self):
        m = fixture('Zrotation', 'Xrotation', '90 0')
        for a, b in zip(m.positions(0), [(1, 2, 3), (-9, 2, 3), (-9, 4, 3)]):
            self.assertPoint(a, b)

    def test_child_position_is_added_before_rotation(self):
        m = fixture('Zrotation', 'Xposition Yposition Zrotation', '90 3 4 90')
        self.assertPoint(m.positions(0)[1], (-13, 5, 3))
        self.assertPoint(m.positions(0)[2], (-15, 5, 3))

    def test_interleaved_position_is_transformed_in_channel_order(self):
        a = fixture('Zrotation Xposition', 'Xrotation', '90 5 0')
        b = fixture('Xposition Zrotation', 'Xrotation', '5 90 0')
        self.assertPoint(a.positions(0)[0], (1, 7, 3))
        self.assertPoint(b.positions(0)[0], (6, 2, 3))

    def test_noncommuting_euler_order(self):
        a = fixture('Zrotation Xrotation', 'Xrotation', '90 90 0')
        b = fixture('Xrotation Zrotation', 'Xrotation', '90 90 0')
        self.assertPoint(a.positions(0)[1], (1, 2, 13))
        self.assertPoint(b.positions(0)[1], (-9, 2, 3))

    def test_rotation_y_sign_and_root_translation(self):
        m = fixture('Xposition Yrotation', 'Zposition', '5 90 2')
        self.assertPoint(m.positions(0)[1], (8, 12, 3))
        self.assertPoint(m.positions(0)[2], (8, 12, 1))

    def test_playback_last_sample_duration_clamp_loop(self):
        m = parse('''HIERARCHY ROOT R { OFFSET 0 0 0 CHANNELS 1 Xposition }
MOTION Frames: 3 Frame Time: 0.1 0 1 2''')
        self.assertAlmostEqual(m.duration, .3)
        self.assertEqual([m.frame_at(t) for t in [0, .099, .1, .299, m.duration]], [0, 0, 1, 2, 0])
        self.assertEqual(m.frame_at(999, False), 2)
        self.assertEqual(m.frame_at(-1, False), 0)
        with self.assertRaises(ValueError):
            m.frame_at(float('nan'))
        with self.assertRaises(IndexError):
            m.positions(-1)

    def test_real_pilot_hashes_all_frames_finite_and_translation_evidence(self):
        entries = json.loads((ROOT / 'data/pilot_manifest.json').read_text())['entries']
        self.assertEqual(len(entries), 12)
        for entry in entries:
            with self.subTest(file=entry['file']):
                path = ROOT / entry['file']
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
                m = load(path)
                poses = [m.positions(i) for i in range(len(m.frames))]
                self.assertTrue(all(math.isfinite(v) for p in poses for j in p for v in j))
                self.assertEqual(len(poses[0]), 27)
                hips = next(i for i, j in enumerate(m.joints) if j.name == 'Hips')
                spans = [max(p[hips][a] for p in poses)-min(p[hips][a] for p in poses) for a in (0, 2)]
                self.assertGreater(max(spans), 100)  # These are travelling clips, even with static root.
                if entry['source_content'] == 'walk' and entry['source_style'] == 'normal':
                    self.assertPoint(poses[0][hips], (-1.71443, 184.1945, -410.123))
