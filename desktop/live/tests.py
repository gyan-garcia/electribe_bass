import ctypes
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time
import unittest
from unittest import mock
import wave

import numpy as np

from model import ROOT,NAMES,read_patch,save_patch,validate_patch
from engine import NativeVoice,Synth,HERE
from audio_io import Audio,Recorder

BASELINE=ROOT/'baselines/bassline-v1'


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.patch=read_patch(BASELINE/'preset.json')
        self.synth=Synth(self.patch)

    def tearDown(self):
        self.synth.close()

    def test_live_blocks_match_offline_source_exactly(self):
        reference=HERE/'build/reference.so'
        subprocess.run(['gcc','-O3','-shared','-fPIC',str(BASELINE/'voice.c'),'-lm','-o',str(reference)],check=True)
        library=ctypes.CDLL(str(reference))
        pointer=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
        settings_type=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        function=library.render_rubber_voice
        function.argtypes=[pointer]*6+[ctypes.c_int,ctypes.c_int,settings_type,ctypes.c_int]
        function.restype=None
        frames=16384
        pitch=np.full(frames,49,dtype=np.float32)
        pitch[8000:]=65.406391
        gate=np.ones(frames,dtype=np.float32)
        gate[12000:]=0
        trigger=np.zeros(frames,dtype=np.float32)
        trigger[[0,8000]]=1
        controls=[pitch,gate,trigger,np.ones(frames,dtype=np.float32),
                  np.full(frames,self.synth.settings[11],dtype=np.float32)]
        expected=np.zeros(frames,dtype=np.float32)
        function(expected,*controls,frames,48000,self.synth.settings,0)
        for blocksize in (1,7,128,256,513,4096):
            self.synth.voice.reset()
            actual=np.zeros_like(expected)
            for start in range(0,frames,blocksize):
                stop=min(frames,start+blocksize)
                self.synth.voice.process(actual[start:stop],[value[start:stop] for value in controls],self.synth.settings)
            self.assertTrue(np.array_equal(expected,actual),blocksize)

    def test_full_approved_render_preserved(self):
        events=json.loads((BASELINE/'events.json').read_text())
        frames=round(events[-1]['end']*48000)
        controls=[np.full(frames,49,dtype=np.float32),np.zeros(frames,dtype=np.float32),
                  np.zeros(frames,dtype=np.float32),np.ones(frames,dtype=np.float32),
                  np.full(frames,self.synth.settings[11],dtype=np.float32)]
        for event in events:
            left=round(event['start']*48000)
            right=round(event['end']*48000)
            controls[0][left:right]=event['frequency']
            controls[1][left:max(left,right-1200)]=1
            controls[2][left]=1
        output=np.zeros(frames,dtype=np.float32)
        for start in range(0,frames,256):
            stop=min(frames,start+256)
            self.synth.voice.process(output[start:stop],[value[start:stop] for value in controls],self.synth.settings)
        gain=min(1,.89/float(np.max(abs(output))))
        integer=np.round(np.clip(output*gain,-.99,.99)*32767).astype('<i2')
        with wave.open(str(BASELINE/'bassline-48k.wav'),'rb') as recording:
            expected=np.frombuffer(recording.readframes(recording.getnframes()),dtype='<i2')
        self.assertTrue(np.array_equal(expected,integer))

    def test_note_priority_sustain_and_zero_velocity(self):
        for event in [('note_on',0,31,90),('note_on',0,36,100),('note_off',0,36,0)]:
            self.synth.send('midi',event)
        self.synth.render(256)
        self.assertEqual(self.synth.notes.active,(0,31,90))
        self.synth.send('midi',('control_change',0,64,127))
        self.synth.send('midi',('note_on',0,31,0))
        self.synth.render(256)
        self.assertIsNotNone(self.synth.notes.active)
        self.synth.send('midi',('control_change',0,64,0))
        self.synth.render(256)
        self.assertIsNone(self.synth.notes.active)

    def test_pitch_bend_legato_and_panic(self):
        self.synth.send('midi',('note_on',0,31,127))
        self.synth.render(256)
        self.synth.send('legato',True)
        self.synth.send('midi',('note_on',0,36,100))
        self.synth.render(256)
        self.assertEqual(self.synth.controls[2][0],0)
        self.synth.send('midi',('pitchwheel',0,4096,0))
        self.synth.render(256)
        self.assertAlmostEqual(self.synth.frequency,440*2**((37-69)/12))
        self.synth.send('panic')
        self.assertTrue(np.all(self.synth.render(256)==0))

    def test_cc_learn_and_channel_filter(self):
        self.synth.send('learn','cutoff_hz')
        self.synth.send('midi',('control_change',0,20,127))
        self.synth.render(256)
        self.assertEqual(self.synth.mapping,{'0:20':'cutoff_hz'})
        self.assertAlmostEqual(self.synth.settings[NAMES.index('cutoff_hz')],10000)
        self.synth.send('channel',1)
        self.synth.send('midi',('note_on',0,31,127))
        self.synth.render(256)
        self.assertIsNone(self.synth.notes.active)

    def test_queue_overflow_recovers_silently(self):
        for _ in range(2050): self.synth.send('midi',('note_on',0,31,127))
        self.assertTrue(np.all(self.synth.render(256)==0))
        self.assertGreater(self.synth.dropped,0)

    def test_patch_save_load_and_immutable_sources(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            first=save_patch('Bass Test',self.patch,directory)
            second=save_patch('Bass Test',self.patch,directory)
            self.assertNotEqual(first,second)
            self.assertEqual(read_patch(first)['parameters'],self.patch['parameters'])
        bad={**self.patch,'parameters':{**self.patch['parameters'],'cutoff_hz':float('nan')}}
        with self.assertRaises(ValueError): validate_patch(bad)
        for line in (BASELINE/'SHA256SUMS').read_text().splitlines():
            digest,name=line.split(maxsplit=1)
            self.assertEqual(hashlib.sha256((BASELINE/name).read_bytes()).hexdigest(),digest)

    def test_callback_and_recording(self):
        audio=Audio(self.synth)
        output=np.zeros((256,2),dtype=np.float32)
        self.synth.send('midi',('note_on',0,31,127))
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            recorder=Recorder(Path(directory)/'test.wav',48000)
            audio.recorder=recorder
            for _ in range(16): audio.callback(output,256,None,False)
            audio.stop_recording()
            self.assertIsNone(recorder.error)
            with wave.open(str(recorder.path),'rb') as recording:
                self.assertEqual(recording.getnframes(),16*256)
                self.assertEqual(recording.getnchannels(),2)
                samples=np.frombuffer(recording.readframes(4096),dtype='<i2').reshape(-1,2)
                self.assertGreater(np.std(samples),1)
                self.assertTrue(np.array_equal(samples[:,0],samples[:,1]))
            with self.assertRaises(FileExistsError): Recorder(recorder.path,48000)
        self.assertIsNone(audio.error)

    def test_loaded_controls_do_not_round_the_preset(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from app import QApplication,Window
        application=QApplication.instance() or QApplication([])
        window=Window(no_devices=True)
        try:
            self.assertEqual(window.patch['parameters'],self.patch['parameters'])
            window.apply_patch(read_patch(ROOT/'presets/bassline-pluck.json'))
            window.synth.drain()
            self.assertAlmostEqual(window.synth.settings[NAMES.index('filter_attack_s')],.001)
            self.assertFalse(window.dirty)
        finally:
            window.close()
        application.processEvents()

    def test_native_callback_budget_report(self):
        self.synth.send('midi',('note_on',0,31,100))
        elapsed=[]
        for _ in range(300):
            start=time.perf_counter()
            self.synth.render(256)
            elapsed.append((time.perf_counter()-start)*1000)
        result={'buffer_frames':256,'rate':48000,'buffer_budget_ms':256/48,
                'median_render_ms':statistics.median(elapsed),'p99_render_ms':float(np.percentile(elapsed,99)),
                'note':'Native desktop benchmark only, not end-to-end latency or Blackfin timing.'}
        (HERE/'outputs').mkdir(exist_ok=True)
        (HERE/'outputs/callback-benchmark.json').write_text(json.dumps(result,indent=2))
        self.assertTrue(np.isfinite(result['p99_render_ms']))

    def test_bluetooth_listed_without_portaudio_pulse_device(self):
        from audio_io import outputs
        devices=[{'name':'Built-in hardware','max_output_channels':2}]
        response=mock.Mock(stdout=json.dumps([{'name':'bluez_output.test','description':'Bluetooth speaker'}]))
        fake=mock.Mock(query_devices=mock.Mock(return_value=devices))
        with mock.patch.dict('sys.modules',{'sounddevice':fake}),mock.patch('audio_io.subprocess.run',return_value=response):
            choices=outputs()
        bluetooth=next(choice for choice in choices if choice['bluetooth'])
        self.assertEqual(bluetooth['backend'],'pulse-simple')
        self.assertEqual(bluetooth['sink'],'bluez_output.test')
        self.assertIn('Bluetooth',bluetooth['label'])

    def test_bluetooth_backend_is_selected_and_stopped(self):
        audio=Audio(self.synth)
        stream=mock.Mock()
        with mock.patch('pulse_output.PulseStream',return_value=stream) as factory:
            audio.start({'backend':'pulse-simple','sink':'bluez_output.test'},256)
            factory.assert_called_once()
            stream.start.assert_called_once()
            self.assertIs(audio.stream,stream)
            audio.stop()
            stream.stop.assert_called_once()
            stream.close.assert_called_once()

    def test_mapping_is_one_to_one_and_can_be_cancelled(self):
        self.synth.send('learn','cutoff_hz')
        self.synth.send('midi',('control_change',0,20,80))
        self.synth.drain()
        self.synth.send('learn','cutoff_hz')
        self.synth.send('midi',('control_change',0,21,80))
        self.synth.drain()
        self.assertEqual(self.synth.mapping,{'0:21':'cutoff_hz'})
        self.synth.send('learn','resonance')
        self.synth.send('midi',('control_change',0,21,90))
        self.synth.drain()
        self.assertEqual(self.synth.mapping,{'0:21':'resonance'})
        self.synth.send('learn','attack_s')
        self.synth.send('midi',('control_change',0,64,127))
        self.synth.drain()
        self.assertEqual(self.synth.learn_target,'attack_s')
        self.synth.send('learn',None)
        self.synth.send('midi',('control_change',0,22,80))
        self.synth.drain()
        self.assertNotIn('0:22',self.synth.mapping)
        self.synth.send('unmap','resonance')
        self.synth.drain()
        self.assertEqual(self.synth.mapping,{})

    def test_right_click_waiting_assignment_and_session_reset(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from app import QApplication,Window,Qt
        from PySide6.QtTest import QTest
        application=QApplication.instance() or QApplication([])
        original_read=Path.read_text
        def reject_preferences(path,*args,**kwargs):
            if path.name=='preferences.json':
                raise AssertionError('Session mappings must not be restored from disk')
            return original_read(path,*args,**kwargs)
        with mock.patch.object(Path,'read_text',reject_preferences):
            window=Window(no_devices=True)
        try:
            knob=window.knobs['cutoff_hz']
            before=window.patch['parameters']['cutoff_hz']
            QTest.mouseClick(knob.dial,Qt.MouseButton.RightButton)
            self.assertTrue(knob.menu.isVisible())
            self.assertEqual(knob.map_action.text(),'Map to MIDI')
            self.assertEqual(window.patch['parameters']['cutoff_hz'],before)
            with mock.patch.object(Path,'write_text',side_effect=AssertionError('Mapping must not be written to disk')):
                knob.map_action.trigger()
                knob.menu.hide()
                window.tick()
                self.assertEqual(window.waiting_for,'cutoff_hz')
                self.assertTrue(knob.property('midiWaiting'))
                self.assertIn('Waiting for MIDI',knob.mapping_label.text())
                window.synth.send('midi',('control_change',0,20,90))
                window.tick()
                self.assertIsNone(window.waiting_for)
                self.assertEqual(window.mappings,{'0:20':'cutoff_hz'})
                self.assertIn('CC 20',knob.mapping_label.text())
                self.assertFalse(knob.property('midiWaiting'))
                window.apply_patch(read_patch(ROOT/'presets/bassline-pluck.json'))
                window.tick()
                self.assertEqual(window.mappings,{'0:20':'cutoff_hz'})
                window.begin_mapping('resonance')
                window.tick()
                window.cancel_mapping()
                window.tick()
                self.assertIsNone(window.synth.learn_target)
                window.remove_mapping('cutoff_hz')
                window.tick()
                self.assertEqual(window.mappings,{})
                window.begin_mapping('resonance')
                window.tick()
                window.synth.send('midi',('control_change',0,21,40))
                window.tick()
                self.assertEqual(window.mappings,{'0:21':'resonance'})
        finally:
            window.dirty=False
            window.close()
        replacement=Window(no_devices=True)
        try:
            replacement.tick()
            self.assertEqual(replacement.mappings,{})
            self.assertEqual(replacement.synth.mapping,{})
            self.assertIsNone(replacement.waiting_for)
        finally:
            replacement.close()
        application.processEvents()


if __name__=='__main__':
    unittest.main(verbosity=2)
