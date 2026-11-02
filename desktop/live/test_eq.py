import os
import tempfile
import unittest
import numpy as np
from eq import DEFAULT, Equalizer
from model import ROOT, read_patch, save_patch, validate_patch

class EQTests(unittest.TestCase):
    def process(self, settings, source, block=256):
        eq=Equalizer(48000)
        try:
            eq.configure({**DEFAULT,**settings})
            result=source.copy()
            for start in range(0,len(result),block):eq.process(result[start:start+block])
            return result
        finally:eq.close()

    def test_flat_bypass_and_blocks(self):
        source=np.random.default_rng(3).normal(0,.1,24000).astype(np.float32)
        for settings in ({},{'enabled':True},{'low_db':12,'mid_db':-12,'high_db':12}):
            np.testing.assert_array_equal(source,self.process(settings,source))
        settings={'enabled':True,'low_db':5,'mid_db':-7,'high_db':3}
        np.testing.assert_array_equal(self.process(settings,source,64),self.process(settings,source,1024))

    def test_band_response(self):
        for key,hz,expected in [('low_db',5,6),('mid_db',700,6),('high_db',18000,6),('mid_db',5,0)]:
            signal=(.01*np.sin(2*np.pi*hz*np.arange(96000)/48000)).astype(np.float32)
            out=self.process({'enabled':True,key:6},signal)
            db=20*np.log10(np.linalg.norm(out[48000:])/np.linalg.norm(signal[48000:]))
            self.assertAlmostEqual(float(db),expected,delta=.08)

    def test_save_defaults_and_validation(self):
        patch=read_patch(ROOT/'presets/bassline-pluck.json')
        self.assertEqual(patch['eq'],DEFAULT)
        patch['eq']={**DEFAULT,'enabled':True,'mid_db':-3.5,'mid_q':1.2}
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(read_patch(save_patch('EQ test',patch,directory))['eq'],patch['eq'])
        for key,value in [('enabled',1),('low_hz',0),('mid_db',float('nan')),('mid_q',9)]:
            with self.assertRaises(ValueError):validate_patch({**patch,'eq':{**DEFAULT,key:value}})

    def test_live_changes_remain_finite(self):
        eq=Equalizer(48000)
        try:
            for i in range(300):
                eq.configure({**DEFAULT,'enabled':bool(i%3),'low_db':12 if i%2 else -12,
                    'mid_db':12,'mid_hz':80 if i%2 else 6000,'mid_q':4,
                    'high_db':-12 if i%2 else 12})
                audio=np.full(256,.01,np.float32)
                eq.process(audio)
                self.assertTrue(np.isfinite(audio).all())
                self.assertLess(float(abs(audio).max()),1)
        finally:eq.close()

    def test_gui_three_knobs_recall_and_flat(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication
        from app import Window
        application=QApplication.instance() or QApplication([])
        window=Window(no_devices=True)
        try:
            window.eq_controls['mid_db'].spin.setValue(-4)
            window.synth.drain()
            self.assertEqual(window.synth.eq.settings['mid_db'],-4)
            self.assertTrue(window.dirty)
            window.apply_patch(read_patch(ROOT/'presets/Model-D-18dB-Finalist-2.json'))
            self.assertEqual(len(window.eq_controls),3)
            self.assertEqual(window.eq_controls['mid_db'].spin.value(),0)
            self.assertFalse(window.dirty)
            window.eq_controls['low_db'].dial.setValue(60)
            self.assertEqual(window.patch['eq']['low_db'],6)
            self.assertTrue(window.patch['eq']['enabled'])
            window.eq_controls['low_db'].spin.setValue(0)
            self.assertEqual(window.patch['eq'],DEFAULT)
            self.assertEqual(window.eq_curve.points,[0]*64)
        finally:
            window.dirty=False
            window.close()
            application.processEvents()

    def test_visualizer_matches_audio_response(self):
        from eq_view import response_db
        settings={**DEFAULT,'enabled':True,'low_db':5,'mid_db':-8,'high_db':3}
        curve=response_db(settings)
        for i in (8,32,52):
            hz=20*1000**(i/63)
            source=(.01*np.sin(2*np.pi*hz*np.arange(96000)/48000)).astype(np.float32)
            out=self.process(settings,source)
            measured=20*np.log10(np.linalg.norm(out[48000:])/np.linalg.norm(source[48000:]))
            self.assertAlmostEqual(curve[i],float(measured),delta=.03)
