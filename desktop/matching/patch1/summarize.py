import json
from pathlib import Path
import sys

import numpy as np
from scipy import signal

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from analyze import load_audio


def balance(audio):
    frequency,_,spectrum=signal.stft(audio,24000,nperseg=2048,noverlap=1536)
    power=abs(spectrum)**2
    low=power[(frequency>=22)&(frequency<400)].sum()
    high=power[(frequency>=400)&(frequency<=6000)].sum()
    return float(10*np.log10((high+1e-12)/(low+1e-12)))


report=json.loads((HERE/'report.json').read_text())
reference=load_audio(HERE.parents[2]/'references/mariana/audio/Mariana_2.wav')
measurements={'reference_balance_db':balance(reference),'candidates':{}}
for name,values in report['outputs'].items():
    audio=load_audio(HERE/f'{name}-same-phrase.wav')
    measurements['candidates'][name]={'upper_lower_balance_db':balance(audio),
                                     'whole_phrase_loss':values['whole_phrase_loss'],
                                     'audit_loss':values['audit_loss']}
    preset={'format':'electribe-desktop-patch-v1','architecture':'svf12',
            'parameters':values['parameters'],'engine_source':'voice-snapshot.c',
            'engine_sha256':report['source_sha256'],'note_events':'../mariana/events.json',
            'status':'listening candidate, not an approved final patch'}
    (HERE/f'{name}-preset.json').write_text(json.dumps(preset,indent=2))
(HERE/'measurements.json').write_text(json.dumps(measurements,indent=2))
print(json.dumps(measurements,indent=2))
