"""Fit existing Model D knobs to the Mariana recording, emphasizing moving timbre.

No engine changes, sampled audio in the voice, or baseline promotion. Every run
has its own directory; candidate presets use exclusive names.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import wave

import numpy as np
from scipy import optimize, signal
import scipy

from engine import NativeVoice
from model import ROOT, MODEL_D_NAMES, read_patch, save_patch
from modeld_preview import render

sys.path.insert(0,str(ROOT/'desktop/matching'))
from analyze import load_audio
from mariana_fit import target_features, loss, audition_normalize

NAMES=['cutoff_hz','filter_env_octaves','filter_decay_s','filter_attack_s',
       'filter_sustain','resonance','mixer_drive','osc2_level','osc3_level',
       'osc2_tune','attack_s','amp_decay_s','amp_sustain','glide_s','feedback_level']
BOUNDS=[(30,500),(2,8),(.08,3),(.0002,.12),(0,.15),(.15,1.05),(.2,4),
        (0,1),(0,.4),(-.15,.15),(.001,.12),(.12,2),(.01,.3),(.0001,.03),(0,.5)]
LOG={0,2,3,6,10,11,13}
TRAIN=[0,3,5,8,10]
CHECK=[1,2,4,6,7,9,11,12]


def features(audio):
    original=target_features(audio)
    normalized=audio/max(1e-9,np.sqrt(np.mean(audio.astype(np.float64)**2)))
    frequency,times,transform=signal.stft(normalized,24000,nperseg=1024,noverlap=904,nfft=2048)
    power=abs(transform)**2
    edges=[25,80,160,320,640,1280,2560,5120,9000]
    bands=np.array([np.sqrt(power[(frequency>=low)&(frequency<high)].sum(axis=0)+1e-12)
                    for low,high in zip(edges[:-1],edges[1:])])
    bands=np.log1p(20*bands)
    colour=bands-bands.mean(axis=0)
    weights=np.where(times<.38,1.0,.3)
    weights/=weights.mean()
    return original,colour,weights


def distance(actual,target):
    broad=loss(actual[0],target[0])
    movement=float(np.mean(abs(actual[1]-target[1])*target[2]))
    motion=float(np.mean(abs(np.diff(actual[1],axis=1)-np.diff(target[1],axis=1))))
    return .55*broad+.35*movement+.10*motion


def write_wav(path,audio):
    with wave.open(str(path),'wb') as handle:
        handle.setparams((1,2,48000,0,'NONE','not compressed'))
        handle.writeframes(np.round(np.clip(audio,-.98,.98)*32767).astype('<i2').tobytes())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--iterations',type=int,default=16)
    parser.add_argument('--seed',type=int,default=20261102)
    parser.add_argument('--start-patch',type=Path,default=ROOT/'presets/model-d-reference-candidate.json')
    parser.add_argument('--resonant',action='store_true',help='Constrain a contrasting lower-drive, higher-emphasis audition')
    parser.add_argument('--local-only',action='store_true',help='Refine an existing candidate without a new waveform search')
    parser.add_argument('--label',default='Model D Rubber v2')
    args=parser.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory=Path(__file__).parent/'outputs'/f'modeld-rubber-{stamp}'
    directory.mkdir()
    source=Path(__file__).parent/'native/modeld.c'
    previous_path=args.start_patch
    previous=read_patch(previous_path)
    immutable=[ROOT/'baselines/bassline-v1/preset.json',ROOT/'baselines/bassline-v1/voice.c',
               ROOT/'presets/bassline-pluck.json',previous_path,source]
    hashes={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in immutable}
    events=json.loads((ROOT/'baselines/bassline-v1/events.json').read_text())
    reference=load_audio(ROOT/'references/mariana/audio/Mariana_2.wav')
    frames=len(reference)
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
                    min(frames,round(min(event['end']-.01,event['start']+.7)*24000)))
              for event in events]
    targets=[features(reference[section]) for section in sections]
    train_frames=max(sections[index].stop for index in TRAIN)
    voice=NativeVoice(24000,'modeld')
    output=np.zeros(frames,dtype=np.float32)
    indices=[MODEL_D_NAMES.index(name) for name in NAMES]
    limits=np.array(BOUNDS,dtype=float)
    if args.local_only:
        limits[4]=(0,.3)
        limits[8]=(0,.65)
        limits[12]=(.01,.75)
    if args.resonant:
        limits[5]=(.55,.95)
        limits[6]=(.2,1.2)
        limits[14]=(0,.2)
    for index in LOG: limits[index]=np.log(limits[index])
    history=[]
    log=(directory/'trials.jsonl').open('x')
    started=time.monotonic()

    def encode(parameters):
        values=np.array([parameters[name] for name in NAMES])
        for index in LOG: values[index]=np.log(max(BOUNDS[index][0],values[index]))
        margin=1e-9*(limits[:,1]-limits[:,0])
        return np.clip(values,limits[:,0]+margin,limits[:,1]-margin)

    def decode(values):
        values=np.array(values,copy=True)
        for index in LOG: values[index]=np.exp(values[index])
        return dict(zip(NAMES,values.tolist()))

    def measure(parameters,notes,rate=24000):
        settings=np.array([parameters[name] for name in MODEL_D_NAMES],dtype=np.float64)
        controls[4].fill(parameters['resonance'])
        voice.reset()
        end=train_frames if notes==TRAIN else frames
        voice.process(output[:end],[control[:end] for control in controls],settings,3)
        if not np.isfinite(output[:end]).all() or np.std(output[:end])<1e-6: return 100.
        return float(np.mean([distance(features(output[sections[index]]),targets[index]) for index in notes]))

    def evaluate(values,base,label):
        parameters={**base,**decode(values)}
        score=measure(parameters,TRAIN)
        row={'trial':len(history)+1,'stage':label,'score':score,'parameters':parameters}
        history.append(row)
        log.write(json.dumps(row)+'\n')
        if len(history)%200==0:
            log.flush()
            print('trials',len(history),'best',round(min(row['score'] for row in history),6),
                  'seconds',round(time.monotonic()-started),flush=True)
        return score

    try:
        old=previous['parameters']
        old_train=measure(old,TRAIN)
        old_check=measure(old,CHECK)
        print('Previous candidate',old_train,old_check,flush=True)
        # A stronger resonance can be masked by an overdriven mixer. Scan both,
        # as well as oscillator spectra, before optimizing contour trajectories.
        for wave1,wave2 in (() if args.local_only else ((2,2),(2,3),(3,2),(1,2),(2,0),(3,3))):
            base={**old,'osc1_wave':wave1,'osc2_wave':wave2}
            for emphasis in (.35,.65,.9):
                for drive in (.4,1.,2.5):
                    parameters={**base,'resonance':emphasis,'mixer_drive':drive}
                    evaluate(encode(parameters),base,'spectrum scan')
        if args.local_only: evaluate(encode(old),old,'local starting point')
        starters=[]
        for row in sorted(history,key=lambda row:row['score']):
            shapes=(row['parameters']['osc1_wave'],row['parameters']['osc2_wave'])
            if any((entry['osc1_wave'],entry['osc2_wave'])==shapes for entry in starters): continue
            starters.append(row['parameters'])
            if len(starters)==(1 if args.resonant else 2): break
        for branch,base in enumerate(starters):
            if args.local_only: break
            random=np.random.default_rng(args.seed+branch)
            start=encode(base)
            population_size=60 if args.resonant else 90
            population=np.clip(start+random.normal(0,.12,(population_size,len(NAMES)))*(limits[:,1]-limits[:,0]),
                               limits[:,0],limits[:,1])
            population[-20:]=random.uniform(limits[:,0],limits[:,1],(20,len(NAMES)))
            print('Optimizing waveforms',base['osc1_wave'],base['osc2_wave'],flush=True)
            optimize.differential_evolution(lambda values:evaluate(values,base,f'joint {branch}'),
                limits,x0=start,seed=args.seed+branch,maxiter=args.iterations,init=population,
                polish=False,tol=.0005)
        best=min(history,key=lambda row:row['score'])
        optimize.minimize(lambda values:evaluate(values,best['parameters'],'local refinement'),
            encode(best['parameters']),method='Powell',bounds=limits,
            options={'maxfev':1000 if args.local_only else 450,'maxiter':5 if args.local_only else 3,
                     'ftol':.0002,'xtol':.002})
        # Check discrete keyboard tracking choices using the strongest timbres.
        for row in sorted(history,key=lambda row:row['score'])[:8]:
            for key1,key2 in ((0,0),(1,0),(0,1),(1,1)):
                base={**row['parameters'],'keytrack_1':key1,'keytrack_2':key2}
                evaluate(encode(base),base,'tracking check')
        shortlist=[]
        for row in sorted(history,key=lambda row:row['score']):
            values=encode(row['parameters'])
            if any(np.linalg.norm((values-encode(entry['parameters']))/(limits[:,1]-limits[:,0]))<.065
                   and row['parameters']['osc1_wave']==entry['parameters']['osc1_wave']
                   and row['parameters']['osc2_wave']==entry['parameters']['osc2_wave']
                   and row['parameters']['keytrack_1']==entry['parameters']['keytrack_1']
                   and row['parameters']['keytrack_2']==entry['parameters']['keytrack_2'] for entry in shortlist): continue
            row['check_score']=measure(row['parameters'],CHECK)
            shortlist.append(row)
            if len(shortlist)==20: break
        finalists=sorted(shortlist,key=lambda row:.4*row['score']+.6*row['check_score'])
        selected=[]
        for row in finalists:
            if selected and np.linalg.norm((encode(row['parameters'])-encode(selected[0]['parameters']))/
                                           (limits[:,1]-limits[:,0]))<.12: continue
            selected.append(row)
            if len(selected)==3: break
        target48=load_audio(ROOT/'references/mariana/audio/Mariana_2.wav',48000)
        previous48=render(previous)
        clips={'mariana':target48,'previous':previous48}
        for index,row in enumerate(selected):
            name=args.label+('' if index==0 else f' alternative {index}')
            if args.resonant: name='Model D Rubber Resonant'+('' if index==0 else f' alternative {index}')
            patch={**previous,'name':name,'parameters':row['parameters']}
            path=save_patch(name,patch,ROOT/'presets')
            row['preset']=str(path)
            audio=render(patch)
            clips[f'candidate-{index+1}']=audio
            # Evaluate the final 48 kHz render after downsampling, not just search rate.
            down=signal.resample_poly(audio,1,2)[:frames]
            row['final_48k_score']=float(np.mean([distance(features(down[section]),target)
                                                for section,target in zip(sections,targets)]))
            write_wav(directory/f'candidate-{index+1}.wav',audition_normalize(audio))
        normalized={name:audition_normalize(audio) for name,audio in clips.items()}
        pause=np.zeros(24000)
        write_wav(directory/'mariana-previous-rubber.wav',np.concatenate([
            normalized['mariana'],pause,normalized['previous'],pause,normalized['candidate-1']]))
        # Short repeated G1 comparisons make contour differences easier to hear.
        section=slice(round(.45*48000),round(3.18*48000))
        names=['mariana','previous']+[f'candidate-{index+1}' for index in range(len(selected))]
        write_wav(directory/'rubber-short-comparison.wav',np.concatenate([
            np.r_[normalized[name][section],pause] for name in names]))
        for path in immutable:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=hashes[str(path)]:
                raise RuntimeError('Protected file changed: '+str(path))
        report={'status':'Listening candidates; no automatic approval or baseline change',
                'seed':args.seed,'iterations_per_waveform':args.iterations,'trials':len(history),
                'seconds':time.monotonic()-started,'previous_train':old_train,'previous_check':old_check,
                'selected':selected,'shortlist':shortlist,'mutable_parameters':NAMES,
                'bounds':[(np.exp(row) if index in LOG else row).tolist() for index,row in enumerate(limits)],
                'resonant_variant':args.resonant,'train_notes':TRAIN,'check_notes':CHECK,
                'local_only':args.local_only,'start_preset':str(previous_path),
                'objective':'Mariana only; multiscale spectra + early moving band colour and trajectory',
                'unchanged_hashes':hashes,'reference_sha256':hashlib.sha256(
                    (ROOT/'references/mariana/audio/Mariana_2.wav').read_bytes()).hexdigest(),
                'versions':{'numpy':np.__version__,'scipy':scipy.__version__},
                'limitations':['No subjective listening judgment by the assistant.',
                               'Estimated gates; same recording for search and check notes.',
                               '24 kHz search; final 48 kHz rendered and checked separately.',
                               'Model D signal path unchanged; no firmware changes.']}
        (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        (directory/'previous-patch.json').write_text(json.dumps(previous,indent=2)+'\n')
        (directory/'source-snapshot.c').write_bytes(source.read_bytes())
        (directory/'search-snapshot.py').write_bytes(Path(__file__).read_bytes())
        print('DONE',directory,flush=True)
        print('previous check',old_check,'new check',selected[0]['check_score'],flush=True)
    finally:
        log.close()
        voice.close()


if __name__=='__main__': main()
