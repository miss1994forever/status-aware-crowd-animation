import json
from pathlib import Path
import re
import tempfile
import unittest
from scripts.build_motion_preview import build


class PreviewBuildTests(unittest.TestCase):
    def test_self_contained_bundle_has_every_frame_and_attribution(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            clips = build(destination=target)
            html = (target / 'index.html').read_text()
            self.assertNotIn('/*__', html)
            self.assertNotRegex(html, r'<(?:script|link)[^>]+(?:src|href)=')
            self.assertNotRegex(html, r'\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(')
            data = json.loads(re.search(r'const DATA = (.*);\n', html)[1])
            self.assertEqual(len(data['clips']), 12)
            self.assertEqual(sum(len(c['poses']) for c in clips), 3014)
            self.assertEqual(data['creator'], 'Bandai Namco Research Inc.')
            self.assertEqual(data['license'], 'CC BY-NC 4.0')
            self.assertTrue((target / 'LICENSE.txt').stat().st_size > 0)
            self.assertEqual(len(json.loads((target / 'evidence.json').read_text())), 12)
            for c in data['clips']:
                self.assertEqual(c['translationMode'], 'channels_replace_offset')
                self.assertAlmostEqual(c['duration'], len(c['poses']) * c['frameTime'])
                self.assertTrue(all(len(p) == len(c['parents']) for p in c['poses']))
            self.assertEqual(data['clips'][0]['poses'][0][1], [-1.71443, 90.2704, -407.123])
