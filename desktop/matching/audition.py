import json

import numpy as np

from analyze import ROOT, REFERENCE, load_audio
from fit import distance, features, save_wav


def normalized_excerpt(audio, start, seconds, rate=24000):
    excerpt=audio[round(start*rate):round((start+seconds)*rate)].copy()
    gain=.14/max(1e-8,np.sqrt(np.mean(excerpt**2)))
    gain=min(gain,.89/max(1e-8,np.max(abs(excerpt))))
    excerpt*=gain
    fade=np.linspace(0,1,240)
    excerpt[:240]*=fade
    excerpt[-240:]*=fade[::-1]
    return excerpt


reference=load_audio(REFERENCE)
baseline=load_audio(ROOT/'outputs/baseline.wav')
static=load_audio(ROOT/'outputs/fitted-static.wav')
automated=load_audio(ROOT/'outputs/fitted-automated.wav')
errors=[]
for start in (3.3,9.3,27.3,39.3,51.3):
    target=features(reference[round(start*24000):round((start+1.4)*24000)],24000)
    row={'start':start}
    for name,audio in [('baseline',baseline),('static',static),('automated',automated)]:
        row[name]=distance(features(audio[round(start*24000):round((start+1.4)*24000)],24000),target)
    errors.append(row)
summary={'independent_audit_windows':errors,
         'means':{name:float(np.mean([row[name] for row in errors])) for name in ('baseline','static','automated')},
         'comparison_order':'For excerpts at 0, 7 and 24 seconds: reference 3 s, silence .5 s, synth 3 s, silence 1 s. RMS-matched with peak caps.',
         'note':'Audit excerpts excluded from explicit core/section fitting windows; same recording and provisional note extraction. Not independent musical material.'}
selected=min(('static','automated'),key=lambda name:summary['means'][name])
summary['selected_output']=selected
summary['note']+=' These audit scores are now used to select the output variant.'
candidate=static if selected=='static' else automated
pieces=[]
for start in (0,7,24):
    pieces.extend([normalized_excerpt(reference,start,3),np.zeros(12000),
                   normalized_excerpt(candidate,start,3),np.zeros(24000)])
save_wav(ROOT/'outputs/reference-then-synth.wav',np.concatenate(pieces),24000)
save_wav(ROOT/'outputs/fitted-preview.wav',candidate[:8*24000],24000)
save_wav(ROOT/'outputs/best-candidate.wav',candidate,24000)
report=json.loads((ROOT/'report.json').read_text())
preset={'engine':'desktop/matching/voice.c','status':'approximation; perceptual match unconfirmed',
        'architecture':report['selected']['architecture'],
        'parameters':report['selected']['parameters'],
        'automation':report['automation'] if selected=='automated' else [],
        'note_schedule':'analysis.json','selected_output':selected,
        'reference_sha256':report['reference_sha256']}
(ROOT/'outputs/best-preset.json').write_text(json.dumps(preset,indent=2))
(ROOT/'audit.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary['means'],indent=2))
