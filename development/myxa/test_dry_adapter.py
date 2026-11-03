"""Host comparison of the firmware bridge with the desktop dry engine."""
import ctypes,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'desktop/live'))
from engine import NativeVoice
from model import read_patch, MODEL_D_PARAMETERS
lib=ctypes.CDLL(str(ROOT/'development/myxa/build/dry_adapter.so'))
array=np.ctypeslib.ndpointer(np.float32,flags='C_CONTIGUOUS')
lib.myxa_dry_init.argtypes=[ctypes.c_int];lib.myxa_dry_init.restype=ctypes.c_int
lib.myxa_dry_process.argtypes=[array,array,array,array,ctypes.c_int];lib.myxa_dry_process.restype=None
assert lib.myxa_dry_init(-1)==-1
for index,name in enumerate(('UK-Res-Bass','BOSS-03','Moog-Res')):
    patch=read_patch(ROOT/f'presets/user/{name}.json')
    n=48000
    pitch=np.full(n,49,np.float32);pitch[16000:32000]=98
    gate=np.ones(n,np.float32);gate[36000:]=0
    trigger=np.zeros(n,np.float32);trigger[0]=1;trigger[16000]=1
    actual=np.zeros(n,np.float32);expected=actual.copy()
    assert lib.myxa_dry_init(index)==0
    lib.myxa_dry_process(pitch,gate,trigger,actual,n)
    # Embedded factory values are float32; compare the same quantized parameters.
    settings=np.array([patch['parameters'][p.name] for p in MODEL_D_PARAMETERS],np.float32).astype(np.float64)
    voice=NativeVoice(48000,'modeld')
    try:
        voice.process(expected,[pitch,gate,trigger,np.ones(n,np.float32),np.full(n,patch['parameters']['resonance'],np.float32)],settings,4)
    finally:voice.close()
    np.testing.assert_allclose(actual,expected,rtol=0,atol=2e-6)
    print(name,'max difference',float(abs(actual-expected).max()))

# Compare cached firmware API against a frozen pre-optimization engine while
# changing every parameter, with audio-rate resonance, pitch and gate movement.
import subprocess
from unittest.mock import patch as mock_patch
reference=ROOT/'development/myxa/build/modeld-before-cache.so'
subprocess.run(['gcc','-O3','-shared','-fPIC',str(ROOT/'desktop/live/fixtures/modeld-before-cache.c'),'-lm','-o',str(reference)],check=True)
lib.myxa_dry_set_parameter.argtypes=[ctypes.c_int,ctypes.c_double]
lib.myxa_dry_set_parameter.restype=ctypes.c_int
rng=np.random.default_rng(221)
for index,name in enumerate(('UK-Res-Bass','BOSS-03','Moog-Res')):
    p=read_patch(ROOT/f'presets/user/{name}.json')
    settings=np.array([p['parameters'][s.name] for s in MODEL_D_PARAMETERS],np.float32).astype(np.float64)
    lib.myxa_dry_init(index)
    with mock_patch('engine.build_library',return_value=reference):old=NativeVoice(48000,'modeld')
    try:
        for step in range(100):
            k=step%len(settings);spec=MODEL_D_PARAMETERS[k]
            value=float(rng.integers(spec.minimum,spec.maximum+1)) if spec.choices else spec.minimum+(spec.maximum-spec.minimum)*rng.random()
            settings[k]=value
            assert lib.myxa_dry_set_parameter(k,value)==0
            count=257
            pitch=np.full(count,49*2**((step%13)/12),np.float32)
            gate=np.full(count,step%5!=0,np.float32);trigger=np.zeros(count,np.float32);trigger[0]=step%3==0
            actual=np.zeros(count,np.float32);expected=actual.copy()
            lib.myxa_dry_process(pitch,gate,trigger,actual,count)
            old.process(expected,[pitch,gate,trigger,np.ones(count,np.float32),np.full(count,settings[23],np.float32)],settings,4)
            np.testing.assert_array_equal(actual,expected)
    finally:old.close()
print('Frozen-engine parity passed: all parameter updates, pitch/gates and active modulation.')
