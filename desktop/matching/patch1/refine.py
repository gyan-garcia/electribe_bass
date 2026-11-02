import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from scipy import optimize, signal

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from analyze import load_audio
from fit import Renderer, NAMES, save_wav
from mariana_fit import EXTENDED_NAMES, audition_normalize, target_features, loss

SOURCE=HERE/'voice-snapshot.c'
MARIANA=HERE.parents[2]/'references/mariana/audio/Mariana_2.wav'
TINASHE=HERE.parents[2]/'references/tinashe/audio/Tinashe_bass.wav'
FILTER_INDICES=[4,5,6,17,18,19,21]
BOUNDS=[(40,240),(2.5,6.5),(.06,.6),(.0005,.045),(0,.2),(.5,2.5),(0,1)]
TRAIN=[0,3,5,8,10]
SELECT=[1,4,6,9]
AUDIT=[2,7,11,12]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seed',type=int,default=20261106)
    parser.add_argument('--coarse-iterations',type=int,default=20)
    parser.add_argument('--refine-iterations',type=int,default=20)
    args=parser.parse_args()
    subprocess.run(['gcc','-O3','-shared','-fPIC',str(SOURCE),'-lm','-o',str(HERE/'voice.so')],check=True)
    settings=json.loads((HERE/'preferred-patch.json').read_text())['selected']['parameters']
    baseline=np.array([settings[name] for name in NAMES]+[0,settings['attack_s'],0,1,0,0,0])
    events=json.loads((HERE.parent/'mariana/events.json').read_text())
    mariana=load_audio(MARIANA)
    tinashe=load_audio(TINASHE)[:round(1.4*24000)]
    renderer=Renderer(events,library_path=HERE/'voice.so',function_name='render_rubber_voice')
    controls=renderer.controls(0,len(mariana)/24000)
    tinashe_events=json.loads((HERE.parent/'analysis.json').read_text())['events']
    other=Renderer(tinashe_events,library_path=HERE/'voice.so',function_name='render_rubber_voice')
    other_controls=other.controls(0,1.4)
    old_audio=renderer.render(baseline,0,controls)
    old_other=other.render(baseline,0,other_controls)
    reference_features={}
    old_features={}
    slices={}
    for index,event in enumerate(events):
        start=max(0,event['start']-.015)
        end=min(event['end']-.01,start+1.0)
        section=slice(round(start*24000),round(end*24000))
        slices[index]=section
        reference_features[index]=target_features(mariana[section])
        old_features[index]=target_features(old_audio[section])
    other_target=target_features(tinashe[2400:])
    frozen=[index for index in range(23) if index not in FILTER_INDICES]
    def check_frozen(candidate):
        if not np.array_equal(candidate[frozen],baseline[frozen]):
            raise ValueError('Frozen preferred sound parameters changed')
    def measure(audio,indices):
        errors=[]
        character=[]
        for index in indices:
            actual=target_features(audio[slices[index]])
            errors.append(loss(actual,reference_features[index]))
            character.append(float(np.mean([np.mean(abs(left-right)) for left,right in zip(actual[0],old_features[index][0])])) )
        return float(np.mean(errors)),float(np.mean(character))
    baseline_train=measure(old_audio,TRAIN)[0]
    baseline_select=measure(old_audio,SELECT)[0]
    baseline_audit=measure(old_audio,AUDIT)[0]
    baseline_other=loss(target_features(old_other[2400:]),other_target)
    cache={}
    records=[]
    started=time.monotonic()
    log=(HERE/'trials.jsonl').open('w')
    def expand(values):
        candidate=baseline.copy()
        candidate[FILTER_INDICES]=values
        check_frozen(candidate)
        return candidate
    def objective(values):
        key=tuple(values)
        if key in cache:
            return cache[key]['loss']
        candidate=expand(values)
        audio=renderer.render(candidate,0,controls)
        if np.max(abs(audio))>1.5 or np.std(audio)<1e-5:
            return 100.0
        fit,character=measure(audio,TRAIN)
        other_audio=other.render(candidate,0,other_controls)
        other_loss=loss(target_features(other_audio[2400:]),other_target)
        error=.70*fit+.20*other_loss+.10*character
        row={'trial':len(records)+1,'loss':error,'mariana_train':fit,
             'tinashe_intro':other_loss,'preferred_character_change':character,'values':list(values)}
        records.append(row)
        cache[key]=row
        log.write(json.dumps(row)+'\n')
        log.flush()
        if len(records)%200==0:
            print('trials',len(records),'best',min(item['loss'] for item in records),flush=True)
        return error
    starting=baseline[FILTER_INDICES]
    objective(starting)
    callbacks=[]
    def stop_on_plateau(values,convergence):
        callbacks.append(objective(values))
        return len(callbacks)>8 and callbacks[-1]>=callbacks[-9]*.998
    active=[0,1,2,3]
    def coarse(values):
        extended=starting.copy()
        extended[active]=values
        return objective(extended)
    coarse_start=starting[active]
    coarse_start[3]=.003
    first=optimize.differential_evolution(coarse,[BOUNDS[index] for index in active],
                x0=coarse_start,seed=args.seed,maxiter=args.coarse_iterations,popsize=8,polish=False)
    current=starting.copy()
    current[active]=first.x
    print('Coarse filter fit complete',first.fun,flush=True)
    rng=np.random.default_rng(args.seed+1)
    lower,upper=np.array(BOUNDS).T
    population=np.clip(current+rng.normal(0,.12,(64,7))*(upper-lower),lower,upper)
    population[-16:]=rng.uniform(lower,upper,(16,7))
    second=optimize.differential_evolution(objective,BOUNDS,x0=current,seed=args.seed+1,
                maxiter=args.refine_iterations,popsize=8,polish=False,init=population,
                callback=stop_on_plateau,tol=.001)
    print('Envelope-shape fit complete',second.fun,flush=True)
    optimize.minimize(objective,second.x,method='Powell',bounds=BOUNDS,
                      options={'maxfev':400,'maxiter':4,'ftol':.001,'xtol':.002})
    ranked=sorted(records,key=lambda row:row['loss'])
    shortlist=[]
    for row in ranked:
        values=np.array(row['values'])
        if any(np.linalg.norm((values-np.array(old['values']))/(upper-lower))<.04 for old in shortlist):
            continue
        candidate=expand(values)
        audio=renderer.render(candidate,0,controls)
        validation,character=measure(audio,SELECT)
        row={**row,'selection_loss':validation,'selection_character_change':character}
        shortlist.append(row)
        if len(shortlist)>=16:
            break
    champion=min(shortlist,key=lambda row:row['selection_loss']+.10*row['selection_character_change'])
    best=expand(champion['values'])
    gentle=baseline.copy()
    gentle[FILTER_INDICES]=(baseline[FILTER_INDICES]+best[FILTER_INDICES])/2
    gentle[4]=np.sqrt(baseline[4]*best[4])
    final_renderer=Renderer(events,48000,HERE/'voice.so','render_rubber_voice')
    final_controls=final_renderer.controls(0,len(mariana)/24000)
    outputs={}
    audition={}
    for name,candidate in [('preferred',baseline),('refined',best),('gentle',gentle)]:
        check_frozen(candidate)
        high=final_renderer.render(candidate,0,final_controls)
        down=signal.resample_poly(high,1,2)
        aligned=audition_normalize(down)
        save_wav(HERE/f'{name}-same-phrase.wav',aligned,24000)
        if name!='preferred':
            save_wav(HERE/f'{name}-48k.wav',high,48000)
        audition[name]=aligned
        audit,change=measure(down,AUDIT)
        outputs[name]={'audit_loss':audit,'audit_character_change':change,
                       'whole_phrase_loss':loss(target_features(down),target_features(mariana)),
                       'parameters':dict(zip(EXTENDED_NAMES,candidate.tolist()))}
    pause=np.zeros(12000)
    reference=audition_normalize(mariana)
    for name in ('refined','gentle'):
        comparison=np.concatenate([reference,pause,audition[name]])
        save_wav(HERE/f'mariana-then-{name}.wav',comparison,24000)
    comparison=np.concatenate([audition['preferred'],pause,audition['refined'],pause,audition['gentle']])
    save_wav(HERE/'preferred-refined-gentle.wav',comparison,24000)
    save_wav(HERE/'refined-preview.wav',audition['refined'][:round(9.7*24000)],24000)
    save_wav(HERE/'gentle-preview.wav',audition['gentle'][:round(9.7*24000)],24000)
    log.close()
    report={'status':'listening candidates; perceptual match unconfirmed','seed':args.seed,
            'trials':len(records),'seconds':time.monotonic()-started,'architecture':'svf12',
            'mutable_parameters':[EXTENDED_NAMES[index] for index in FILTER_INDICES],
            'frozen_parameters':[EXTENDED_NAMES[index] for index in frozen],
            'baseline_training_loss':baseline_train,'baseline_selection_loss':baseline_select,
            'baseline_audit_loss':baseline_audit,'baseline_tinashe_intro_loss':baseline_other,
            'training_notes':TRAIN,'selection_notes':SELECT,'audit_notes':AUDIT,
            'shortlist':shortlist,'champion':champion,'outputs':outputs,
            'reference_hashes':{str(path.name):hashlib.sha256(path.read_bytes()).hexdigest() for path in (MARIANA,TINASHE)},
            'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'limitations':['User listening preference cannot be inferred from error alone.',
                           'Timing/gates estimated; final G1 retrigger inferred from audio.',
                           'Same recordings used for development; not a generalization test.',
                           'Tinashe intro check only covers 1.3 seconds, not the full song.',
                           'Envelope timing parameters are time constants, not exact stage lengths.',
                           'Desktop floating-point render, no hardware performance validation.']}
    (HERE/'report.json').write_text(json.dumps(report,indent=2))
    for name,values in outputs.items():
        preset={'format':'electribe-desktop-patch-v1','architecture':'svf12',
                'parameters':values['parameters'],'engine_source':'voice-snapshot.c',
                'engine_sha256':report['source_sha256'],'note_events':'../mariana/events.json',
                'status':'listening candidate, not an approved final patch'}
        (HERE/f'{name}-preset.json').write_text(json.dumps(preset,indent=2))
        print(name,'full',values['whole_phrase_loss'],'audit',values['audit_loss'],flush=True)
    print('Done',len(records),'candidates',flush=True)


if __name__=='__main__':
    main()
