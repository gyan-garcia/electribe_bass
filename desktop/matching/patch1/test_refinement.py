import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from scipy.io import wavfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from fit import Renderer
from mariana_fit import EXTENDED_NAMES


class RefinementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=json.loads((HERE/'report.json').read_text())

    def test_architecture_and_preferred_character_are_frozen(self):
        self.assertEqual(self.report['architecture'],'svf12')
        old=self.report['outputs']['preferred']['parameters']
        for name in ('refined','gentle'):
            new=self.report['outputs'][name]['parameters']
            for parameter in self.report['frozen_parameters']:
                self.assertEqual(new[parameter],old[parameter],(name,parameter))
        self.assertEqual(set(self.report['mutable_parameters']),
                         {'cutoff_hz','filter_env_octaves','filter_decay_s','filter_attack_s',
                          'filter_sustain','filter_curve','filter_key_tracking'})

    def test_exports_headroom_and_silence(self):
        for name in ('preferred','refined','gentle'):
            rate,audio=wavfile.read(HERE/f'{name}-same-phrase.wav')
            self.assertEqual(rate,24000)
            self.assertEqual(len(audio),310155)
            self.assertLess(np.max(abs(audio.astype(np.int32))),32767)
            self.assertGreater(float(np.std(audio)),10)
            self.assertTrue(np.all(audio[:8400]==0))

    def test_saved_engine_and_deterministic_presets(self):
        expected=hashlib.sha256((HERE/'voice-snapshot.c').read_bytes()).hexdigest()
        self.assertEqual(self.report['source_sha256'],expected)
        events=json.loads((HERE.parent/'mariana/events.json').read_text())
        renderer=Renderer(events,library_path=HERE/'voice.so',function_name='render_rubber_voice')
        controls=renderer.controls(0,2)
        for name in ('preferred','refined','gentle'):
            settings=np.array([self.report['outputs'][name]['parameters'][key] for key in EXTENDED_NAMES])
            first=renderer.render(settings,0,controls)
            self.assertTrue(np.array_equal(first,renderer.render(settings,0,controls)))

    def test_unseen_notes_are_not_search_notes(self):
        self.assertFalse(set(self.report['audit_notes']) & set(self.report['training_notes']))
        self.assertFalse(set(self.report['audit_notes']) & set(self.report['selection_notes']))


if __name__=='__main__':
    unittest.main()
