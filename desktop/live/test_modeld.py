import ctypes
import json
import os
import tempfile
import time
import unittest

import numpy as np

from engine import NativeVoice, Synth
from model import ROOT, MODEL_D_NAMES, MODEL_D_PARAMETERS, patch_paths, read_patch, save_patch, validate_patch
from modeld_preview import factory


class ModelDTests(unittest.TestCase):
    def setUp(self):
        self.patch=factory()['init']

    def audio(self,changes=None,frames=12000,block=256):
        patch={**self.patch,'parameters':{**self.patch['parameters'],**(changes or {})}}
        values=np.array([patch['parameters'][name] for name in MODEL_D_NAMES],dtype=np.float64)
        controls=[np.full(frames,98,dtype=np.float32),np.ones(frames,dtype=np.float32),
                  np.zeros(frames,dtype=np.float32),np.ones(frames,dtype=np.float32),
                  np.full(frames,patch['parameters']['resonance'],dtype=np.float32)]
        controls[2][0]=1
        voice=NativeVoice(48000,'modeld')
        output=np.zeros(frames,dtype=np.float32)
        try:
            for start in range(0,frames,block):
                stop=min(frames,start+block)
                voice.process(output[start:stop],[control[start:stop] for control in controls],values,3)
        finally: voice.close()
        self.assertTrue(np.isfinite(output).all())
        return output

    def test_schema_and_exclusive_save(self):
        voice=NativeVoice(48000,'modeld')
        try:
            self.assertEqual(voice.parameter_count,47)
            voice.library.synth_state_size.restype=ctypes.c_int
            self.assertLess(voice.library.synth_state_size(),512)
        finally: voice.close()
        with tempfile.TemporaryDirectory() as directory:
            first=save_patch('Model D test',self.patch,directory)
            second=save_patch('Model D test',self.patch,directory)
            self.assertNotEqual(first,second)
            self.assertEqual(read_patch(first),self.patch|{'name':'Model D test'})
        bad={**self.patch,'parameters':{**self.patch['parameters'],'osc1_wave':1.5}}
        with self.assertRaises(ValueError): validate_patch(bad)

    def test_active_patches_discovered_and_valid(self):
        patches=[read_patch(path) for path in patch_paths()]
        self.assertTrue({'BOSS 03','Moog Res','TL - Broken Radio','UK50 29 Jungle - Concrete Reese'}.issubset({p['name'] for p in patches}))
        self.assertNotIn('Model D Init',{p['name'] for p in patches})
        for patch in patches: self.assertEqual(validate_patch(patch),patch)

    def test_blocks_are_identical(self):
        settings={'filter_env_octaves':4,'filter_attack_s':.03,'filter_decay_s':.12,
                  'resonance':.8,'osc2_level':.6,'mod_amount':.2,
                  'filter_mod_enabled':1,'pitch_mod_enabled':1}
        expected=self.audio(settings,frames=8192,block=8192)
        for block in (1,7,128,513):
            np.testing.assert_array_equal(expected,self.audio(settings,frames=8192,block=block))

    def test_independent_oscillator_ranges_and_waveforms(self):
        for oscillator in (1,2,3):
            changes={f'osc{i}_level':float(i==oscillator) for i in (1,2,3)}
            spectrum=np.abs(np.fft.rfft(self.audio(changes,frames=48000)[4800:]))
            fundamental=np.argmax(spectrum)*48000/43200
            self.assertAlmostEqual(fundamental,98,delta=1.2)
            changes[f'osc{oscillator}_octave']=1
            spectrum=np.abs(np.fft.rfft(self.audio(changes,frames=48000)[4800:]))
            self.assertAlmostEqual(np.argmax(spectrum)*48000/43200,196,delta=1.2)
        waves=[self.audio({'osc1_wave':shape}) for shape in range(6)]
        for left in range(6):
            for right in range(left): self.assertGreater(np.mean(abs(waves[left]-waves[right])),.01)

    def test_filter_is_fixed_lowpass_and_noise_modulation_change_audio(self):
        low=self.audio({'cutoff_hz':200,'resonance':.2})
        high=self.audio({'cutoff_hz':200,'resonance':.2,'filter_mode':1})
        np.testing.assert_array_equal(low,high)
        white=self.audio({'osc1_level':0,'noise_level':1})
        pink=self.audio({'osc1_level':0,'noise_level':1,'noise_color':1})
        self.assertGreater(np.std(white),.02)
        self.assertGreater(np.mean(abs(white-pink)),.01)
        plain=self.audio()
        for changes in ({'mod_amount':1,'pitch_mod_enabled':1},
                        {'mod_amount':1,'filter_mod_enabled':1,'cutoff_hz':500},
                        {'feedback_level':.7,'resonance':.6}):
            self.assertGreater(np.mean(abs(plain-self.audio(changes))),.01)

    def test_parameter_extremes_remain_finite(self):
        random=np.random.default_rng(20261101)
        for trial in range(60):
            changes={spec.name:spec.from_position(random.uniform(0,1000)) for spec in MODEL_D_PARAMETERS}
            changes['attack_s']=0
            changes['filter_attack_s']=0
            result=self.audio(changes,frames=8192)
            self.assertLess(np.max(abs(result)),3)

    def test_self_oscillation_without_mixer_input(self):
        result=self.audio({'osc1_level':0,'resonance':1.1,'cutoff_hz':500},frames=96000)
        self.assertGreater(np.std(result[-24000:]),.01)

    def test_mode_switch_mappings_and_modwheel(self):
        synth=Synth(read_patch(ROOT/'baselines/bassline-v1/preset.json'))
        try:
            synth.send('learn','cutoff_hz')
            synth.send('midi',('control_change',0,20,80))
            synth.drain()
            synth.send('patch',self.patch)
            synth.send('midi',('control_change',0,1,127))
            synth.drain()
            self.assertEqual(synth.mapping,{})
            self.assertEqual(synth.settings[synth.indices['mod_amount']],1)
            synth.send('learn','osc1_wave')
            synth.send('midi',('control_change',0,20,80))
            synth.send('midi',('note_on',0,31,100))
            synth.render(256)
            self.assertEqual(synth.mapping,{'0:20':'osc1_wave'})
            self.assertEqual(synth.settings[synth.indices['osc1_wave']],3)
            synth.send('patch',read_patch(ROOT/'presets/bassline-pluck.json'))
            synth.render(128)
            self.assertEqual(synth.mapping,{'0:20':'cutoff_hz'})
            self.assertIsNone(synth.notes.active)
            synth.send('patch',self.patch)
            synth.drain()
            self.assertEqual(synth.mapping,{'0:20':'osc1_wave'})
        finally: synth.close()

    def test_gui_switch_discrete_mapping_and_stale_notifications(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication
        from app import Window
        application=QApplication.instance() or QApplication([])
        window=Window(no_devices=True)
        try:
            # Leave a legacy parameter event pending when replacing its controls.
            window.synth.send('learn','pulse_blend')
            window.synth.send('midi',('control_change',0,20,80))
            window.synth.drain()
            window.apply_patch(self.patch)
            window.tick()
            self.assertEqual(len(window.knobs),46)
            self.assertEqual(window.tabs.count(),9)
            self.assertNotIn('pulse_blend',window.patch['parameters'])
            window.knobs['osc1_wave'].spin.setCurrentIndex(4)
            window.tick()
            self.assertEqual(window.patch['parameters']['osc1_wave'],4)
            window.begin_mapping('osc2_octave')
            window.tick()
            window.synth.send('midi',('control_change',0,21,127))
            window.tick()
            self.assertEqual(window.patch['parameters']['osc2_octave'],2)
            window.apply_patch(read_patch(ROOT/'presets/bassline-pluck.json'))
            window.tick()
            self.assertEqual(len(window.knobs),23)
            self.assertEqual(window.mappings,{'0:20':'pulse_blend'})
        finally:
            window.dirty=False
            window.close()
            application.processEvents()


if __name__=='__main__': unittest.main(verbosity=2)
