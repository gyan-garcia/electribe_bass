import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

HERE=Path(__file__).resolve().parent
BASELINE=HERE.parents[2]/'baselines/bassline-v1'
report=json.loads((HERE/'report.json').read_text())
assert report['baseline_verified']
for name,digest in report['baseline_hashes'].items():
    assert hashlib.sha256((BASELINE/name).read_bytes()).hexdigest()==digest,name
assert len(report['variants'])==8
for row in report['variants']:
    rate,audio=wavfile.read(HERE/'outputs'/f'{row["name"]}.wav')
    assert rate==24000 and len(audio)==310155
    assert np.max(abs(audio.astype(np.int32)))<32767
    assert np.std(audio)>10
    assert np.all(audio[:8400]==0)
_,original=wavfile.read(BASELINE/'bassline-48k.wav')
_,regenerated=wavfile.read(HERE/'outputs/baseline-render-check-48k.wav')
assert np.array_equal(original,regenerated)
rate,sampler=wavfile.read(HERE/'outputs/sampler-in-order.wav')
assert rate==24000 and len(sampler)==739200
assert hashlib.sha256((HERE/'experiment_voice.c').read_bytes()).hexdigest()==report['source_sha256']
print('Baseline integrity, exact default render, 8 exports, sampler and source checks passed.')
