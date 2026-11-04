import os
import json
import subprocess
import unittest
import tempfile
import numpy as np
from model import ROOT, read_patch, save_patch
from modeld_preview import render
from hour_search import Voice, controls_for

class FinalistTests(unittest.TestCase):
    def test_legacy_finalists_import_as_24db_and_match_frozen_24db_path(self):
        source=ROOT/'desktop/live/fixtures/modeld-before-cache.c'
        with tempfile.TemporaryDirectory() as directory:
            from pathlib import Path
            library=Path(directory)/'reference.so'
            subprocess.run(['gcc','-O3','-shared','-fPIC',str(source),'-lm','-o',str(library)],check=True)
            voice=Voice(library,48000)
            events=json.loads((ROOT/'baselines/bassline-v1/events.json').read_text())
            try:
                for rank in (2,3):
                    patch=read_patch(ROOT/f'presets/Model-D-18dB-Finalist-{rank}.json')
                    expected=voice.render(patch,controls_for(events,48000),513)
                    actual=render(patch,apply_output_gain=False)
                    np.testing.assert_array_equal(actual,expected)
                    path=save_patch('roundtrip',patch,directory)
                    self.assertEqual(read_patch(path)['architecture'],'modeld')
                    self.assertEqual(read_patch(path)['parameters'],patch['parameters'])
            finally:voice.voice.close()

    def test_gui_loads_filter_label_gain_and_maps(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication
        from app import Window
        app=QApplication.instance() or QApplication([])
        window=Window(no_devices=True)
        try:
            patch=read_patch(ROOT/'presets/Model-D-18dB-Finalist-2.json')
            window.apply_patch(patch);window.tick()
            self.assertEqual(window.synth.architecture,3)
            self.assertIn('24 dB',window.architecture_label.text())
            self.assertNotIn('filter_mode',window.knobs)
            self.assertTrue(window.patch_volume.isEnabled())
            self.assertEqual(window.synth.output_gain_db,patch['output_gain_db'])
            window.begin_mapping('cutoff_hz');window.synth.send('midi',('control_change',0,20,40));window.tick()
            window.apply_patch(read_patch(ROOT/'presets/model-d-bass.json'));window.tick()
            self.assertEqual(window.synth.architecture,3)
            self.assertNotIn('filter_mode',window.knobs)
            self.assertEqual(window.mappings,{'0:20':'cutoff_hz'})
        finally:
            window.dirty=False;window.close();app.processEvents()
