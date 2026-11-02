import os
import tempfile
import unittest

import numpy as np

from engine import Synth
from model import ROOT, read_patch, save_patch, validate_patch
from modeld_preview import factory


class PatchVolumeTests(unittest.TestCase):
    def test_older_patch_default_validation_and_save(self):
        old=factory()['init']
        old.pop('output_gain_db',None)
        self.assertEqual(validate_patch(old)['output_gain_db'],0)
        for value in (float('nan'),float('inf'),-25,25,True,'12'):
            with self.assertRaises(ValueError): validate_patch({**old,'output_gain_db':value})
        with tempfile.TemporaryDirectory() as directory:
            patch={**old,'output_gain_db':12.5}
            path=save_patch('Volume test',patch,directory)
            self.assertEqual(read_patch(path)['output_gain_db'],12.5)
            self.assertEqual(read_patch(path)['parameters'],patch['parameters'])
        self.assertNotIn('output_gain_db',read_patch(ROOT/'baselines/bassline-v1/preset.json'))

    def test_gain_scales_waveform_without_changing_synthesis(self):
        patch=factory()['init']
        normal=Synth({**patch,'output_gain_db':0})
        boosted=Synth({**patch,'output_gain_db':12})
        try:
            for synth in (normal,boosted):
                synth.send('master',.01)
                synth.send('midi',('note_on',0,31,100))
            for _ in range(30):
                original=normal.render(256).copy()
                raised=boosted.render(256).copy()
                np.testing.assert_allclose(raised,original*10**(.6),rtol=3e-7,atol=1e-8)
            np.testing.assert_array_equal(normal.settings,boosted.settings)
            self.assertEqual(boosted.clipped,0)
        finally:
            normal.close()
            boosted.close()

    def test_live_edit_is_smoothed_and_mode_switch_resets_gain(self):
        patch=factory()['init']
        normal=Synth(patch)
        edited=Synth(patch)
        try:
            for synth in (normal,edited):
                synth.send('master',.01)
                synth.send('midi',('note_on',0,31,127))
            for _ in range(30):
                normal.render(256)
                edited.render(256)
            edited.send('output_gain_db',6.020599913279624)
            reference=normal.render(256).copy()
            changed=edited.render(256).copy()
            valid=abs(reference)>1e-5
            ratios=(changed[valid]/reference[valid])
            self.assertLess(ratios[0],1.01)
            self.assertGreater(ratios[-1],1.5)
            for _ in range(10):
                reference=normal.render(256).copy()
                changed=edited.render(256).copy()
            np.testing.assert_allclose(changed,reference*2,rtol=3e-5,atol=1e-8)
            edited.send('output_gain_db',float('nan'))
            edited.send('output_gain_db',99)
            edited.drain()
            self.assertAlmostEqual(edited.output_gain_db,6.020599913279624)
            edited.send('patch',read_patch(ROOT/'baselines/bassline-v1/preset.json'))
            edited.drain()
            self.assertEqual(edited.output_gain_db,0)
            edited.send('patch',{**patch,'output_gain_db':7.5})
            edited.drain()
            self.assertEqual(edited.output_gain_db,7.5)
        finally:
            normal.close()
            edited.close()

    def test_gui_volume_recall_and_dirty_state(self):
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtWidgets import QApplication
        from app import Window
        application=QApplication.instance() or QApplication([])
        window=Window(no_devices=True)
        try:
            self.assertFalse(window.patch_volume.isEnabled())
            patch={**factory()['init'],'output_gain_db':9.75}
            window.apply_patch(patch)
            window.tick()
            self.assertTrue(window.patch_volume.isEnabled())
            self.assertEqual(window.patch_volume.value(),9.75)
            self.assertFalse(window.dirty)
            window.patch_volume.setValue(12.5)
            window.tick()
            self.assertTrue(window.dirty)
            self.assertEqual(window.patch['output_gain_db'],12.5)
            self.assertEqual(window.synth.output_gain_db,12.5)
            window.apply_patch(read_patch(ROOT/'presets/bassline-pluck.json'))
            window.tick()
            self.assertFalse(window.patch_volume.isEnabled())
            self.assertEqual(window.patch_volume.value(),0)
            self.assertEqual(window.synth.output_gain_db,0)
        finally:
            window.dirty=False
            window.close()
            application.processEvents()


if __name__=='__main__': unittest.main(verbosity=2)
