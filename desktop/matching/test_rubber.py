import json
import subprocess
import unittest

import numpy as np
from scipy.io import wavfile

from analyze import ROOT
from fit import Renderer, NAMES
from mariana_fit import BOUNDS, INDICES, DEST


class RubberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(['gcc','-O3','-shared','-fPIC',str(ROOT/'voice.c'),'-lm',
                        '-o',str(DEST/'rubber-test.so')],check=True)
        cls.settings=np.array([json.loads((ROOT/'report.json').read_text())['selected']['parameters'][name]
                               for name in NAMES]+[0,.002,0,1,0,0,0])

    def renderer(self,frequency=49):
        return Renderer([{'start':0,'end':.5,'frequency':frequency}],
                        library_path=DEST/'rubber-test.so',function_name='render_rubber_voice')

    def test_extended_settings_stability_and_repeatability(self):
        rng=np.random.default_rng(8)
        for architecture in range(3):
            renderer=self.renderer(29.135)
            controls=renderer.controls(0,4)
            for trial in range(12):
                settings=self.settings.copy()
                settings[INDICES]=[rng.uniform(low,high) for low,high in BOUNDS]
                audio=renderer.render(settings,architecture,controls)
                self.assertTrue(np.all(np.isfinite(audio)))
                self.assertLess(float(np.max(abs(audio))),1.6)
                self.assertLess(float(np.max(abs(audio[-2400:]))),.01)
            repeated=renderer.render(self.settings,architecture,controls)
            self.assertTrue(np.array_equal(repeated,renderer.render(self.settings,architecture,controls)))

    def test_cutoff_controls_brightness(self):
        renderer=self.renderer()
        controls=renderer.controls(0,1)
        settings=self.settings.copy()
        settings[5]=0
        settings[3]=0
        settings[9]=1
        settings[11]=0
        settings[7]=.001
        brightness=[]
        for cutoff in (150,2500):
            settings[4]=cutoff
            audio=renderer.render(settings,0,controls)[2400:9600]
            spectrum=abs(np.fft.rfft(audio*np.hanning(len(audio))))**2
            frequency=np.fft.rfftfreq(len(audio),1/24000)
            brightness.append(spectrum[frequency>700].sum()/spectrum.sum())
        self.assertGreater(brightness[1],brightness[0]*4)

    def test_note_sequence_and_exports(self):
        report=json.loads((DEST/'report.json').read_text())
        events=json.loads((DEST/'events.json').read_text())
        expected=[31,31,31,32,29,36,37,34,24,25,22,31]
        self.assertEqual(report['note_sequence_user'],expected)
        self.assertEqual([event['midi'] for event in events[:12]],expected)
        for filename in ('rubber-bass.wav','rubber-preview.wav','mariana-then-synth.wav'):
            rate,audio=wavfile.read(DEST/filename)
            self.assertIn(rate,(24000,48000))
            self.assertLess(np.max(abs(audio.astype(np.int32))),32767)
            self.assertGreater(np.std(audio),10)
        self.assertLess(report['full_recording_loss_new'],report['full_recording_loss_previous'])

    def test_parameter_count_guard(self):
        renderer=self.renderer()
        with self.assertRaises(ValueError):
            renderer.render(self.settings[:16],0,renderer.controls(0,1))


if __name__=='__main__':
    unittest.main()
