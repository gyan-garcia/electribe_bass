"""Three biquads using RBJ formulas: https://www.w3.org/TR/audio-eq-cookbook/."""
import ctypes
import math
from pathlib import Path
import subprocess
import os
import numpy as np

CONTROLS={
    'low_hz':('Low shelf frequency',30,500,100,' Hz'),
    'low_db':('Low shelf gain',-12,12,0,' dB'),
    'mid_hz':('Mid frequency',80,6000,700,' Hz'),
    'mid_db':('Mid gain',-12,12,0,' dB'),
    'mid_q':('Mid Q',.3,4,.7,''),
    'high_hz':('High shelf frequency',500,12000,2500,' Hz'),
    'high_db':('High shelf gain',-12,12,0,' dB')}
DEFAULT={'enabled':False,**{key:value[3] for key,value in CONTROLS.items()}}

def validate(data):
    if not isinstance(data,dict) or set(data)!=set(DEFAULT) or not isinstance(data['enabled'],bool):
        raise ValueError('Invalid EQ settings')
    result={'enabled':data['enabled']}
    for key,(_,low,high,_,_) in CONTROLS.items():
        v=data[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not low<=v<=high:
            raise ValueError('Invalid EQ '+key)
        result[key]=float(v)
    return result

def coefficients(kind,hz,db,q,rate):
    if db==0:return [1,0,0,0,0]
    a=10**(db/40);w=2*math.pi*min(hz,rate*.45)/rate;c=math.cos(w);s=math.sin(w)
    if kind=='mid':
        alpha=s/(2*q);b=[1+alpha*a,-2*c,1-alpha*a];d=[1+alpha/a,-2*c,1-alpha/a]
    else:
        t=s*math.sqrt(2*a)
        if kind=='low':
            b=[a*((a+1)-(a-1)*c+t),2*a*((a-1)-(a+1)*c),a*((a+1)-(a-1)*c-t)]
            d=[(a+1)+(a-1)*c+t,-2*((a-1)+(a+1)*c),(a+1)+(a-1)*c-t]
        else:
            b=[a*((a+1)+(a-1)*c+t),-2*a*((a-1)+(a+1)*c),a*((a+1)+(a-1)*c-t)]
            d=[(a+1)-(a-1)*c+t,2*((a-1)-(a+1)*c),(a+1)-(a-1)*c-t]
    return [v/d[0] for v in b+d[1:]]

class Equalizer:
    def __init__(self,rate):
        here=Path(__file__).parent;src=here/'native/eq.c';lib=here/'build/eq.so';lib.parent.mkdir(exist_ok=True)
        if not lib.exists() or src.stat().st_mtime>lib.stat().st_mtime:
            temp=lib.with_name(f'eq-{os.getpid()}.so')
            subprocess.run(['gcc','-O3','-Wall','-Wextra','-Werror','-shared','-fPIC',str(src),'-lm','-o',str(temp)],check=True);temp.replace(lib)
        self.lib=ctypes.CDLL(str(lib));self.lib.eq_create.restype=ctypes.c_void_p
        self.lib.eq_destroy.argtypes=[ctypes.c_void_p];self.lib.eq_reset.argtypes=[ctypes.c_void_p]
        self.lib.eq_process.argtypes=[ctypes.c_void_p,np.ctypeslib.ndpointer(np.float32,flags='C_CONTIGUOUS'),ctypes.c_int,np.ctypeslib.ndpointer(np.float64,flags='C_CONTIGUOUS'),ctypes.c_double,ctypes.c_int]
        for name in ('eq_destroy','eq_reset','eq_process'):getattr(self.lib,name).restype=None
        self.handle=self.lib.eq_create()
        if not self.handle:raise MemoryError('Cannot allocate EQ')
        self.rate=rate;self.configure(DEFAULT)
    def configure(self,settings):
        self.settings=validate(settings)
        self.target=np.array(sum([coefficients(b,settings[b+'_hz'],settings[b+'_db'],settings['mid_q'],self.rate) for b in ('low','mid','high')],[]),np.float64)
    def process(self,audio):
        self.lib.eq_process(self.handle,audio,len(audio),self.target,float(self.settings['enabled']),self.rate)
    def reset(self):self.lib.eq_reset(self.handle)
    def close(self):
        if self.handle:self.lib.eq_destroy(self.handle);self.handle=None
