"""Package completed settings experiments into a compact listening comparison."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from scipy import signal

from model import ROOT, read_patch
from modeld_preview import render
from refine_modeld_rubber import features, distance, write_wav, load_audio, audition_normalize


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('runs',type=Path,nargs='+')
    args=parser.parse_args()
    reports=[json.loads((directory/'report.json').read_text()) for directory in args.runs]
    regular=[row for report in reports if not report.get('resonant_variant',False) for row in report['selected']]
    resonant=[row for report in reports if report.get('resonant_variant',False) for row in report['selected']]
    primary=min(regular,key=lambda row:row['final_48k_score'])
    contrast=min(resonant,key=lambda row:row['final_48k_score'])
    directory=Path(__file__).parent/'outputs/modeld-rubber-audition'
    directory.mkdir(exist_ok=True)
    reference=load_audio(ROOT/'references/mariana/audio/Mariana_2.wav',48000)
    old=render(read_patch(ROOT/'presets/model-d-reference-candidate.json'))
    new=render(read_patch(primary['preset']))
    alternative=render(read_patch(contrast['preset']))
    clips=[reference,old,new,alternative]
    labels=['Mariana','Previous Model D',read_patch(primary['preset'])['name'],read_patch(contrast['preset'])['name']]
    normalized=[audition_normalize(audio) for audio in clips]
    pause=np.zeros(24000)
    section=slice(round(.45*48000),round(3.18*48000))
    write_wav(directory/'short-comparison.wav',np.concatenate([
        np.r_[audio[section],pause] for audio in normalized]))
    write_wav(directory/'full-comparison.wav',np.concatenate([
        np.r_[audio,pause] for audio in normalized]))
    write_wav(directory/'rubber-candidate.wav',normalized[2])
    write_wav(directory/'resonant-candidate.wav',normalized[3])
    reference24=signal.resample_poly(reference,1,2)
    events=json.loads((ROOT/'baselines/bassline-v1/events.json').read_text())
    sections=[slice(round((event['start']-.015)*24000),
                    min(len(reference24),round(min(event['end']-.01,event['start']+.7)*24000)))
              for event in events]
    targets=[features(reference24[section]) for section in sections]
    metrics={}
    for label,audio in zip(labels[1:],clips[1:]):
        down=signal.resample_poly(audio,1,2)
        scores=[distance(features(down[section]),target) for section,target in zip(sections,targets)]
        metrics[label]={'all_notes':float(np.mean(scores)),
                        'check_notes':float(np.mean(np.array(scores)[[1,2,4,6,7,9,11,12]]))}
    protected=[ROOT/'baselines/bassline-v1/preset.json',ROOT/'baselines/bassline-v1/voice.c',
               ROOT/'presets/bassline-pluck.json',ROOT/'presets/model-d-reference-candidate.json',
               Path(__file__).parent/'native/modeld.c']
    hashes={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    for report in reports:
        for path,digest in report['unchanged_hashes'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:
                raise RuntimeError('Protected file changed: '+path)
    result={'comparison_order':labels,'primary_preset':primary['preset'],
            'resonant_preset':contrast['preset'],'trials':sum(report['trials'] for report in reports),
            'search_seconds':sum(report['seconds'] for report in reports),
            'final_48k_metrics':metrics,'runs':[str(path.resolve()) for path in args.runs],
            'unchanged_sha256':hashes,'status':'New settings only; listening approval pending'}
    (directory/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    shutil.copyfile(primary['preset'],directory/'candidate-preset.json')
    shutil.copyfile(contrast['preset'],directory/'resonant-preset.json')
    (directory/'README.md').write_text(
        '# Model D rubber refinement\n\n'
        'The short and full comparisons play: '+ ' → '.join(labels)+'.\n\n'
        'All synthesized clips use the existing Model D engine with changed knobs only. '
        'Reference audio is used for measurement and comparison, never as part of the synth. '
        'Clips have matched RMS subject to a peak cap; this is static audition gain, not compression.\n\n'
        'Primary preset: '+primary['preset']+'\n\n'
        'Contrast preset: '+contrast['preset']+'\n\n'
        'Save any open edits, reopen Bass Lab, select Model D prototype and choose the named preset. '
        'Session MIDI maps start empty after restarting. No preset is promoted to the baseline.\n\n'
        'These metrics aid comparison, but cannot establish that the sound is subjectively matched. '
        'Check notes come from the same reference recording; estimated gate timing remains a limitation. '
        'The same recordings were used throughout development. No new hardware performance claim.\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
