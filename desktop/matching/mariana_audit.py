import json

import numpy as np
from scipy import signal

from analyze import load_audio
from mariana_fit import DEST, REFERENCE, target_features, loss, audition_normalize
from fit import save_wav


def measurements(audio):
    frequency,_,transformed=signal.stft(audio,24000,nperseg=2048,noverlap=1536)
    power=abs(transformed)**2
    low=power[(frequency>=22)&(frequency<400)].sum()
    high=power[(frequency>=400)&(frequency<=6000)].sum()
    return {'upper_lower_balance_db':float(10*np.log10((high+1e-12)/(low+1e-12))),
            'peak':float(np.max(abs(audio))),
            'rms':float(np.sqrt(np.mean(audio**2)))}


reference=load_audio(REFERENCE)
old=load_audio(DEST/'previous-patch-same-notes.wav')
new=load_audio(DEST/'rubber-bass.wav')
report={'reference':measurements(reference),'previous':measurements(old),'candidate':measurements(new),
        'reference_sha256':json.loads((DEST/'report.json').read_text())['reference_sha256'],
        'description':'Full-phrase mono energy 400-6000 Hz relative to 22-400 Hz. Not a perceptual-match percentage.'}
report['full_loss_previous']=loss(target_features(old),target_features(reference))
report['full_loss_new']=loss(target_features(new),target_features(reference))
(DEST/'audit.json').write_text(json.dumps(report,indent=2))
selected=json.loads((DEST/'report.json').read_text())['selected']
preset={'format':'electribe-desktop-rubber-v1','engine_function':'render_rubber_voice',
        'status':'listening candidate, match unconfirmed','selected':selected,
        'events_file':'events.json','reference_sha256':report['reference_sha256']}
(DEST/'preset.json').write_text(json.dumps(preset,indent=2))
save_wav(DEST/'rubber-preview.wav',audition_normalize(new)[:round(9.7*24000)],24000)
print(json.dumps(report,indent=2))
