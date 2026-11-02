"""Reference/user-patch oscilloscope and time-frequency comparison."""
import json
from pathlib import Path
import sys
import wave
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from model import ROOT, read_patch, save_patch
from modeld_preview import render
sys.path.insert(0,str(ROOT/'desktop/matching'))
from analyze import load_audio
from mariana_fit import audition_normalize


def main():
    out=Path(__file__).parent/'outputs/user-update-comparison'
    out.mkdir(exist_ok=True)
    labels=['Mariana','Your update 1','Your update 2']
    audio=[load_audio(ROOT/'references/mariana/audio/Mariana_2.wav',48000)]
    for number in (1,2): audio.append(render(read_patch(ROOT/f'presets/archive/retired-user-patches/Model-D-update-{number}.json')))
    reports=[]
    for directory in (Path(__file__).parent/'outputs').glob('modeld-rubber-*'):
        path=directory/'report.json'
        if path.exists():
            report=json.loads(path.read_text())
            if '/presets/user/Model-D-update-' in report.get('start_preset',''):
                reports.append((directory,report))
    candidates=[row for _,report in reports for row in report['selected']]
    best=min(candidates,key=lambda row:row['final_48k_score'])
    patch=read_patch(best['preset'])
    raw=render(patch,apply_output_gain=False)
    base=render(read_patch(ROOT/'baselines/bassline-v1/preset.json'),apply_output_gain=False)
    gain=min(float(np.sqrt(np.mean(base.astype(float)**2))/np.sqrt(np.mean(raw.astype(float)**2))),
             .75/(.126*float(np.max(abs(raw)))))
    patch['output_gain_db']=round(float(np.clip(20*np.log10(gain),-24,24)),2)
    path=save_patch('Model D user update rubber candidate',patch,ROOT/'presets')
    labels.append('Refined candidate')
    audio.append(render(read_patch(path)))
    normalized=[audition_normalize(item) for item in audio]
    section=slice(round(.45*48000),round(3.18*48000))
    comparison=np.concatenate([np.r_[item[section],np.zeros(24000)] for item in normalized])
    for name,item in [('comparison',comparison),('candidate',normalized[-1])]:
        with wave.open(str(out/f'{name}.wav'),'wb') as handle:
            handle.setparams((1,2,48000,0,'NONE','not compressed'))
            handle.writeframes(np.round(np.clip(item,-.98,.98)*32767).astype('<i2').tobytes())
    fig,axes=plt.subplots(4,2,figsize=(13,11),layout='constrained')
    for row,(label,item) in enumerate(zip(labels,normalized)):
        start=round(.53*48000)
        segment=item[start:start+round(.08*48000)]
        axes[row,0].plot(np.arange(len(segment))/48,segment,color='#007f78',linewidth=.9)
        axes[row,0].set_title(label+' — waveform, 30 ms after onset')
        axes[row,0].set_ylim(-.7,.7)
        axes[row,0].set_xlabel('Time (ms)')
        frequency,times,z=signal.stft(item[24000:60000],48000,nperseg=2048,noverlap=1808)
        axes[row,1].pcolormesh(times*1000,frequency,20*np.log10(abs(z)+1e-7),vmin=-70,vmax=-15,shading='auto',cmap='magma')
        axes[row,1].set_ylim(25,4000)
        axes[row,1].set_yscale('log')
        axes[row,1].set_xlabel('Time after note onset (ms)')
        axes[row,1].set_ylabel('Frequency (Hz)')
    fig.suptitle('Matched playback levels; waveform phase is not aligned\nSpectrograms show harmonic movement, not direct measurements of filter cutoff')
    fig.savefig(out/'waveform-and-sweep.png',dpi=150)
    plt.close(fig)
    result={'candidate':str(path),'comparison_order':labels,'selected_metrics':best,
            'runs':[str(directory) for directory,_ in reports],
            'trials':sum(report['trials'] for _,report in reports),
            'limitations':'No confirmed perceptual match. Waveform phase differs; compare spectral motion and listen. Original user patches untouched.'}
    (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('candidate','trials','runs')},indent=2))


if __name__=='__main__': main()
