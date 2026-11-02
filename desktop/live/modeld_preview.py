"""Rebuild factory examples and a deterministic, silent-to-device audition."""
import json
from pathlib import Path
import wave

import numpy as np

from engine import NativeVoice
from model import ROOT, ARCHITECTURES, MODEL_D_PARAMETERS, parameters_for, validate_patch


def factory():
    values={spec.name:spec.minimum for spec in MODEL_D_PARAMETERS}
    for oscillator in range(1,4):
        values.update({f'osc{oscillator}_wave':2,f'osc{oscillator}_octave':0,
                       f'osc{oscillator}_tune':0,f'osc{oscillator}_low':0})
    values.update(osc3_keyboard=1,osc3_fixed_hz=5,osc1_level=1,mixer_drive=1,
                  output_drive=1,cutoff_hz=12000,filter_env_octaves=0,
                  filter_decay_s=.2,amp_decay_s=.2,amp_sustain=1,
                  release_enabled=1,tune_cents=0,lfo_rate_hz=5,mod_source_2=1,
                  mod_mix=1,pitch_mod_depth=2,filter_mod_depth=2)
    init=validate_patch({'name':'Model D Init','architecture':'modeld','parameters':values})
    bass={**values,'osc2_level':.55,'osc2_tune':-.0344865,'osc3_wave':0,
          'osc3_octave':-1,'osc3_level':.15,'mixer_drive':2.5,'cutoff_hz':110,
          'resonance':.4,'filter_env_octaves':5.2,'filter_attack_s':.015,
          'filter_decay_s':.65,'filter_sustain':.018,'attack_s':.025,
          'amp_decay_s':.95,'amp_sustain':.062,'keytrack_1':1,'keytrack_2':1}
    patches={'init':init}
    for slug,name,parameters in (
        ('bass','Model D Bass — candidate',bass),
        ('pluck','Model D Pluck — candidate',{**bass,'filter_attack_s':.001,'filter_decay_s':.85}),
        ('modulation','Model D Modulation',{**values,'osc3_keyboard':0,'osc3_fixed_hz':5,
          'mod_source_1':0,'mod_mix':0,'mod_amount':.4,'pitch_mod_enabled':1,
          'pitch_mod_depth':.5,'cutoff_hz':2500,'resonance':.35})):
        patches[slug]=validate_patch({'name':name,'architecture':'modeld','parameters':parameters})
    return patches


def render(patch,blocksize=256,apply_output_gain=True):
    events=json.loads((ROOT/'baselines/bassline-v1/events.json').read_text())
    rate=48000
    frames=round(events[-1]['end']*rate)
    controls=[np.full(frames,49,dtype=np.float32),np.zeros(frames,dtype=np.float32),
              np.zeros(frames,dtype=np.float32),np.ones(frames,dtype=np.float32),
              np.full(frames,patch['parameters']['resonance'],dtype=np.float32)]
    for event in events:
        left=round(event['start']*rate)
        right=round(event['end']*rate)
        controls[0][left:right]=event['frequency']
        controls[1][left:max(left,right-1200)]=1
        controls[2][left]=1
    voice=NativeVoice(rate,'modeld' if patch['architecture']=='modeld' else 'bass')
    settings=np.array([patch['parameters'][spec.name] for spec in parameters_for(patch['architecture'])],dtype=np.float64)
    output=np.zeros(frames,dtype=np.float32)
    try:
        for start in range(0,frames,blocksize):
            end=min(frames,start+blocksize)
            voice.process(output[start:end],[control[start:end] for control in controls],settings,ARCHITECTURES[patch['architecture']])
    finally:
        voice.close()
    if apply_output_gain: output*=10**(patch.get('output_gain_db',0)/20)
    return output


def main():
    out=Path(__file__).parent/'outputs'
    out.mkdir(exist_ok=True)
    for slug,patch in factory().items():
        path=ROOT/f'presets/model-d-{slug}.json'
        # Preserve any existing factory candidate; never rewrite a user's edits.
        if not path.exists(): path.write_text(json.dumps(patch,indent=2)+'\n')
        if slug in ('bass','pluck'):
            audio=render(patch)
            gain=min(1,.7/max(1e-9,float(np.max(abs(audio)))))
            pcm=np.round(audio*gain*32767).astype('<i2')
            target=out/f'model-d-{slug}-candidate.wav'
            with wave.open(str(target),'wb') as handle:
                handle.setparams((1,2,48000,0,'NONE','not compressed'))
                handle.writeframes(pcm.tobytes())
            print(target)


if __name__=='__main__': main()
