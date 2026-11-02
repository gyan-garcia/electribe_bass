"""Apply static factory patch gains against the approved live engine's phrase.

Only output_gain_db changes. User presets and archived auditions are untouched.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from model import ROOT, engine_key, read_patch, validate_patch
from modeld_preview import render


def main():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory=Path(__file__).parent/'outputs'/f'modeld-volume-{stamp}'
    directory.mkdir()
    baseline=read_patch(ROOT/'baselines/bassline-v1/preset.json')
    reference=render(baseline,apply_output_gain=False)
    reference_rms=float(np.sqrt(np.mean(reference.astype(np.float64)**2)))
    rows=[]
    for path in sorted((ROOT/'presets').glob('*.json')):
        if not path.name.lower().startswith('model-d-'): continue
        original=path.read_bytes()
        data=json.loads(original)
        patch=validate_patch(data)
        if engine_key(patch['architecture'])!='modeld': continue
        audio=render(patch,apply_output_gain=False)
        rms=float(np.sqrt(np.mean(audio.astype(np.float64)**2)))
        peak=float(np.max(abs(audio)))
        if rms<1e-8: raise ValueError('Cannot balance a silent factory patch: '+str(path))
        desired=20*np.log10(reference_rms/rms)
        # Keep headroom at the initial -18 dB master and maximum note velocity.
        ceiling=20*np.log10(.8/max(1e-9,peak*.126))
        gain=round(float(np.clip(min(desired,ceiling),-24,24)),2)
        data['output_gain_db']=gain
        validate_patch(data)
        (directory/path.name).write_bytes(original)
        temporary=path.with_suffix('.volume-tmp')
        temporary.write_text(json.dumps(data,indent=2)+'\n')
        temporary.replace(path)
        adjusted=rms*10**(gain/20)
        rows.append({'preset':str(path),'name':patch['name'],'output_gain_db':gain,
                     'previous_gain_db':patch['output_gain_db'],'raw_rms':rms,
                     'adjusted_rms':adjusted,'reference_difference_db':float(20*np.log10(adjusted/reference_rms)),
                     'default_master_peak':peak*.126*10**(gain/20),
                     'before_sha256':hashlib.sha256(original).hexdigest(),
                     'parameters_unchanged':data['parameters']==patch['parameters']})
    report={'reference_rms':reference_rms,'reference':'Approved bass raw live phrase',
            'method':'Static RMS match, -24..24 dB, peak headroom at -18 dB master; no compressor or normalization in playback',
            'presets':rows}
    (directory/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    print('REPORT',directory/'report.json')


if __name__=='__main__': main()
