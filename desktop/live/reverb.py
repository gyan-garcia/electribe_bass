"""Small dark mono room. Mix 0..1; nominal low-frequency decay in seconds."""
import ctypes
import math
import os
from pathlib import Path
import subprocess
import numpy as np

DEFAULT={'mix':0.,'decay':.6}

def validate(settings):
    if not isinstance(settings,dict) or set(settings)!=set(DEFAULT):
        raise ValueError('Invalid reverb settings')
    for key,low,high in (('mix',0,1),('decay',.15,2.5)):
        v=settings[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:
            raise ValueError('Invalid reverb '+key)
    return {k:float(v) for k,v in settings.items()}

class Reverb:
    def __init__(self,rate):
        here=Path(__file__).parent;src=here/'native/reverb.c';lib=here/'build/reverb.so'
        lib.parent.mkdir(exist_ok=True)
        if not lib.exists() or src.stat().st_mtime>lib.stat().st_mtime:
            temp=lib.with_name(f'reverb-{os.getpid()}.so')
            subprocess.run(['gcc','-O3','-Wall','-Wextra','-Werror','-shared','-fPIC',str(src),'-lm','-o',str(temp)],check=True)
            temp.replace(lib)
        self.lib=ctypes.CDLL(str(lib))
        self.lib.room_create.argtypes=[ctypes.c_int];self.lib.room_create.restype=ctypes.c_void_p
        for name in ('room_destroy','room_reset'):
            getattr(self.lib,name).argtypes=[ctypes.c_void_p];getattr(self.lib,name).restype=None
        self.lib.room_process.argtypes=[ctypes.c_void_p,np.ctypeslib.ndpointer(np.float32,flags='C_CONTIGUOUS'),ctypes.c_int,ctypes.c_double,ctypes.c_double]
        self.lib.room_process.restype=None
        self.handle=self.lib.room_create(rate)
        if not self.handle:raise ValueError('Cannot create reverb at this sample rate')
        self.configure(DEFAULT)
    def configure(self,settings):self.settings=validate(settings)
    def process(self,audio):self.lib.room_process(self.handle,audio,len(audio),self.settings['mix'],self.settings['decay'])
    def reset(self):self.lib.room_reset(self.handle)
    def close(self):
        if self.handle:self.lib.room_destroy(self.handle);self.handle=None
