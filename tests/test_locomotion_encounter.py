from pathlib import Path
import tempfile
import unittest
from scripts.build_locomotion_encounter import build,ROOT


class EncounterBuildTests(unittest.TestCase):
    def test_self_contained_uses_unmodified_gait_without_contact_ik(self):
        with tempfile.TemporaryDirectory() as directory:
            data=build(Path(directory));html=(Path(directory)/'index.html').read_text()
            self.assertNotIn('/*__',html)
            self.assertNotRegex(html,r'<(?:script|link)[^>]+(?:src|href)=')
            self.assertNotRegex(html,r'\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(')
            self.assertNotIn('function contactActor(',html)
            self.assertIn('function stepEncounter(',html)
            self.assertIn('not final',data['purpose'].replace('no final','not final'))
            self.assertEqual(data['translation_mode'],'channels_replace_offset')
            self.assertTrue((Path(directory)/'LICENSE.txt').exists())

    def test_contact_experiment_default_returns_to_original(self):
        html=(ROOT/'outputs/locomotion/index.html').read_text()
        self.assertIn('<option value="original" selected>',html)
        self.assertIn('未定为最终实验素材',html)
