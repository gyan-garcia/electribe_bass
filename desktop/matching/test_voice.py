import json
import subprocess
import unittest

import numpy as np
from scipy.io import wavfile

from analyze import ROOT
from fit import BASE, BOUNDS, INDICES, Renderer


class VoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(['gcc','-O3','-fPIC','-shared',str(ROOT/'voice.c'),'-lm',
                        '-o',str(ROOT/'voice-test.so')],check=True)

    def test_pitch_and_repeatability(self):
        for midi in (22,24,25,29,31,32,34,36,37,43,44,41):
            frequency=440*2**((midi-69)/12)
            renderer=Renderer([{'start':0,'end':2,'frequency':frequency}],library_path=ROOT/'voice-test.so')
            controls=renderer.controls(0,2)
            settings=BASE.copy()
            settings[[0,2,3,4,5,7,9,11,12,14,15]]=[0,0,0,6000,0,.001,1,0,.5,.0001,.5]
            audio=renderer.render(settings,0,controls)
            repeated=renderer.render(settings,0,controls)
            self.assertTrue(np.array_equal(audio,repeated))
            spectrum=abs(np.fft.rfft(audio[12000:36000]*np.hanning(24000)))
            measured=float(np.argmax(spectrum))
            self.assertLess(abs(measured-frequency),.6)

    def test_silence_release_and_parameter_bounds(self):
        generator=np.random.default_rng(42)
        renderer=Renderer([{'start':0,'end':.25,'frequency':49}],library_path=ROOT/'voice-test.so')
        controls=renderer.controls(0,1)
        for architecture in range(3):
            for trial in range(16):
                settings=BASE.copy()
                settings[INDICES]=[generator.uniform(low,high) for low,high in BOUNDS]
                audio=renderer.render(settings,architecture,controls)
                self.assertTrue(np.all(np.isfinite(audio)))
                self.assertLess(float(np.max(abs(audio))),1.5)
                self.assertLess(float(np.max(abs(audio[-2400:]))),.03)
            silent=tuple(np.zeros(2400,dtype=np.float32) for _ in range(3))
            silent=(np.full(2400,49,dtype=np.float32),silent[1],silent[2])
            self.assertTrue(np.all(renderer.render(BASE,architecture,silent)==0))

    def test_saved_candidates(self):
        report=json.loads((ROOT/'report.json').read_text())
        for candidate in report['architectures']:
            self.assertLessEqual(candidate['training_loss'],candidate['baseline_training_loss'])
        for name in ('baseline','fitted-static','fitted-automated'):
            rate,audio=wavfile.read(ROOT/'outputs'/f'{name}.wav')
            self.assertEqual((rate,len(audio)),(48000,2592000))
            self.assertGreater(float(np.std(audio)),10)
            self.assertLess(int(np.max(abs(audio.astype(np.int32)))),32767)


if __name__=='__main__':
    unittest.main()
