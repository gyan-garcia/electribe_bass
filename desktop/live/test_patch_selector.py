"""Keep the displayed patch synchronized across filter-layout rebuilds."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from app import Window
from model import ROOT,read_patch,save_patch
import tempfile


class PatchSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.window=Window(no_devices=True)
        self.window.mode_selector.setCurrentIndex(self.window.mode_selector.findData('modeld'))
        self.window.change_mode();self.window.tick()

    def tearDown(self):
        self.window.dirty=False;self.window.close();self.app.processEvents()

    def select(self,filename):
        path=ROOT/'presets/user'/filename
        index=self.window.patch_selector.findData(str(path))
        self.assertGreaterEqual(index,0)
        self.window.patch_selector.setCurrentIndex(index)
        self.window.patch_selector.activated.emit(index)
        self.window.tick()
        return path

    def assert_loaded(self,path):
        expected=read_patch(path)
        self.assertEqual(self.window.current_path,path)
        self.assertEqual(self.window.patch_selector.currentData(),str(path))
        self.assertEqual(self.window.patch_selector.currentText(),expected['name'])
        self.assertEqual(self.window.patch,expected)
        self.assertEqual(self.window.synth.patch,expected)

    def test_switching_filter_variants_keeps_requested_selection(self):
        for _ in range(2):
            for filename in ('TL-Broken-Radio.json','Moog-Res.json','BOSS-03.json',
                             'UK-Res-Bass.json','TL-Outlaw.json'):
                self.assert_loaded(self.select(filename))

    def test_refresh_keeps_loaded_selection(self):
        path=self.select('TL-Destitution.json')
        self.window._patches()
        self.assert_loaded(path)

    def test_cancel_keeps_previous_patch(self):
        previous=self.select('UK-Res-Bass.json')
        with patch.object(self.window,'_confirm_discard',return_value=False):
            self.select('TL-Broken-Radio.json')
        self.assert_loaded(previous)

    def test_failed_load_keeps_previous_patch(self):
        previous=self.select('UK-Res-Bass.json')
        with patch('app.read_patch',side_effect=OSError('Unavailable patch')),patch('app.QMessageBox.warning'):
            self.select('TL-Broken-Radio.json')
        self.assert_loaded(previous)

    def test_all_active_patches_use_fixed_24db_and_no_filter_selectors(self):
        from model import patch_paths
        for path in patch_paths():
            self.select(path.name)
            self.assertEqual(self.window.patch['architecture'],'modeld')
            self.assertEqual(self.window.synth.architecture,3)
            self.assertNotIn('filter_mode',self.window.knobs)
            self.assertNotIn('filter_mode',self.window.specs)
            self.assertFalse(hasattr(self.window,'filter_slope'))
            self.assertEqual(self.window.architecture_label.text(),'24 dB/octave low-pass')

    def test_legacy_import_canonicalizes_and_save_stays_lowpass(self):
        legacy=read_patch(ROOT/'presets/user/UK-Res-Bass.json')
        legacy['architecture']='modeld18';legacy['parameters']['filter_mode']=1
        from model import validate_patch
        migrated=validate_patch(legacy)
        self.assertEqual(migrated['architecture'],'modeld')
        self.assertEqual(migrated['parameters']['filter_mode'],0)
        with tempfile.TemporaryDirectory() as directory:
            path=save_patch('Fixed low-pass',migrated,directory)
            self.assertEqual(read_patch(path),{**migrated,'name':'Fixed low-pass'})

    def test_reserved_filter_mode_cannot_be_midi_mapped_or_changed(self):
        self.select('UK-Res-Bass.json')
        self.window.synth.send('learn','filter_mode');self.window.tick()
        self.assertIsNone(self.window.synth.learn_target)
        self.window.synth.send('parameter','filter_mode',1);self.window.tick()
        self.assertEqual(self.window.synth.settings[self.window.synth.indices['filter_mode']],0)


if __name__=='__main__':unittest.main()
