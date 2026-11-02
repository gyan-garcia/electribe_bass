"""Plot measured attack/brightness motion; these are audio proxies, not cutoff measurements."""
import argparse
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

from model import ROOT, read_patch
from modeld_preview import render

sys.path.insert(0,str(ROOT/'desktop/matching'))
from analyze import load_audio


def trajectory(audio):
    audio=audio[round(.5*48000):round(1.2*48000)]
    frequency,times,transform=signal.stft(audio,48000,nperseg=2048,noverlap=1808,nfft=4096)
    power=abs(transform)**2
    mask=(frequency>=25)&(frequency<8000)
    rms=np.sqrt(power[mask].sum(axis=0))
    centroid=(frequency[mask,None]*power[mask]).sum(axis=0)/(power[mask].sum(axis=0)+1e-12)
    low=power[(frequency>=25)&(frequency<400)].sum(axis=0)
    high=power[(frequency>=800)&(frequency<5000)].sum(axis=0)
    brightness=10*np.log10((high+1e-10)/(low+1e-10))
    return times,rms,centroid,brightness


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    report=json.loads((args.directory/'report.json').read_text())
    candidate=read_patch(report['selected'][0]['preset'])
    audio={'Mariana':load_audio(ROOT/'references/mariana/audio/Mariana_2.wav',48000),
           'Previous Model D':render(read_patch(ROOT/'presets/model-d-reference-candidate.json')),
           candidate['name']:render(candidate)}
    fig,axes=plt.subplots(3,1,figsize=(10,8),sharex=True,layout='constrained')
    colors=['#272727','#a4a4a4','#007f78']
    metrics={}
    for (label,recording),color in zip(audio.items(),colors):
        times,rms,centroid,brightness=trajectory(recording)
        axes[0].plot(times*1000,20*np.log10(rms/max(rms.max(),1e-9)+1e-8),label=label,color=color)
        axes[1].plot(times*1000,centroid,color=color)
        axes[2].plot(times*1000,brightness,color=color)
        mask=(times>=.025)&(times<=.4)
        peak=np.where(mask)[0][np.argmax(centroid[mask])]
        metrics[label]={'early_centroid_peak_ms':float(times[peak]*1000),
                        'early_centroid_peak_hz':float(centroid[peak]),
                        'centroid_at_300ms_hz':float(np.interp(.3,times,centroid)),
                        'brightness_at_50ms_db':float(np.interp(.05,times,brightness)),
                        'brightness_at_300ms_db':float(np.interp(.3,times,brightness))}
    axes[0].set_ylabel('Relative level (dB)')
    axes[0].set_ylim(-45,2)
    axes[0].legend()
    axes[1].set_ylabel('Power centroid (Hz)')
    axes[2].set_ylabel('High / low energy (dB)')
    axes[2].set_xlabel('Time after first G1 onset (ms)')
    for axis in axes:
        axis.grid(alpha=.18)
        axis.set_xlim(0,650)
    fig.suptitle('First G1: measured contour and timbre movement\nBrightness proxies, not measurements of filter cutoff')
    fig.savefig(args.directory/'movement-comparison.png',dpi=160)
    plt.close(fig)
    (args.directory/'movement-measurements.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps(metrics,indent=2))


if __name__=='__main__': main()
