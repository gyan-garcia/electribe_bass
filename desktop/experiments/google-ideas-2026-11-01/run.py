import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy import signal
from scipy.io import wavfile

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[2]
BASELINE=PROJECT/'baselines/bassline-v1'
sys.path.insert(0,str(PROJECT/'desktop/matching'))
from fit import Renderer, save_wav
from mariana_fit import EXTENDED_NAMES, audition_normalize, target_features, loss
from analyze import load_audio


def baseline_hashes():
    expected={}
    for line in (BASELINE/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split(maxsplit=1)
        name=name.strip()
        actual=hashlib.sha256((BASELINE/name).read_bytes()).hexdigest()
        if actual!=digest:
            raise ValueError(f'Baseline checksum mismatch: {name}')
        expected[name]=actual
    return expected


def peak_eq(rate,frequency,gain_db,quality):
    amplitude=10**(gain_db/40)
    omega=2*np.pi*frequency/rate
    alpha=np.sin(omega)/(2*quality)
    numerator=[1+alpha*amplitude,-2*np.cos(omega),1-alpha*amplitude]
    denominator=[1+alpha/amplitude,-2*np.cos(omega),1-alpha/amplitude]
    return np.array(numerator)/denominator[0],np.array(denominator)/denominator[0]


def main():
    before=baseline_hashes()
    output=HERE/'outputs'
    build=HERE/'build'
    output.mkdir(exist_ok=True)
    build.mkdir(exist_ok=True)
    preset=json.loads((BASELINE/'preset.json').read_text())
    base=np.array([preset['parameters'][name] for name in EXTENDED_NAMES])
    events=json.loads((BASELINE/'events.json').read_text())
    reference=load_audio(PROJECT/'references/mariana/audio/Mariana_2.wav')
    seconds=len(reference)/24000
    configurations=[
        ('00-baseline',[],{},None,'Approved Bassline v1','none'),
        ('01-pluck-envelope',[],{'filter_attack_s':.001,'filter_decay_s':.18},None,
         'Faster filter attack, longer decay time constant; amplitude stays fixed','00-baseline'),
        ('02-clean-sub',['CLEAN_SUB'],{},None,
         'Sub bypasses final waveshaper but retains its level/filter/amp','00-baseline'),
        ('03-main-soft-drive',['CLEAN_SUB','MAIN_SOFT_DRIVE'],{},None,
         'Additional soft drive on main path only','02-clean-sub'),
        ('04-main-hard-clip',['CLEAN_SUB','MAIN_CLIP'],{},None,
         'Main-path hard clip experiment; aliasing risk, not deployment approved','02-clean-sub'),
        ('05-pulse-a',['PULSE_A'],{},None,
         'Main oscillator A becomes pulse; B stays mostly saw; no extra voices','00-baseline'),
        ('06-low-mid-eq',[],{},'eq',
         '350 Hz bell boost +2 dB, Q .7','00-baseline'),
        ('07-highpass-20hz',[],{},'highpass',
         '20 Hz second-order high-pass; deliberately tests loss of lowest sub','00-baseline')]
    rows=[]
    sampler=[]
    last_by_flags={}
    raw_by_name={}
    for name,flags,changes,effect,description,parent in configurations:
        key=tuple(flags)
        if key not in last_by_flags:
            library=build/f'{name}.so'
            subprocess.run(['gcc','-O3','-Wall','-Wextra','-Werror','-shared','-fPIC',
                            *[f'-D{flag}' for flag in flags],str(HERE/'experiment_voice.c'),
                            '-lm','-o',str(library)],check=True)
            last_by_flags[key]=library
        settings=base.copy()
        for parameter,value in changes.items():
            settings[EXTENDED_NAMES.index(parameter)]=value
        renderer=Renderer(events,48000,last_by_flags[key],'render_rubber_voice')
        controls=renderer.controls(0,seconds)
        audio=renderer.render(settings,0,controls)
        if effect=='eq':
            numerator,denominator=peak_eq(48000,350,2,.7)
            audio=signal.lfilter(numerator,denominator,audio)
        elif effect=='highpass':
            audio=signal.sosfilt(signal.butter(2,20,btype='highpass',fs=48000,output='sos'),audio)
        if not np.all(np.isfinite(audio)):
            raise ValueError(f'Non-finite render: {name}')
        raw_by_name[name]=audio
        down=signal.resample_poly(audio,1,2)
        adjusted=audition_normalize(down)
        save_wav(output/f'{name}.wav',adjusted,24000)
        if name=='00-baseline':
            save_wav(output/'baseline-render-check-48k.wav',audio,48000)
            rate,original=wavfile.read(BASELINE/'bassline-48k.wav')
            _,check=wavfile.read(output/'baseline-render-check-48k.wav')
            if rate!=48000 or not np.array_equal(original,check):
                raise ValueError('Experiment default does not reproduce approved baseline')
        excerpt=down[round(.45*24000):round(3.95*24000)].copy()
        excerpt=audition_normalize(excerpt)
        fade=np.linspace(0,1,240)
        excerpt[:240]*=fade
        excerpt[-240:]*=fade[::-1]
        sampler.extend([excerpt,np.zeros(8400)])
        frequency,_,spectrum=signal.stft(down,24000,nperseg=2048,noverlap=1536)
        power=abs(spectrum)**2
        low=power[(frequency>=22)&(frequency<400)].sum()
        high=power[(frequency>=400)&(frequency<=6000)].sum()
        row={'name':name,'description':description,'compare_to':parent,'flags':flags,
             'parameter_changes':changes,'post_effect':effect,
             'raw_peak':float(np.max(abs(audio))),'audition_rms':float(np.sqrt(np.mean(adjusted**2))),
             'upper_lower_db':float(10*np.log10((high+1e-12)/(low+1e-12))),
             'reference_loss':loss(target_features(down),target_features(reference)),
             'parameters':dict(zip(EXTENDED_NAMES,settings.tolist()))}
        rows.append(row)
        (output/f'{name}.json').write_text(json.dumps(row,indent=2))
        print(name,'balance',round(row['upper_lower_db'],2),'reference error',round(row['reference_loss'],4),flush=True)
    for row in rows[1:]:
        audio=raw_by_name[row['name']]
        parent=raw_by_name[row['compare_to']]
        if np.array_equal(audio,parent):
            raise ValueError(f'Experiment had no effect: {row["name"]}')
    save_wav(output/'sampler-in-order.wav',np.concatenate(sampler),24000)
    after=baseline_hashes()
    if before!=after:
        raise ValueError('Baseline changed')
    report={'status':'controlled auditions only; no candidate promoted','baseline_verified':True,
            'baseline_hashes':after,'order':[row['name'] for row in rows],
            'sampler':'3.5 s same excerpt per variant, followed by .35 s silence, in numbered order.',
            'note_events':str(BASELINE/'events.json'),'variants':rows,
            'source_sha256':hashlib.sha256((HERE/'experiment_voice.c').read_bytes()).hexdigest(),
            'limitations':['Native desktop only; no Blackfin timing or fixed-point validation.',
                           'Hard clipping can add aliasing with the current simple oversampling.',
                           'Reference loss is descriptive, not a perceptual quality ranking.',
                           'No Serum proprietary wavetables or external presets were used.',
                           'No sidechain compressor or multiband compressor implemented.']}
    (HERE/'report.json').write_text(json.dumps(report,indent=2))
    print('Baseline checksums unchanged; eight auditions saved.',flush=True)


if __name__=='__main__':
    main()
