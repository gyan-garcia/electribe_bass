import os
import tempfile
import unittest
import numpy as np
from reverb import Reverb, DEFAULT
from model import ROOT, read_patch, save_patch, validate_patch

class ReverbTests(unittest.TestCase):
    def render(self,mix=1,decay=.6,block=256,source=None,rate=48000):
        audio=np.zeros(rate*4,np.float32) if source is None else source.copy()
        if source is None:audio[0]=1
        room=Reverb(rate)
        try:
            room.configure({'mix':mix,'decay':decay})
            for start in range(0,len(audio),block):room.process(audio[start:start+block])
            return audio
        finally:room.close()

    def test_dry_exact_and_block_invariance(self):
        source=np.random.default_rng(2).normal(0,.1,48000).astype(np.float32)
        np.testing.assert_array_equal(source,self.render(mix=0,source=source))
        np.testing.assert_array_equal(self.render(block=64),self.render(block=1024))

    def test_tail_decay_and_reset(self):
        short=self.render(decay=.2);long=self.render(decay=2)
        self.assertEqual(float(abs(long[:1400]).max()),0)
        self.assertGreater(float(np.linalg.norm(long[12000:48000])),float(np.linalg.norm(short[12000:48000]))*10)
        self.assertLess(float(np.linalg.norm(long[-24000:])),float(np.linalg.norm(long[24000:48000]))*.1)
        room=Reverb(48000)
        try:
            room.configure({'mix':1,'decay':2.5})
            signal=np.ones(256,np.float32);room.process(signal)
            room.reset();silence=np.zeros(48000,np.float32);room.process(silence)
            self.assertFalse(silence.any())
            for i in range(200):
                room.configure({'mix':i%2,'decay':.15 if i%2 else 2.5})
                signal=np.full(256,.1,np.float32);room.process(signal)
                self.assertTrue(np.isfinite(signal).all())
                self.assertLess(float(abs(signal).max()),1)
        finally:room.close()

    def test_save_validation_and_ui(self):
        patch=read_patch(ROOT/'presets/bassline-pluck.json')
        self.assertEqual(patch['reverb'],DEFAULT)
        for value in (-1,2,float('nan'),True):
            with self.assertRaises(ValueError):validate_patch({**patch,'reverb':{'mix':value,'decay':.6}})
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication
        from app import Window
        application=QApplication.instance() or QApplication([])
        window=Window(no_devices=True)
        try:
            window.reverb_controls['mix'].spin.setValue(25)
            window.reverb_controls['decay'].spin.setValue(1.2)
            window.synth.drain()
            self.assertEqual(window.synth.reverb.settings,{'mix':.25,'decay':1.2})
            with tempfile.TemporaryDirectory() as directory:
                saved=read_patch(save_patch('Room test',window.patch,directory))
                self.assertEqual(saved['reverb'],{'mix':.25,'decay':1.2})
            window.apply_patch(read_patch(ROOT/'presets/Model-D-18dB-Finalist-2.json'))
            window.synth.drain()
            self.assertEqual(window.synth.reverb.settings,DEFAULT)
            self.assertEqual(window.reverb_controls['mix'].spin.value(),0)
            window.apply_patch(saved)
            self.assertEqual(window.reverb_controls['mix'].spin.value(),25)
        finally:
            window.dirty=False;window.close();application.processEvents()
