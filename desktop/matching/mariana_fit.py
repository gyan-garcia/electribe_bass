import argparse
import hashlib
import json
import subprocess
import time

import numpy as np
from scipy import optimize, signal

from analyze import ROOT, load_audio
from fit import NAMES, ARCHITECTURES, Renderer, save_wav

DEST = ROOT/'mariana'
REFERENCE = ROOT.parents[1]/'references/mariana/audio/Mariana_2.wav'
EXTENDED_NAMES = NAMES + ['tune_cents','filter_attack_s','filter_sustain',
                         'filter_curve','pulse_env_depth','filter_key_tracking','resonance_env_depth']
INDICES = [0,1,2,3,4,5,6,7,8,9,10,11,12,16,17,18,19,20,21,22]
BOUNDS = [(0,1),(.12,.88),(-10,10),(0,.6),(40,1800),(0,7),(.035,.65),
          (.0005,.015),(.04,.8),(0,.9),(.02,.4),(0,.94),(.4,3.8),
          (-30,10),(.0003,.04),(0,.4),(.4,2.3),(-.35,.35),(0,1.2),(-.35,.5)]


def target_features(audio):
    audio=audio/max(1e-8,np.sqrt(np.mean(audio.astype(np.float64)**2)))
    spectra=[]
    for window in (512,2048):
        frequency,_,transformed=signal.stft(audio,24000,nperseg=window,noverlap=window-window//4)
        magnitude=abs(transformed)
        mask=(frequency>=22)&(frequency<=8000)
        spectra.append(np.log1p(30*magnitude[mask]))
    power=magnitude**2
    low=power[(frequency>=22)&(frequency<400)].sum(axis=0)
    high=power[(frequency>=400)&(frequency<=8000)].sum(axis=0)
    brightness=np.log1p(100*high/(low+.001))
    centroid=np.log1p((magnitude[mask]*frequency[mask,None]).sum(axis=0)/(magnitude[mask].sum(axis=0)+1e-8))/8
    blocks=len(audio)//240
    envelope=np.log1p(4*np.sqrt(np.mean(audio[:blocks*240].reshape(blocks,240)**2,axis=1)))
    balance=float(np.log10((high.sum()+1e-8)/(low.sum()+1e-8)))
    return spectra,envelope,brightness,centroid,balance


def loss(actual,target):
    spectral=np.mean([np.mean(abs(left-right)) for left,right in zip(actual[0],target[0])])
    return float(spectral+.12*np.mean(abs(actual[1]-target[1]))
                 +.05*np.mean(abs(actual[2]-target[2]))
                 +.12*np.mean(abs(actual[3]-target[3]))
                 +.20*abs(actual[4]-target[4]))


def make_events(audio):
    _,times,transformed=signal.stft(audio,24000,nperseg=512,noverlap=272)
    flux=np.r_[0,np.maximum(0,np.diff(np.log1p(abs(transformed)*100),axis=1)).mean(axis=0)]
    peaks,_=signal.find_peaks(flux,distance=45,prominence=.035)
    starts=[max(0,float(times[peak])-.01) for peak in peaks if times[peak]<10]
    notes=[31,31,31,32,29,36,37,34,24,25,22,31]
    if len(starts)!=len(notes):
        raise ValueError(f'Expected {len(notes)} clear attacks, detected {starts}')
    events=[]
    for index,(start,midi) in enumerate(zip(starts,notes)):
        end=starts[index+1] if index+1<len(starts) else len(audio)/24000
        events.append({'start':start,'end':end,'midi':midi,'frequency':440*2**((midi-69)/12)})
    later=[float(times[peak])-.01 for peak in peaks if times[peak]>10]
    if later:
        events[-1]['end']=later[0]
        events.append({**events[-1],'start':later[0],'end':len(audio)/24000})
    return events


def controls_for(renderer,start,duration,fraction):
    pitch,_,trigger=renderer.controls(start,duration)
    gate=np.zeros(len(pitch),dtype=np.float32)
    for event in renderer.events:
        begin=max(0,round((event['start']-start)*renderer.rate))
        stop=min(len(pitch),round((event['start']+(event['end']-event['start'])*fraction-start)*renderer.rate))
        if stop>begin:
            gate[begin:stop]=1
    return pitch,gate,trigger


def audition_normalize(audio):
    return audio*min(.13/max(1e-8,np.sqrt(np.mean(audio**2))),.86/max(1e-8,np.max(abs(audio))))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--iterations',type=int,default=16)
    parser.add_argument('--seed',type=int,default=20261104)
    parser.add_argument('--warm-start')
    args=parser.parse_args()
    DEST.mkdir(exist_ok=True)
    subprocess.run(['gcc','-O3','-shared','-fPIC',str(ROOT/'voice.c'),'-lm','-o',str(DEST/'rubber.so')],check=True)
    audio=load_audio(REFERENCE)
    events=make_events(audio)
    (DEST/'events.json').write_text(json.dumps(events,indent=2))
    renderer=Renderer(events,library_path=DEST/'rubber.so',function_name='render_rubber_voice')
    previous=json.loads((ROOT/'report.json').read_text())
    baseline=np.array([previous['selected']['parameters'][name] for name in NAMES]+[0,previous['selected']['parameters']['attack_s'],0,1,0,0,0])
    initial=baseline.copy()
    initial[7]=.003
    initial[16:]=[-8,.002,.05,1,0,.35,0]
    train_indices=[0,2,5,8,10]
    validation_indices=[1,3,4,6,7,9,11]
    def prepare(indices):
        windows=[]
        for index in indices:
            start=max(0,events[index]['start']-.025)
            duration=min(.64,events[index]['end']-start-.01)
            target=audio[round(start*24000):round((start+duration)*24000)]
            windows.append((start,len(target)/24000,target_features(target)))
        return windows
    training,validation=prepare(train_indices),prepare(validation_indices)
    baseline_control=renderer.controls(0,len(audio)/24000)
    baseline_audio=renderer.render(baseline,0,baseline_control)
    save_wav(DEST/'previous-patch-same-notes.wav',baseline_audio,24000)
    trials=0
    results=[]
    warm=json.load(open(args.warm_start)) if args.warm_start else []
    started=time.monotonic()
    with (DEST/'trials.jsonl').open('w') as log:
        for architecture in range(3):
            current=initial.copy()
            fraction=.85
            if warm:
                current=np.array([warm[architecture]['parameters'][name] for name in EXTENDED_NAMES])
                fraction=warm[architecture]['gate_fraction']
            bounds=BOUNDS+[(.5,.98)]
            starting=np.r_[current[INDICES],fraction]
            def evaluate(settings,fraction,windows):
                errors=[]
                for start,duration,target in windows:
                    controls=controls_for(renderer,start,duration,fraction)
                    rendered=renderer.render(settings,architecture,controls)
                    if np.max(abs(rendered))>1.5 or np.std(rendered)<1e-5:
                        return 100.0
                    errors.append(loss(target_features(rendered),target))
                return float(np.mean(errors))
            baseline_score=evaluate(baseline,.96,validation)
            def objective(values):
                nonlocal trials
                settings=current.copy()
                settings[INDICES]=values[:-1]
                error=evaluate(settings,values[-1],training)
                trials+=1
                log.write(json.dumps({'trial':trials,'architecture':ARCHITECTURES[architecture],
                                      'loss':error,'values':values.tolist()})+'\n')
                log.flush()
                return error
            population='latinhypercube'
            if warm:
                rng=np.random.default_rng(args.seed+architecture)
                lower,upper=np.array(bounds).T
                population=np.clip(starting+rng.normal(0,.08,(64,len(bounds)))*(upper-lower),lower,upper)
                population[-12:]=rng.uniform(lower,upper,(12,len(bounds)))
            optimized=optimize.differential_evolution(objective,bounds,x0=starting,
                        seed=args.seed+architecture,maxiter=args.iterations,popsize=3,
                        polish=False,tol=.001,init=population)
            settings=current.copy()
            settings[INDICES]=optimized.x[:-1]
            fraction=float(optimized.x[-1])
            error=evaluate(settings,fraction,validation)
            current_error=evaluate(current,warm[architecture]['gate_fraction'],validation) if warm else None
            if warm and error>current_error:
                settings=current
                fraction=warm[architecture]['gate_fraction']
                error=current_error
            item={'architecture':ARCHITECTURES[architecture],'architecture_index':architecture,
                  'training_loss':evaluate(settings,fraction,training),'validation_loss':error,
                  'previous_patch_validation_loss':baseline_score,'gate_fraction':fraction,
                  'parameters':dict(zip(EXTENDED_NAMES,settings.tolist()))}
            results.append(item)
            (DEST/'architectures.json').write_text(json.dumps(results,indent=2))
            print(item['architecture'],'training',item['training_loss'],'validation',error,flush=True)
    best=min(results,key=lambda item:item['validation_loss'])
    settings=np.array([best['parameters'][name] for name in EXTENDED_NAMES])
    final_renderer=Renderer(events,48000,DEST/'rubber.so','render_rubber_voice')
    controls=controls_for(final_renderer,0,len(audio)/24000,best['gate_fraction'])
    rendered=final_renderer.render(settings,best['architecture_index'],controls)
    save_wav(DEST/'rubber-bass.wav',rendered,48000)
    candidate=signal.resample_poly(rendered,1,2)
    silence=np.zeros(12000)
    comparison=np.concatenate([audition_normalize(audio),silence,audition_normalize(candidate)])
    save_wav(DEST/'mariana-then-synth.wav',comparison,24000)
    save_wav(DEST/'rubber-preview.wav',audition_normalize(candidate)[:round(9.7*24000)],24000)
    overall_previous=loss(target_features(baseline_audio),target_features(audio))
    overall_new=loss(target_features(candidate),target_features(audio))
    report={'status':'listening candidate, match unconfirmed','trials':trials,'seed':args.seed,
            'metric_version':'mariana-brightness-v2',
            'iterations':args.iterations,'warm_start':args.warm_start,'seconds':time.monotonic()-started,
            'reference_sha256':hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
            'previous_patch_parameters':dict(zip(EXTENDED_NAMES,baseline.tolist())),
            'voice_source_sha256':hashlib.sha256((ROOT/'voice.c').read_bytes()).hexdigest(),
            'note_sequence_user':[31,31,31,32,29,36,37,34,24,25,22,31],
            'extra_retrigger':'A further G1 attack near 11.1 s is detected in the recording.',
            'training_note_indices':train_indices,'selection_note_indices':validation_indices,
            'architectures':results,'selected':best,
            'full_recording_loss_previous':overall_previous,'full_recording_loss_new':overall_new,
            'limitations':['Gate lengths and exact onset times estimated.',
                           'Selection excerpts reused for architecture selection.',
                           'Mono comparison; Mariana effects/stereo not reconstructed.',
                           'Additional controls are hypotheses, not recovered preset settings.',
                           'Desktop only; fixed-point port and hardware performance untested.']}
    (DEST/'report.json').write_text(json.dumps(report,indent=2))
    print('Full recording loss:',overall_previous,'->',overall_new,flush=True)


if __name__=='__main__':
    main()
