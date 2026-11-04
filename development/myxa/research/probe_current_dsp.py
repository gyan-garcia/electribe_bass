"""Measure the current DSP only; creates no patches or device audio."""
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'desktop/live/outputs/open-synth-review'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=ROOT/'desktop/live/native/modeld.c';before=hashlib.sha256(source.read_bytes()).hexdigest()
    presets={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'presets/user').glob('*.json')}
    wrapper=Path(__file__).with_suffix('.c');library=OUT/'current-probe.so'
    subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',str(wrapper),'-lm','-o',str(library)],check=True)
    lib=ctypes.CDLL(str(library));pointer=np.ctypeslib.ndpointer(np.float32,flags='C_CONTIGUOUS')
    lib.research_oscillator.argtypes=[pointer,ctypes.c_int,ctypes.c_float,ctypes.c_int]
    lib.research_oscillator.restype=None
    lib.research_filter.argtypes=[pointer,pointer,ctypes.c_int,ctypes.c_float,ctypes.c_float]
    lib.research_filter.restype=None
    n=8192;rate=48000
    osc=[]
    for bin_number in (85,701):
        frequency=rate*bin_number/n
        for shape,name in ((0,'triangle'),(2,'saw'),(3,'square'),(4,'pulse25'),(5,'pulse10')):
            out=np.zeros(n,np.float32);lib.research_oscillator(out,n,frequency,shape)
            spectrum=np.abs(np.fft.rfft(out))**2
            expected=np.zeros(len(spectrum),bool);expected[0]=True
            for harmonic in range(1,int(rate/2/frequency)+1):
                index=harmonic*bin_number;expected[max(0,index-1):index+2]=True
            alias=float(spectrum[~expected].sum());fund=float(spectrum[bin_number])
            osc.append(dict(waveform=name,frequency_hz=frequency,mean=float(out.mean()),
                            non_harmonic_energy_db_relative_to_fundamental=10*np.log10(max(alias,1e-30)/fund)))
    # Small-signal passband loss at a coherent low tone, far below the cutoff.
    n=48000;time=np.arange(n)/rate
    x=(.001*np.sin(2*np.pi*50*time)).astype(np.float32)
    results=[]
    for resonance in (0,.3,.5,.7,.9):
        y=np.zeros(n,np.float32);lib.research_filter(x,y,n,1000,resonance)
        a=float(np.sqrt(np.mean(x[12000:]**2)));b=float(np.sqrt(np.mean(y[12000:]**2)))
        results.append(dict(resonance=resonance,passband_gain_db=20*np.log10(b/a)))
    # A DC-balanced alternative input demonstrates why post-VCA DC removal
    # cannot undo bias inside the nonlinear ladder. It is a diagnostic only.
    dc_cases=[]
    for shape,name in ((4,'pulse25'),(5,'pulse10')):
        x=np.zeros(n,np.float32);lib.research_oscillator(x,n,50,shape)
        for centered in (False,True):
            z=(x-x.mean()).astype(np.float32) if centered else x
            y=np.zeros(n,np.float32);lib.research_filter(z,y,n,500,.7)
            tail=y[12000:].astype(float)
            dc_cases.append(dict(waveform=name,dc_balanced_input=centered,input_mean=float(z.mean()),output_mean=float(tail.mean()),
                                 output_ac_rms=float(np.sqrt(np.mean((tail-tail.mean())**2)))))
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in presets.items())
    report=dict(core_sha256=before,presets_unchanged=len(presets),sample_rate=rate,
                oscillator_measurements=osc,resonance_passband=results,pulse_bias=dc_cases,
                limitations=['Oscillator-only coherent FFT; measures non-harmonic folded energy, not whole-patch perceived aliasing.',
                             'Filter probe holds each 48 kHz input sample for two internal samples and averages outputs; not a full synth render.',
                             'Pulse-centering probe is a diagnostic, not a calibrated analogue circuit model or an approved improvement.',
                             'No comparisons of complete competitor audio engines, listening tests, or Blackfin timing measurements.'])
    (OUT/'current-dsp-measurements.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
