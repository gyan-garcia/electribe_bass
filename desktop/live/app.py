import argparse
from datetime import datetime
from pathlib import Path
import queue
import sys
from zoneinfo import ZoneInfo

from PySide6.QtCore import Qt, QEvent, QSignalBlocker, QTimer
from PySide6.QtWidgets import (QApplication,QCheckBox,QComboBox,QDial,QDoubleSpinBox,
    QFileDialog,QGridLayout,QHBoxLayout,QInputDialog,QLabel,QMainWindow,QMessageBox,
    QMenu,QProgressBar,QPushButton,QScrollArea,QSlider,QTabWidget,QVBoxLayout,QWidget)

from model import ROOT, PARAMETERS, SPECS, engine_key, parameters_for, specs_for, patch_paths, read_patch, save_patch
from engine import Synth
from audio_io import Audio, Midi, Recorder, midi_backend, outputs

HERE=Path(__file__).resolve().parent


class Knob(QWidget):
    def __init__(self,spec,value,changed,selected,map_requested,cancel_requested,unmap_requested):
        super().__init__()
        self.spec=spec
        self.changed=changed
        self.selected=selected
        self.setObjectName('mappingCard')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(14,8,14,8)
        label=QLabel(spec.label)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.dial=QDial()
        self.dial.setRange(0,1000)
        self.dial.setNotchesVisible(True)
        self.dial.setFixedSize(92,92)
        layout.addWidget(self.dial,alignment=Qt.AlignmentFlag.AlignCenter)
        if spec.choices:
            self.spin=QComboBox()
            self.spin.addItems(spec.choices)
        else:
            self.spin=QDoubleSpinBox()
            self.spin.setRange(spec.minimum*spec.multiplier,spec.maximum*spec.multiplier)
            self.spin.setDecimals(3 if spec.multiplier==1000 else 4)
            self.spin.setSuffix(spec.suffix)
            self.spin.setSingleStep(.5 if spec.multiplier==1000 else max(.001,(spec.maximum-spec.minimum)/200))
            self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.spin)
        self.mapping_label=QLabel('Right-click to map')
        self.mapping_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mapping_label.setStyleSheet('color: #95a5b3; font-size: 11px;')
        layout.addWidget(self.mapping_label)
        self.menu=QMenu(self)
        self.map_action=self.menu.addAction('Map to MIDI')
        self.map_action.triggered.connect(lambda:map_requested(spec.name))
        self.cancel_action=self.menu.addAction('Cancel MIDI mapping')
        self.cancel_action.triggered.connect(cancel_requested)
        self.unmap_action=self.menu.addAction('Remove MIDI mapping')
        self.unmap_action.triggered.connect(lambda:unmap_requested(spec.name))
        for widget in [self]+self.findChildren(QWidget):
            if widget is not self.menu:
                widget.installEventFilter(self)
        self.set_mapping(False,[])
        if spec.multiplier==1000 and 'Glide' not in spec.label:
            self.setToolTip('Envelope coefficient time constant; not a literal measured stage duration.')
        self.dial.valueChanged.connect(self._dial)
        if spec.choices:
            self.spin.currentIndexChanged.connect(lambda index:self._spin(index+spec.minimum))
        else:
            self.spin.valueChanged.connect(self._spin)
        self.dial.sliderPressed.connect(lambda:selected(spec.name))
        self.set_value(value)

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.MouseButtonPress and event.button()==Qt.MouseButton.RightButton:
            if not self.menu.isVisible(): self.menu.popup(event.globalPosition().toPoint())
            return True
        if event.type()==QEvent.Type.ContextMenu:
            if not self.menu.isVisible(): self.menu.popup(event.globalPos())
            return True
        return super().eventFilter(watched,event)

    def set_mapping(self,waiting,controls):
        state=(waiting,tuple(controls))
        if getattr(self,'mapping_state',None)==state:
            return
        self.mapping_state=state
        self.setProperty('midiWaiting',waiting)
        self.style().unpolish(self)
        self.style().polish(self)
        self.cancel_action.setEnabled(waiting)
        self.unmap_action.setEnabled(bool(controls))
        if waiting:
            self.mapping_label.setText('Waiting for MIDI…')
            self.mapping_label.setStyleSheet('color: #ffd27d; font-size: 11px;')
        elif controls:
            channel,control=controls[0].split(':')
            self.mapping_label.setText(f'MIDI CC {control} · ch {int(channel)+1}')
            self.mapping_label.setStyleSheet('color: #8edbc0; font-size: 11px;')
        else:
            self.mapping_label.setText('Right-click to map')
            self.mapping_label.setStyleSheet('color: #95a5b3; font-size: 11px;')

    def set_value(self,value):
        blockers=[QSignalBlocker(self.dial),QSignalBlocker(self.spin)]
        self.dial.setValue(self.spec.position(value))
        if self.spec.choices:
            self.spin.setCurrentIndex(round(value-self.spec.minimum))
        else:
            self.spin.setValue(value*self.spec.multiplier)
        del blockers

    def _dial(self,position):
        value=self.spec.from_position(position)
        self.set_value(value)
        self.selected(self.spec.name)
        self.changed(self.spec.name,value)

    def _spin(self,display):
        value=display/self.spec.multiplier
        blocker=QSignalBlocker(self.dial)
        self.dial.setValue(self.spec.position(value))
        del blocker
        self.selected(self.spec.name)
        self.changed(self.spec.name,value)


class Window(QMainWindow):
    def __init__(self,no_devices=False):
        super().__init__()
        self.setWindowTitle('Electribe Bass Lab')
        self.resize(1080,880)
        self.patch=read_patch(ROOT/'baselines/bassline-v1/preset.json')
        self.specs=specs_for(self.patch['architecture'])
        self.mode_paths={'bass':ROOT/'baselines/bassline-v1/preset.json',
                         'modeld':ROOT/'presets/model-d-bass.json'}
        reference_candidate=ROOT/'presets/model-d-reference-candidate.json'
        if reference_candidate.exists(): self.mode_paths['modeld']=reference_candidate
        self.synth=Synth(self.patch)
        self.audio=Audio(self.synth)
        self.midi=Midi(self.synth)
        self.dirty=False
        self.current_path=ROOT/'baselines/bassline-v1/preset.json'
        self.selected='cutoff_hz'
        self.mappings={}
        self.waiting_for=None
        self.knobs={}
        self.record_path=None
        self.no_devices=no_devices
        self._build()
        self._patches()
        if not no_devices:
            self.refresh_devices()
        self.timer=QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)

    def _build(self):
        container=QWidget()
        self.setCentralWidget(container)
        layout=QVBoxLayout(container)
        layout.setContentsMargins(22,16,22,16)
        title=QLabel('ELECTRIBE  /  BASS LAB')
        title.setObjectName('title')
        layout.addWidget(title)
        layout.addWidget(QLabel('Approved bass engine + Model D-style prototype · desktop audition and patch editor'))
        row=QHBoxLayout()
        self.mode_selector=QComboBox()
        self.mode_selector.addItem('Approved bass','bass')
        self.mode_selector.addItem('Model D prototype','modeld')
        self.mode_selector.activated.connect(self.change_mode)
        row.addWidget(self.mode_selector)
        self.patch_selector=QComboBox()
        self.patch_selector.setMinimumWidth(250)
        row.addWidget(QLabel('Patch'))
        row.addWidget(self.patch_selector,1)
        self.patch_selector.activated.connect(self.load_selected)
        save=QPushButton('Save As…')
        save.clicked.connect(self.save_as)
        row.addWidget(save)
        importing=QPushButton('Import…')
        importing.clicked.connect(self.import_patch)
        row.addWidget(importing)
        self.dirty_label=QLabel('Saved')
        row.addWidget(self.dirty_label)
        self.architecture_label=QLabel('12 dB SVF')
        row.addWidget(self.architecture_label)
        layout.addLayout(row)
        devices=QGridLayout()
        self.midi_selector=QComboBox()
        self.output_selector=QComboBox()
        self.midi_selector.setMinimumWidth(300)
        self.output_selector.setMinimumWidth(390)
        devices.addWidget(QLabel('MIDI input'),0,0)
        devices.addWidget(self.midi_selector,0,1)
        connect=QPushButton('Connect MIDI')
        connect.clicked.connect(self.connect_midi)
        devices.addWidget(connect,0,2)
        self.channel=QComboBox()
        self.channel.addItem('All channels',None)
        for channel in range(16): self.channel.addItem(f'Channel {channel+1}',channel)
        self.channel.currentIndexChanged.connect(lambda:self.synth.send('channel',self.channel.currentData()))
        devices.addWidget(self.channel,0,3)
        devices.addWidget(QLabel('Audio output'),1,0)
        devices.addWidget(self.output_selector,1,1)
        self.start=QPushButton('Start audio')
        self.start.setObjectName('primary')
        self.start.clicked.connect(self.toggle_audio)
        devices.addWidget(self.start,1,2)
        self.buffer=QComboBox()
        for frames in (128,256,512,1024): self.buffer.addItem(f'{frames} samples',frames)
        self.buffer.setCurrentIndex(1)
        devices.addWidget(self.buffer,1,3)
        refresh=QPushButton('Refresh devices')
        refresh.clicked.connect(self.refresh_devices)
        devices.addWidget(refresh,2,2)
        self.legato=QCheckBox('Legato (no retrigger on overlapping notes)')
        self.legato.toggled.connect(lambda value:self.synth.send('legato',value))
        devices.addWidget(self.legato,2,1)
        panic=QPushButton('PANIC / All notes off')
        panic.clicked.connect(lambda:self.synth.send('panic'))
        devices.addWidget(panic,2,3)
        layout.addLayout(devices)
        self.tabs=QTabWidget()
        self.build_controls()
        layout.addWidget(self.tabs,1)
        learnrow=QHBoxLayout()
        self.learn_label=QLabel('Right-click a knob to map it · mappings last for this session only')
        learnrow.addWidget(self.learn_label,1)
        self.learn_button=QPushButton('Map selected knob')
        self.learn_button.clicked.connect(self.learn)
        learnrow.addWidget(self.learn_button)
        clear=QPushButton('Clear MIDI mappings')
        clear.clicked.connect(self.clear_mapping)
        learnrow.addWidget(clear)
        layout.addLayout(learnrow)
        keys=QHBoxLayout()
        keys.setSpacing(3)
        for note in range(24,48):
            pitch=('C','C♯','D','D♯','E','F','F♯','G','G♯','A','B♭','B')[note%12]
            key=QPushButton(f'{pitch}{note//12-1}')
            key.setFixedHeight(46)
            key.setMinimumWidth(28)
            key.setStyleSheet('background: #151d26;' if note%12 in (1,3,6,8,10) else 'background: #465260;')
            key.pressed.connect(lambda note=note:self.synth.send('midi',('note_on',0,note,100)))
            key.released.connect(lambda note=note:self.synth.send('midi',('note_off',0,note,0)))
            keys.addWidget(key)
        layout.addLayout(keys)
        bottom=QHBoxLayout()
        bottom.addWidget(QLabel('Master'))
        self.volume=QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(-60,0)
        self.volume.setValue(-18)
        self.volume.valueChanged.connect(self.set_volume)
        bottom.addWidget(self.volume,1)
        self.volume_label=QLabel('-18 dB')
        bottom.addWidget(self.volume_label)
        bottom.addWidget(QLabel('Patch volume'))
        self.patch_volume=QDoubleSpinBox()
        self.patch_volume.setRange(-24,24)
        self.patch_volume.setDecimals(2)
        self.patch_volume.setSingleStep(.5)
        self.patch_volume.setSuffix(' dB')
        self.patch_volume.setValue(self.patch.get('output_gain_db',0))
        self.patch_volume.setEnabled(self.patch['architecture']=='modeld')
        self.patch_volume.setToolTip('Clean Model D patch gain after synthesis. Saved with the patch; separate from drive and master.')
        self.patch_volume.valueChanged.connect(self.set_patch_volume)
        bottom.addWidget(self.patch_volume)
        self.meter=QProgressBar()
        self.meter.setRange(0,100)
        self.meter.setFormat('Output %p%')
        self.meter.setFixedWidth(140)
        bottom.addWidget(self.meter)
        self.record=QPushButton('● Record WAV')
        self.record.clicked.connect(self.toggle_record)
        bottom.addWidget(self.record)
        layout.addLayout(bottom)
        self.status=QLabel('Audio stopped. Connect your MPK, choose an output, then Start audio.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.activity=QLabel('MIDI — · 48 kHz · Wired output recommended for low latency')
        self.activity.setWordWrap(True)
        layout.addWidget(self.activity)

    def build_controls(self):
        while self.tabs.count():
            widget=self.tabs.widget(0)
            self.tabs.removeTab(0)
            widget.deleteLater()
        self.knobs={}
        parameters=parameters_for(self.patch['architecture'])
        for group in dict.fromkeys(parameter.group for parameter in parameters):
            tab=QWidget()
            grid=QGridLayout(tab)
            for index,spec in enumerate(parameter for parameter in parameters if parameter.group==group):
                knob=Knob(spec,self.patch['parameters'][spec.name],self.parameter_changed,self.select_parameter,
                          self.begin_mapping,self.cancel_mapping,self.remove_mapping)
                if engine_key(self.patch['architecture'])=='modeld':
                    knob.setToolTip('Model D-style prototype. Contour times use this engine’s timing convention.')
                self.knobs[spec.name]=knob
                grid.addWidget(knob,index//4,index%4)
            scroll=QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(tab)
            self.tabs.addTab(scroll,group.replace('&','&&'))

    def change_mode(self):
        family=self.mode_selector.currentData()
        previous=engine_key(self.patch['architecture'])
        if family==previous: return
        if not self._confirm_discard():
            blocker=QSignalBlocker(self.mode_selector)
            self.mode_selector.setCurrentIndex(self.mode_selector.findData(previous))
            return
        try:
            path=self.mode_paths[family]
            patch=read_patch(path)
            self.mode_paths[previous]=self.current_path
            self.apply_patch(patch)
            self.current_path=path
            self._patches(path)
        except (OSError,ValueError) as error:
            blocker=QSignalBlocker(self.mode_selector)
            self.mode_selector.setCurrentIndex(self.mode_selector.findData(previous))
            QMessageBox.warning(self,'Cannot change engine',str(error))

    def _patches(self,selected=None):
        self.patch_selector.blockSignals(True)
        self.patch_selector.clear()
        for path in patch_paths():
            try:
                patch=read_patch(path)
                if engine_key(patch['architecture'])!=engine_key(self.patch['architecture']): continue
                self.patch_selector.addItem(patch['name'],str(path))
            except (OSError,ValueError):
                continue
        if selected:
            index=self.patch_selector.findData(str(selected))
            if index>=0: self.patch_selector.setCurrentIndex(index)
        self.patch_selector.blockSignals(False)

    def _confirm_discard(self):
        return not self.dirty or QMessageBox.question(self,'Unsaved patch',
             'Discard the unsaved changes?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes

    def apply_patch(self,patch):
        changed=engine_key(patch['architecture'])!=engine_key(self.patch['architecture'])
        self.patch=patch
        self.specs=specs_for(patch['architecture'])
        self.architecture_label.setText({'svf12':'12 dB SVF','ladder12':'12 dB cascade','ladder24':'24 dB cascade',
                                        'modeld':'24 dB nonlinear ladder'}[patch['architecture']])
        if changed:
            self.mappings={}
            self.waiting_for=None
            self.selected='cutoff_hz'
            self.build_controls()
            blocker=QSignalBlocker(self.mode_selector)
            self.mode_selector.setCurrentIndex(self.mode_selector.findData(engine_key(patch['architecture'])))
            del blocker
            self._patches()
            self.refresh_mapping_status()
        for name,knob in self.knobs.items(): knob.set_value(patch['parameters'][name])
        blocker=QSignalBlocker(self.patch_volume)
        self.patch_volume.setValue(patch.get('output_gain_db',0))
        self.patch_volume.setEnabled(patch['architecture']=='modeld')
        del blocker
        self.synth.send('patch',patch)
        self.dirty=False
        self.dirty_label.setText('Saved')
        self.status.setText(f'Loaded {patch["name"]}.')

    def load_selected(self):
        if not self._confirm_discard():
            blocker=QSignalBlocker(self.patch_selector)
            self.patch_selector.setCurrentIndex(self.patch_selector.findData(str(self.current_path)))
            del blocker
            return
        try:
            path=self.patch_selector.currentData()
            self.apply_patch(read_patch(path))
            self.current_path=Path(path)
        except (OSError,ValueError) as error:
            QMessageBox.warning(self,'Cannot load patch',str(error))

    def parameter_changed(self,name,value):
        self.patch['parameters'][name]=value
        self.synth.send('parameter',name,value)
        self.dirty=True
        self.dirty_label.setText('● Unsaved')

    def select_parameter(self,name):
        self.selected=name
        self.refresh_mapping_status()

    def refresh_mapping_status(self):
        for name,knob in self.knobs.items():
            controls=[key for key,target in self.mappings.items() if target==name]
            knob.set_mapping(self.waiting_for==name,controls)
        if self.waiting_for:
            self.learn_label.setText('Waiting for MIDI: '+self.specs[self.waiting_for].label+' — turn a controller knob')
            self.learn_button.setText('Cancel mapping')
        else:
            self.learn_label.setText('Selected: '+self.specs[self.selected].label+' · session-only MIDI mappings')
            self.learn_button.setText('Map selected knob')

    def begin_mapping(self,name):
        if self.synth.send('learn',name):
            self.selected=name
            self.waiting_for=name
            self.refresh_mapping_status()
            self.status.setText(f'Waiting for MIDI — turn a controller knob to map {self.specs[name].label}.')

    def cancel_mapping(self):
        self.synth.send('learn',None)
        self.waiting_for=None
        self.refresh_mapping_status()
        self.status.setText('MIDI mapping cancelled.')

    def remove_mapping(self,name):
        self.synth.send('unmap',name)
        self.mappings={key:target for key,target in self.mappings.items() if target!=name}
        if self.waiting_for==name: self.waiting_for=None
        self.refresh_mapping_status()
        self.status.setText('Removed MIDI mapping for '+self.specs[name].label+'.')

    def save_as(self):
        self.tick()
        name,accepted=QInputDialog.getText(self,'Save new patch','Patch name:',text=self.patch['name']+' edited')
        if not accepted: return
        try:
            path=save_patch(name,self.patch)
            self.patch['name']=name.strip()
            self.dirty=False
            self.dirty_label.setText('Saved')
            self._patches(path)
            self.current_path=path
            self.status.setText(f'Saved {path.name}; existing patches were not overwritten.')
        except (OSError,ValueError) as error:
            QMessageBox.warning(self,'Cannot save patch',str(error))

    def import_patch(self):
        if not self._confirm_discard(): return
        path,_=QFileDialog.getOpenFileName(self,'Import synth patch',str(ROOT/'presets'),'JSON patches (*.json)')
        if not path: return
        try:
            self.apply_patch(read_patch(path))
            self.current_path=Path(path)
            self.patch_selector.addItem('Imported: '+self.patch['name'],path)
            self.patch_selector.setCurrentIndex(self.patch_selector.count()-1)
            self.status.setText('Imported patch. Use Save As to add it to your patch list.')
        except (OSError,ValueError) as error:
            QMessageBox.warning(self,'Cannot import patch',str(error))

    def refresh_devices(self):
        if self.audio.stream:
            self.status.setText('Stop audio before refreshing devices.')
            return
        try:
            self.midi_selector.clear()
            names=midi_backend().get_input_names()
            self.midi_selector.addItems(names)
            preferred=next((index for index,name in enumerate(names) if 'MPK' in name.upper()),0)
            self.midi_selector.setCurrentIndex(preferred)
            self.output_selector.clear()
            choices=outputs()
            for output in choices: self.output_selector.addItem(output['label'],output)
            preferred=next((index for index,output in enumerate(choices)
                            if output.get('sink') is None and 'analog' in output['label'].lower()),
                           next((index for index,output in enumerate(choices)
                                 if output.get('sink') and 'analog' in output['sink']),0))
            self.output_selector.setCurrentIndex(preferred)
            if names and 'MPK' in names[self.midi_selector.currentIndex()].upper() and self.midi.port is None:
                self.midi.connect(names[self.midi_selector.currentIndex()])
                self.status.setText('MPK connected. Choose your wired output, then press Start audio.')
            else:
                self.status.setText('Devices ready. Audio stays stopped until you press Start audio.')
        except Exception as error:
            self.status.setText(f'Device access: {error}')

    def connect_midi(self):
        try:
            name=self.midi_selector.currentText()
            if not name: raise ValueError('No MIDI input selected')
            self.midi.connect(name)
            self.status.setText(f'Connected to {name}.')
        except Exception as error:
            self.status.setText(f'MIDI connection failed: {error}')

    def toggle_audio(self):
        if self.audio.stream:
            self.audio.stop()
            self.record.setText('● Record WAV')
            self.start.setText('Start audio')
            self.output_selector.setEnabled(True)
            self.buffer.setEnabled(True)
            self.status.setText('Audio stopped.')
            return
        try:
            output=self.output_selector.currentData()
            if output is None: raise ValueError('No audio output selected')
            self.audio.start(output,self.buffer.currentData())
            self.start.setText('Stop audio')
            self.output_selector.setEnabled(False)
            self.buffer.setEnabled(False)
            note=' Bluetooth adds transport delay.' if output['bluetooth'] else ''
            if getattr(self.audio.stream,'latency_measured',True):
                latency=float(self.audio.stream.latency)*1000
                self.status.setText(f'Audio running · reported output buffering {latency:.1f} ms.{note}')
            else:
                self.status.setText('Audio running · measuring buffering.'+note)
        except Exception as error:
            self.status.setText(f'Audio start failed: {error}')

    def set_volume(self,value):
        self.volume_label.setText(f'{value} dB')
        self.synth.send('master',10**(value/20))

    def set_patch_volume(self,value):
        if self.patch['architecture']!='modeld': return
        self.patch['output_gain_db']=value
        self.synth.send('output_gain_db',value)
        self.dirty=True
        self.dirty_label.setText('● Unsaved')

    def learn(self):
        if self.waiting_for:
            self.cancel_mapping()
        else:
            self.begin_mapping(self.selected)

    def clear_mapping(self):
        self.mappings={}
        self.synth.send('mapping',{})
        self.synth.send('learn',None)
        self.waiting_for=None
        self.refresh_mapping_status()
        self.status.setText('MIDI mappings cleared.')

    def toggle_record(self):
        if self.audio.recorder:
            recorder=self.audio.stop_recording()
            self.record.setText('● Record WAV')
            self.status.setText(recorder.error or f'Saved {recorder.path.name} ({recorder.frames/recorder.rate:.1f} s).')
            return
        if not self.audio.stream:
            self.status.setText('Start audio before recording.')
            return
        try:
            directory=ROOT/'outputs/live-recordings'
            directory.mkdir(parents=True,exist_ok=True)
            stamp=datetime.now(ZoneInfo('America/Los_Angeles')).strftime('%Y%m%d-%H%M%S-%f')
            self.audio.recorder=Recorder(directory/f'bass-lab-{stamp}.wav',self.synth.rate)
            self.record.setText('■ Stop recording')
            self.status.setText('Recording the synth output to outputs/live-recordings.')
        except OSError as error:
            self.status.setText(f'Could not start recording: {error}')

    def tick(self):
        if self.audio.stream is None:
            self.synth.drain()
            self.synth.peak=0
        self.meter.setValue(round(min(1,self.synth.peak)*100))
        pulse_backend=self.output_selector.currentData() or {}
        underruns='n/a' if pulse_backend.get('backend')=='pulse-simple' else str(self.audio.underruns)
        buffering=''
        if self.audio.stream and getattr(self.audio.stream,'latency_measured',True):
            buffering=f' · Buffering {float(self.audio.stream.latency)*1000:.0f} ms'
        self.activity.setText(f'MIDI: {self.midi.last_message} · Note {self.synth.last_note} · '
                              f'Underruns {underruns} · Clipped blocks {self.synth.clipped}'+buffering)
        for _ in range(128):
            try:
                event=self.synth.notifications.get_nowait()
            except queue.Empty:
                break
            if event[0] in ('learning','mapping','learned','parameter') and event[1]!=engine_key(self.patch['architecture']):
                continue
            if event[0]=='learning':
                self.waiting_for=event[2]
                self.refresh_mapping_status()
            elif event[0]=='mapping':
                self.mappings=event[2]
                self.refresh_mapping_status()
            elif event[0]=='learned':
                _,family,key,name=event
                self.status.setText(f'Mapped CC {key.split(":")[1]} → {self.specs[name].label} (this session only).')
            elif event[0]=='parameter':
                _,family,name,value=event
                self.patch['parameters'][name]=value
                self.knobs[name].set_value(value)
                self.dirty=True
                self.dirty_label.setText('● Unsaved')
            else:
                self.status.setText(str(event[1]))
        if self.audio.error:
            message=self.audio.error
            self.audio.stop()
            self.start.setText('Start audio')
            self.output_selector.setEnabled(True)
            self.buffer.setEnabled(True)
            self.status.setText('Audio stopped: '+message)
            self.audio.error=None
        if self.audio.recorder and self.audio.recorder.error:
            self.toggle_record()

    def closeEvent(self,event):
        if not self._confirm_discard():
            event.ignore()
            return
        self.timer.stop()
        self.midi.close()
        self.audio.stop()
        self.synth.close()
        event.accept()


STYLE='''
QWidget { background: #19212b; color: #e6ecf0; font-size: 13px; }
QLabel#title { color: #8edbc0; font-size: 25px; font-weight: 700; padding: 4px 0; }
QPushButton, QComboBox, QDoubleSpinBox { background: #293542; border: 1px solid #465364; border-radius: 5px; padding: 6px; }
QPushButton:hover { background: #3c4d60; }
QPushButton:pressed { background: #477e70; }
QPushButton#primary { background: #356b59; font-weight: 600; }
QTabWidget::pane { border: 1px solid #3b4958; border-radius: 5px; }
QTabBar::tab { background: #263240; padding: 9px 20px; }
QTabBar::tab:selected { background: #3d5d57; }
QDial { background: #22303d; }
QWidget#mappingCard[midiWaiting="true"] { background: #38382c; border: 1px solid #e3be68; border-radius: 8px; }
QProgressBar { border: 1px solid #465364; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background: #4a9d7e; }
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-devices',action='store_true')
    parser.add_argument('--screenshot',type=Path)
    parser.add_argument('--patch',type=Path,help='Open a saved patch; audio remains stopped')
    args=parser.parse_args()
    app=QApplication(sys.argv[:1])
    app.setApplicationName('Electribe Bass Lab')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window=Window(args.no_devices)
    if args.patch:
        window.apply_patch(read_patch(args.patch))
        window.current_path=args.patch.resolve()
        window._patches(window.current_path)
    window.show()
    if args.screenshot:
        def capture():
            args.screenshot.parent.mkdir(parents=True,exist_ok=True)
            window.grab().save(str(args.screenshot))
            window.close()
        QTimer.singleShot(500,capture)
    sys.exit(app.exec())


if __name__=='__main__':
    main()
