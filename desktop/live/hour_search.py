"""One-hour isolated architecture search; exports replayable top-ten bundles."""
import argparse, ctypes, hashlib, html, json, os, subprocess, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from scipy import signal
import engine
from engine import NativeVoice
from model import ROOT, MODEL_D_NAMES, read_patch
from refine_modeld_rubber import features, distance, load_audio, audition_normalize, write_wav

TRAIN=[0,3,5,8,10]
CHECK=[1,4,6,9]
AUDIT=[2,7,11,12]
NAMES=['cutoff_hz','resonance','filter_env_octaves','filter_attack_s','filter_decay_s','filter_sustain',
       'mixer_drive','feedback_level','osc1_level','osc2_level','osc3_level','osc2_tune',
       'attack_s','amp_decay_s','amp_sustain','glide_s']
BOUNDS=np.array([(25,600),(.1,1.05),(1,8),(.0002,.15),(.08,3),(0,.35),(.2,4),(0,.6),
                 (.3,1),(0,1),(0,1),(-.12,.12),(.0005,.12),(.1,3),(.01,.8),(.0001,.04)],float)
LOG=[0,3,4,6,12,13,15]

SVF='''static float ladder(ModelDState *state,float input,float coefficient,float resonance,int highpass) {
    float g=coefficient/(1-coefficient);
    float k=fmaxf(.045f,2.0f-1.82f*resonance);
    float value=INPUT;
    for(int stage=0;stage<STAGES;stage++) {
        float *s=&state->poles[stage*2];
        float v1=(s[0]+g*(value-s[1]))/(1+g*(g+k));
        float v2=s[1]+g*v1;
        s[0]=STATE1; s[1]=STATE2;
        value=highpass ? value-k*v1-v2 : v2;
    }
    return value;
}

'''

def architectures(source):
    variants={'ladder24-original':source}
    variants['ladder12-tap']=source.replace(': taps[3];',': taps[1];')
    variants['ladder18-tap']=source.replace(': taps[3];',': taps[2];')
    variants['ladder24-stage-soft']=source.replace('state->poles[stage]=value+difference;',
                                                'state->poles[stage]=saturate(value+difference);')
    variants['ladder24-tanh']=source.replace('saturate(argument)','tanhf(argument)').replace(
        'slope(argument)','(1.0f-tanhf(argument)*tanhf(argument))')
    a=source.index('    for (int iteration=0;iteration<3;iteration++)')
    b=source.index('    float original=value;',a)
    linear=source[:a]+source[b:]
    variants['ladder24-linear-feedback']=linear.replace('float source=input-feedback*memory;',
                                                       'float source=saturate(input)-feedback*memory;')
    begin=source.index('static float ladder(')
    end=source.index('void synth_process(',begin)
    for stages in (1,2):
        for soft in (False,True):
            body=SVF.replace('STAGES',str(stages)).replace('INPUT','saturate(input)')
            body=body.replace('STATE1','saturate(2*v1-s[0])' if soft else '2*v1-s[0]')
            body=body.replace('STATE2','saturate(2*v2-s[1])' if soft else '2*v2-s[1]')
            variants[f'svf{12*stages}-'+('soft-state' if soft else 'linear-state')]=source[:begin]+body+source[end:]
    for power,label in ((.5,'sqrt-contour'),(2.,'square-contour')):
        variants['ladder24-'+label]=source.replace('settings[CONTOUR]*state->contour+mod',
                                f'settings[CONTOUR]*powf(state->contour,{power}f)+mod')
    return variants

class Voice:
    def __init__(self,library,rate):
        original=engine.build_library
        engine.build_library=lambda kind='bass':library if kind=='modeld' else original(kind)
        try: self.voice=NativeVoice(rate,'modeld')
        finally: engine.build_library=original
    def render(self,patch,controls,block=0):
        settings=np.array([patch['parameters'][name] for name in MODEL_D_NAMES],np.float64)
        controls[4].fill(patch['parameters']['resonance'])
        self.voice.reset()
        out=np.zeros(len(controls[0]),np.float32)
        block=block or len(out)
        for start in range(0,len(out),block):
            end=min(len(out),start+block)
            self.voice.process(out[start:end],[c[start:end] for c in controls],settings,3)
        return out

def controls_for(events,rate):
    n=round(events[-1]['end']*rate)
    c=[np.full(n,49,np.float32),np.zeros(n,np.float32),np.zeros(n,np.float32),np.ones(n,np.float32),np.zeros(n,np.float32)]
    for event in events:
        left=round(event['start']*rate);right=min(n,round(event['end']*rate))
        c[0][left:right]=event['frequency'];c[1][left:max(left,right-round(.025*rate))]=1;c[2][left]=1
    return c

def cycle_error(a,b):
    a=a.astype(float)-np.mean(a);b=b.astype(float)-np.mean(b)
    denominator=np.linalg.norm(a)*np.linalg.norm(b)
    if denominator<1e-9:return 1.
    correlation=np.fft.irfft(np.fft.rfft(a)*np.conj(np.fft.rfft(b)),n=len(a))
    return float(np.sqrt(max(0,2-2*np.max(correlation)/denominator))/2)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=float,default=3600)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--engines',nargs='+')
    parser.add_argument('--seed-bundles',nargs='+',type=Path)
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    os.nice(5)
    started=time.monotonic();deadline=started+args.seconds
    random=np.random.default_rng(20261102)
    # Keep architecture experiments based on the original, single-output core.
    source=(ROOT/'desktop/live/fixtures/ladder18-audition.c').read_text().replace(': taps[2];',': taps[3];')
    events=json.loads((ROOT/'baselines/bassline-v1/events.json').read_text())
    reference=load_audio(ROOT/'references/mariana/audio/Mariana_2.wav')
    controls=controls_for(events,24000)
    sections=[slice(round((e['start']-.015)*24000),min(len(reference),round(min(e['end']-.01,e['start']+.7)*24000))) for e in events]
    targets=[features(reference[s]) for s in sections]
    windows=[]
    for event in events:
        length=round(2*24000/event['frequency'])
        windows.append([slice(round((event['start']+offset)*24000),round((event['start']+offset)*24000)+length)
                        for offset in (.025,.15,.35) if event['start']+offset+length/24000<event['end']])
    seeds=[read_patch(ROOT/f'presets/archive/retired-user-patches/Model-D-update-{i}.json') for i in (1,2)]
    seeds += [read_patch(ROOT/'presets/Model-D-user-update-rubber-candidate.json'),read_patch(ROOT/'presets/Model-D-Rubber-v3.json')]
    if args.seed_bundles: seeds=[json.loads(path.read_text())['patch'] for path in args.seed_bundles]
    protected=[ROOT/f'presets/archive/retired-user-patches/Model-D-update-{i}.json' for i in (1,2)]+[ROOT/'desktop/live/native/modeld.c',ROOT/'baselines/bassline-v1/preset.json']
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    voices={};banks={};sources={}
    for name,code in architectures(source).items():
        if args.engines and name not in args.engines: continue
        path=out/f'{name}.c';path.write_text(code);lib=out/f'{name}.so'
        subprocess.run(['gcc','-O3','-fPIC','-shared',str(path),'-lm','-o',str(lib)],check=True)
        voices[name]=Voice(lib,24000);banks[name]=[];sources[name]=path
    if not voices: raise ValueError('No matching architectures')
    bounds=BOUNDS.copy();bounds[LOG]=np.log(bounds[LOG])
    def encode(p):
        values=np.array([p['parameters'][n] for n in NAMES]);values[LOG]=np.log(np.maximum(values[LOG],BOUNDS[LOG,0]))
        return np.clip((values-bounds[:,0])/(bounds[:,1]-bounds[:,0]),0,1)
    def mutate(parent,scale):
        p=json.loads(json.dumps(parent));v=encode(p)
        chosen=random.random(len(v))<(.25 if scale<.1 else .7)
        if not chosen.any():chosen[random.integers(len(v))]=True
        v[chosen]+=random.normal(0,scale,chosen.sum());v=np.clip(v,0,1)
        values=bounds[:,0]+v*(bounds[:,1]-bounds[:,0]);values[LOG]=np.exp(values[LOG])
        p['parameters'].update(dict(zip(NAMES,map(float,values))))
        if random.random()<.06:
            osc=random.integers(1,4);p['parameters'][f'osc{osc}_wave']=int(random.choice([0,1,2,3]))
        if random.random()<.04:p['parameters']['osc2_octave']=int(random.choice([-1,0]))
        p['output_gain_db']=0
        return p
    def score(audio,notes):
        if not np.isfinite(audio).all() or np.max(abs(audio))>3 or np.std(audio)<1e-6:return 100.
        scores=[]
        for i in notes:
            spectral=distance(features(audio[sections[i]]),targets[i])
            waveform=np.mean([cycle_error(audio[w],reference[w]) for w in windows[i]])
            scores.append(.75*spectral+.25*waveform)
        return float(np.mean(scores))
    trials=0;last=0;rejected=0
    log=(out/'trials.jsonl').open('w')
    try:
        while time.monotonic()<deadline or trials<len(voices)*len(seeds):
            for name,voice in voices.items():
                bank=banks[name]
                if len(bank)<len(seeds):patch=seeds[len(bank)]
                else:
                    parent=bank[int(random.integers(min(len(bank),8)))]['patch'] if random.random()<.85 else seeds[int(random.integers(len(seeds)))]
                    scale=float(random.choice([.015,.04,.1,.25],p=[.2,.35,.3,.15]))
                    patch=mutate(parent,scale)
                audio=voice.render(patch,controls);value=score(audio,TRAIN);trials+=1
                row={'trial':trials,'engine':name,'train':value,'patch':patch}
                log.write(json.dumps(row)+'\n')
                if value>=100:rejected+=1
                else:
                    bank.append(row);bank.sort(key=lambda row:row['train']);del bank[30:]
                if time.monotonic()-last>30:
                    progress={'status':'searching','trials':trials,'rejected':rejected,'elapsed_seconds':time.monotonic()-started,
                              'duration_seconds':args.seconds,'best':{k:v[0]['train'] if v else None for k,v in banks.items()}}
                    (out/'progress.json').write_text(json.dumps(progress,indent=2));log.flush();last=time.monotonic()
                if time.monotonic()>=deadline and trials>=len(voices)*len(seeds):break
        shortlist=[]
        for name,bank in banks.items():
            unique=[]
            for row in bank:
                if any(np.linalg.norm(encode(row['patch'])-encode(old['patch']))<.08 for old in unique):continue
                unique.append(row)
                if len(unique)==5:break
            for row in unique:
                audio=voices[name].render(row['patch'],controls)
                row['check']=score(audio,CHECK);row['selection_score']=.35*row['train']+.65*row['check'];shortlist.append(row)
        shortlist.sort(key=lambda row:row['selection_score'])
        selected=[];counts={}
        for row in shortlist:
            if counts.get(row['engine'],0)>=max(2,int(np.ceil(10/len(voices)))):continue
            selected.append(row);counts[row['engine']]=counts.get(row['engine'],0)+1
            if len(selected)==10:break
        controls48=controls_for(events,48000)
        reference48=load_audio(ROOT/'references/mariana/audio/Mariana_2.wav',48000)
        write_wav(out/'reference.wav',audition_normalize(reference48))
        entries=[]
        for rank,row in enumerate(selected,1):
            name=row['engine'];voice=Voice(out/f'{name}.so',48000)
            before=time.perf_counter();audio=voice.render(row['patch'],controls48,256);seconds=time.perf_counter()-before
            if not np.isfinite(audio).all() or np.max(abs(audio))>3:raise ValueError('Final unstable candidate '+name)
            again=voice.render(row['patch'],controls48,513)
            if not np.array_equal(audio,again):raise ValueError('Block dependent '+name)
            down=signal.resample_poly(audio,1,2);row['audit_48k']=score(down,AUDIT);row['render_seconds']=seconds
            row['source_sha256']=hashlib.sha256(sources[name].read_bytes()).hexdigest()
            row['rank']=rank;row['source']=sources[name].name
            row['notice']='Experimental architecture bundle, not a standard live-app preset. Use the bundled source to reproduce.'
            filename=f'{rank:02d}-{name}'
            (out/f'{filename}.json').write_text(json.dumps(row,indent=2))
            write_wav(out/f'{filename}.wav',audition_normalize(audio))
            write_wav(out/f'{filename}-AB.wav',np.r_[audition_normalize(reference48),np.zeros(24000),audition_normalize(audio)])
            entries.append(f'<li><h2>{rank}. {html.escape(name)}</h2><p>Score {row["selection_score"]:.5f}; audit {row["audit_48k"]:.5f}</p><audio controls src="{filename}.wav"></audio> <a href="{filename}-AB.wav">Reference then candidate</a> · <a href="{filename}.json">Patch + architecture</a> · <a href="{name}.c">Engine source</a></li>')
            voice.voice.close()
        for p in protected:
            if hashlib.sha256(p.read_bytes()).hexdigest()!=hashes[str(p)]:raise ValueError('Protected source changed '+str(p))
        report={'status':'complete','trials':trials,'rejected':rejected,'elapsed_seconds':time.monotonic()-started,
                'seed_bundles':[str(path) for path in (args.seed_bundles or [])],
                'requested_search_seconds':args.seconds,'ranked':selected,'protected_hashes':hashes,
                'limitations':['Relative numerical ranking, not proof of perceptual match.','Waveforms compared with cyclic phase alignment, not sample-by-sample phase locking.',
                              'Check notes select candidates; audit notes evaluated afterward from same recording.','24 kHz search, 48 kHz final validation.',
                              'Listening shortlist limits entries per engine to retain architectural variety. No hardware timing claim.']}
        (out/'report.json').write_text(json.dumps(report,indent=2))
        (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Mariana architecture audition</title><style>body{font:17px system-ui;background:#17222c;color:#eee;max-width:1000px;margin:40px auto}a{color:#8edbc0}li{margin-bottom:28px}audio{width:420px}</style><h1>Top 10 architecture auditions</h1><p>Reference: Mariana</p><audio controls src="reference.wav"></audio><p>Loudness matched. Ranked numerical candidates; listening judgment remains yours. Experimental bundles require their supplied engine source.</p><ol>'+''.join(entries)+'</ol>')
        (out/'progress.json').write_text(json.dumps({'status':'complete','trials':trials,'elapsed_seconds':time.monotonic()-started},indent=2))
        print('COMPLETE',out,flush=True)
    except Exception:
        (out/'failure.txt').write_text(traceback.format_exc());raise
    finally:
        log.close()
        for voice in voices.values():voice.voice.close()

if __name__=='__main__':main()
