"""Bounded Model D knob search; preserves every approved patch and factory preset."""
import hashlib
import json
from pathlib import Path
import sys
import time
import wave

import numpy as np
from scipy import optimize, signal

from engine import NativeVoice
from model import ROOT, MODEL_D_NAMES, read_patch, save_patch
from modeld_preview import render

sys.path.insert(0,str(ROOT/'desktop/matching'))
from analyze import load_audio
from mariana_fit import target_features, loss, audition_normalize


def main():
    directory=Path(__file__).parent/'outputs/modeld-fit'
    directory.mkdir(exist_ok=True)
    patch=read_patch(ROOT/'presets/model-d-bass.json')
    names=['cutoff_hz','filter_env_octaves','filter_decay_s','filter_attack_s',
           'resonance','mixer_drive','attack_s','amp_decay_s','amp_sustain']
    bounds=[(40,300),(3,7),(.12,1.5),(.001,.12),(.15,.9),(1,4),(.005,.13),(.25,1.5),(.02,.25)]
    events=json.loads((ROOT/'baselines/bassline-v1/events.json').read_text())
    mariana=load_audio(ROOT/'references/mariana/audio/Mariana_2.wav')
    approved=load_audio(ROOT/'baselines/bassline-v1/bassline-48k.wav')
    frames=min(len(mariana),len(approved))
    controls=[np.full(frames,49,dtype=np.float32),np.zeros(frames,dtype=np.float32),
              np.zeros(frames,dtype=np.float32),np.ones(frames,dtype=np.float32),
              np.zeros(frames,dtype=np.float32)]
    for event in events:
        left=round(event['start']*24000)
        right=min(frames,round(event['end']*24000))
        controls[0][left:right]=event['frequency']
        controls[1][left:max(left,right-600)]=1
        if left<frames: controls[2][left]=1
    sections=[slice(max(0,round((event['start']-.015)*24000)),
                    min(frames,round(min(event['end']-.01,event['start']+.75)*24000)))
              for event in events]
    reference=[target_features(mariana[section]) for section in sections]
    character=[target_features(approved[section]) for section in sections]
    train=[0,3,5,8,10]
    check=[1,2,4,6,7,9,11,12]
    voice=NativeVoice(24000,'modeld')
    output=np.zeros(frames,dtype=np.float32)
    settings=np.array([patch['parameters'][name] for name in MODEL_D_NAMES],dtype=np.float64)
    indices=[MODEL_D_NAMES.index(name) for name in names]
    history=[]

    def measure(values,notes):
        settings[indices]=values
        controls[4].fill(settings[MODEL_D_NAMES.index('resonance')])
        voice.reset()
        voice.process(output,controls,settings,3)
        scores=[]
        for index in notes:
            actual=target_features(output[sections[index]])
            scores.append(.65*loss(actual,reference[index])+.35*loss(actual,character[index]))
        return float(np.mean(scores))

    def objective(values):
        score=measure(values,train)
        history.append({'score':score,'values':list(values)})
        return score

    started=time.monotonic()
    initial=np.array([patch['parameters'][name] for name in names])
    initial_score=objective(initial)
    initial_check=measure(initial,check)
    try:
        optimize.differential_evolution(objective,bounds,x0=initial,seed=20261101,
                                        popsize=6,maxiter=9,polish=False)
        shortlist=sorted(history,key=lambda item:item['score'])[:12]
        for row in shortlist: row['check_score']=measure(row['values'],check)
        selected=min(shortlist,key=lambda item:item['check_score'])
        final={**patch,'name':'Model D Reference — candidate',
               'parameters':{**patch['parameters'],**dict(zip(names,selected['values']))}}
        # Exclusive save adds a suffix if this experiment is repeated.
        path=save_patch('Model D Reference — candidate',final,ROOT/'presets')
        destination=path
        audio=render(final)
        actual=audition_normalize(audio)
        baseline=audition_normalize(load_audio(ROOT/'baselines/bassline-v1/bassline-48k.wav',48000))
        target=audition_normalize(load_audio(ROOT/'references/mariana/audio/Mariana_2.wav',48000))
        for name,recording in (('model-d-reference-candidate',actual),
                 ('mariana-approved-model-d',np.concatenate([target,np.zeros(24000),baseline,np.zeros(24000),actual]))):
            with wave.open(str(directory/f'{name}.wav'),'wb') as handle:
                handle.setparams((1,2,48000,0,'NONE','not compressed'))
                handle.writeframes(np.round(recording*32767).astype('<i2').tobytes())
        report={'status':'Numerically tuned listening candidate; user approval pending',
                'seed':20261101,'trials':len(history),'seconds':time.monotonic()-started,
                'initial_training_score':initial_score,'initial_check_score':initial_check,
                'selected':selected,'mutable_parameters':names,'bounds':bounds,
                'training_notes':train,'check_notes':check,'preset':str(destination),
                'weighting':{'mariana':.65,'approved_character':.35},
                'limitations':['Metric is not perceptual proof. No baseline promotion.',
                              'Same recordings used for development; check notes are not independent recordings.',
                              '24 kHz search, final 48 kHz render; estimated gates.'],
                'source_sha256':hashlib.sha256((Path(__file__).parent/'native/modeld.c').read_bytes()).hexdigest()}
        (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        (directory/'trials.json').write_text(json.dumps(history,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally: voice.close()


if __name__=='__main__': main()
