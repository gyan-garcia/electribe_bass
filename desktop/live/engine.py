import ctypes
import os
from pathlib import Path
import queue
import subprocess
import threading

import numpy as np
from eq import Equalizer
from reverb import Reverb

from model import ARCHITECTURES, NAMES, MODEL_D_NAMES, Notes, engine_key, parameters_for, validate_patch

HERE=Path(__file__).resolve().parent


def build_library(kind='bass'):
    filename='modeld' if kind=='modeld' else 'voice'
    source=HERE/f'native/{filename}.c'
    library=HERE/f'build/{filename}.so'
    library.parent.mkdir(exist_ok=True)
    if not library.exists() or source.stat().st_mtime>library.stat().st_mtime:
        temporary=library.with_name(f'{filename}-{os.getpid()}.so')
        subprocess.run(['gcc','-O3','-Wall','-Wextra','-Werror','-fPIC','-shared',
                        str(source),'-lm','-o',str(temporary)],check=True)
        temporary.replace(library)
    return library


class NativeVoice:
    def __init__(self,rate=48000,kind='bass'):
        self.parameter_count=len(MODEL_D_NAMES) if kind=='modeld' else len(NAMES)
        self.library=ctypes.CDLL(str(build_library(kind)))
        if kind=='modeld':
            self.library.synth_parameter_count.restype=ctypes.c_int
            if self.library.synth_parameter_count()!=self.parameter_count:
                raise ValueError('Model D native parameter schema mismatch')
        pointer=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
        settings=np.ctypeslib.ndpointer(dtype=np.float64,flags='C_CONTIGUOUS')
        self.library.synth_create.argtypes=[ctypes.c_int]
        self.library.synth_create.restype=ctypes.c_void_p
        self.library.synth_destroy.argtypes=[ctypes.c_void_p]
        self.library.synth_destroy.restype=None
        self.library.synth_reset.argtypes=[ctypes.c_void_p]
        self.library.synth_reset.restype=None
        self.library.synth_process.argtypes=[ctypes.c_void_p]+[pointer]*6+[ctypes.c_int,settings,ctypes.c_int]
        self.library.synth_process.restype=None
        self.library.synth_gain.argtypes=[ctypes.c_void_p,pointer,ctypes.c_int,ctypes.c_double]
        self.library.synth_gain.restype=None
        self.handle=self.library.synth_create(rate)
        if not self.handle:
            raise ValueError('Could not create the native synth')

    def reset(self):
        self.library.synth_reset(self.handle)

    def process(self,output,controls,settings,architecture=0):
        frames=len(output)
        if settings.shape!=(self.parameter_count,) or any(control.shape!=(frames,) for control in controls):
            raise ValueError('Incorrect native voice buffer sizes')
        self.library.synth_process(self.handle,output,*controls,frames,settings,architecture)

    def gain(self,audio,target):
        self.library.synth_gain(self.handle,audio,len(audio),target)

    def close(self):
        if self.handle:
            self.library.synth_destroy(self.handle)
            self.handle=None


class Synth:
    def __init__(self,patch,rate=48000,capacity=4096):
        self.voice=NativeVoice(rate)
        self.modeld_voice=NativeVoice(rate,'modeld')
        self.rate=rate
        self.capacity=capacity
        self.patch=validate_patch(patch)
        self.eq=Equalizer(rate)
        self.eq.configure(self.patch['eq'])
        self.reverb=Reverb(rate)
        self.reverb.configure(self.patch['reverb'])
        self.setting_buffers={'bass':np.zeros(len(NAMES),dtype=np.float64),
                              'modeld':np.zeros(len(MODEL_D_NAMES),dtype=np.float64)}
        self.family=engine_key(self.patch['architecture'])
        self.specs={parameter.name:parameter for parameter in parameters_for(self.patch['architecture'])}
        self.names=list(self.specs)
        self.indices={name:index for index,name in enumerate(self.names)}
        self.settings=self.setting_buffers[self.family]
        self.settings[:]=[self.patch['parameters'][name] for name in self.names]
        self.architecture=ARCHITECTURES[self.patch['architecture']]
        self.output_gain_db=self.patch.get('output_gain_db',0.)
        self.commands=queue.Queue(maxsize=2048)
        self.notifications=queue.SimpleQueue()
        self.overflow=threading.Event()
        self.notes=Notes()
        self.frequency=49.0
        self.velocity=127
        self.channel=None
        self.legato=False
        self.master=.126
        self.bend_range=2
        self.learn_target=None
        self.mapping={}
        self.session_mappings={'bass':{},'modeld':{}}
        self.pending_trigger=False
        self.dropped=0
        self.clipped=0
        self.peak=0.0
        self.last_note='—'
        self.audio=np.zeros(capacity,dtype=np.float32)
        self.controls=[np.zeros(capacity,dtype=np.float32) for _ in range(5)]
        self.controls[3].fill(1)

    def send(self,*command):
        try:
            self.commands.put_nowait(command)
            return True
        except queue.Full:
            self.dropped+=1
            self.overflow.set()
            return False

    def _panic(self):
        self.notes.panic()
        self.pending_trigger=False
        self.last_note='—'
        self.voice.reset()
        self.modeld_voice.reset()
        self.eq.reset()
        self.reverb.reset()

    def _midi(self,message):
        kind,channel,first,second=message
        if self.channel is not None and channel!=self.channel:
            return
        before=self.notes.active
        if kind=='note_on' and second>0:
            self.notes.note_on(channel,first,second)
            self.pending_trigger=self.pending_trigger or before is None or not self.legato
        elif kind in ('note_off','note_on'):
            self.notes.note_off(channel,first)
            if self.notes.active and self.notes.active!=before and not self.legato:
                self.pending_trigger=True
        elif kind=='pitchwheel':
            self.notes.bends[channel]=first/8192
        elif kind=='control_change':
            if first==64:
                self.notes.pedal(channel,second)
            elif first==120:
                self._panic()
            elif first==123:
                self.notes.release_channel(channel)
            elif first==121:
                self.notes.bends[channel]=0
                self.notes.pedal(channel,0)
            key=f'{channel}:{first}'
            if self.family=='modeld' and first==1 and key not in self.mapping and self.learn_target is None:
                value=second/127
                self.settings[self.indices['mod_amount']]=value
                self.notifications.put(('parameter',self.family,'mod_amount',value))
            if self.learn_target and first not in (64,120,121,123):
                self.mapping={control:name for control,name in self.mapping.items()
                              if name!=self.learn_target and control!=key}
                self.mapping[key]=self.learn_target
                self.notifications.put(('mapping',self.family,dict(self.mapping)))
                self.notifications.put(('learned',self.family,key,self.learn_target))
                self.learn_target=None
                self.notifications.put(('learning',self.family,None))
            if key in self.mapping:
                name=self.mapping[key]
                value=self.specs[name].from_position(second*1000/127)
                self.settings[self.indices[name]]=value
                self.notifications.put(('parameter',self.family,name,value))

    def drain(self):
        if self.overflow.is_set():
            while True:
                try:
                    self.commands.get_nowait()
                except queue.Empty:
                    break
            self._panic()
            self.overflow.clear()
            self.notifications.put(('error','Control queue overflow: notes reset.'))
        for _ in range(256):
            try:
                command=self.commands.get_nowait()
            except queue.Empty:
                break
            kind,*values=command
            if kind=='midi':
                self._midi(values[0])
            elif kind=='parameter':
                name,value=values
                spec=self.specs.get(name)
                if spec and np.isfinite(value) and spec.minimum<=value<=spec.maximum:
                    if not spec.choices or value==round(value): self.settings[self.indices[name]]=value
            elif kind=='patch':
                patch=validate_patch(values[0])
                self._panic()
                family=engine_key(patch['architecture'])
                if family!=self.family:
                    self.session_mappings[self.family]=self.mapping
                    self.mapping=self.session_mappings[family]
                    self.learn_target=None
                self.family=family
                self.patch=patch
                self.eq.configure(patch['eq'])
                self.reverb.configure(patch['reverb'])
                self.specs={parameter.name:parameter for parameter in parameters_for(patch['architecture'])}
                self.names=list(self.specs)
                self.indices={name:index for index,name in enumerate(self.names)}
                self.settings=self.setting_buffers[self.family]
                self.settings[:]=[patch['parameters'][name] for name in self.names]
                self.architecture=ARCHITECTURES[patch['architecture']]
                self.output_gain_db=patch.get('output_gain_db',0.)
                self.notifications.put(('mapping',self.family,dict(self.mapping)))
                self.notifications.put(('learning',self.family,self.learn_target))
            elif kind=='panic':
                self._panic()
            elif kind=='master':
                self.master=max(0,min(1,float(values[0])))
            elif kind=='reverb':
                self.reverb.configure(values[0])
            elif kind=='eq':
                self.eq.configure(values[0])
            elif kind=='output_gain_db':
                value=values[0]
                if self.family=='modeld' and not isinstance(value,bool) and np.isfinite(value) and -24<=value<=24:
                    self.output_gain_db=float(value)
            elif kind=='legato':
                self.legato=bool(values[0])
            elif kind=='channel':
                self.channel=values[0]
                self._panic()
            elif kind=='learn':
                self.learn_target=values[0] if values[0] in self.specs else None
                self.notifications.put(('learning',self.family,self.learn_target))
            elif kind=='mapping':
                self.mapping={key:name for key,name in values[0].items() if name in self.specs}
                self.notifications.put(('mapping',self.family,dict(self.mapping)))
            elif kind=='unmap':
                self.mapping={key:name for key,name in self.mapping.items() if name!=values[0]}
                if self.learn_target==values[0]:
                    self.learn_target=None
                    self.notifications.put(('learning',self.family,None))
                self.notifications.put(('mapping',self.family,dict(self.mapping)))

    def render(self,frames):
        if frames<1 or frames>self.capacity:
            raise ValueError('Audio buffer exceeds synth capacity')
        self.drain()
        active=self.notes.active
        if active:
            channel,note,self.velocity=active
            bend=self.notes.bends.get(channel,0)*self.bend_range
            self.frequency=440*2**((note+bend-69)/12)
            self.last_note=f'{note} · velocity {self.velocity}'
        else:
            self.last_note='—'
        pitch,gate,trigger,cutoff,resonance=[control[:frames] for control in self.controls]
        pitch.fill(self.frequency)
        gate.fill(1 if active else 0)
        trigger.fill(0)
        if self.pending_trigger:
            trigger[0]=1
            self.pending_trigger=False
        resonance.fill(self.settings[self.indices['resonance']])
        output=self.audio[:frames]
        voice=self.modeld_voice if self.family=='modeld' else self.voice
        voice.process(output,[pitch,gate,trigger,cutoff,resonance],self.settings,self.architecture)
        self.eq.process(output)
        self.reverb.process(output)
        voice.gain(output,self.master*(self.velocity/127)**.7*10**(self.output_gain_db/20))
        if not np.all(np.isfinite(output)):
            output.fill(0)
            self._panic()
            raise ValueError('Non-finite audio: synth reset')
        self.peak=float(np.max(abs(output)))
        if self.peak>.98:
            self.clipped+=1
        np.clip(output,-.98,.98,out=output)
        return output

    def close(self):
        self.voice.close()
        self.modeld_voice.close()
        self.eq.close()
        self.reverb.close()
