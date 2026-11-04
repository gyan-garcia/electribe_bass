"""One-time, backed-up active-library migration, run before retiring the 18 dB core."""
import argparse
from datetime import datetime,timezone
import hashlib
import html
import json
from pathlib import Path
import shutil
import time
import wave

import numpy as np
from scipy import optimize,signal
from model import ROOT,read_patch
from modeld_preview import render


def fingerprint(y):
    y=signal.resample_poly(y,1,2)
    rms=max(1e-12,float(np.sqrt(np.mean(y.astype(float)**2))))
    _,_,z=signal.stft(y/rms,24000,nperseg=1024,noverlap=768,boundary=None)
    power=abs(z)**2
    freqs=np.fft.rfftfreq(1024,1/24000)
    edges=np.geomspace(30,9500,25)
    bands=np.array([np.sqrt(power[(freqs>=a)&(freqs<b)].sum(axis=0)+1e-12) for a,b in zip(edges[:-1],edges[1:])])
    return np.log1p(8*bands),rms


def wav(path,y):
    with wave.open(str(path),'wb') as f:
        f.setparams((1,2,48000,0,'NONE','not compressed'))
        f.writeframes(np.round(np.clip(y,-1,1)*32767).astype('<i2').tobytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    paths=sorted((ROOT/'presets/user').glob('*.json'))
    originals={p:read_patch(p) for p in paths}
    old=[p for p in paths if originals[p]['architecture']=='modeld18']
    if not old: raise SystemExit('No active 18 dB patches to migrate.')
    out=ROOT/'desktop/live/outputs'/('24db-migration-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup=out/'originals';backup.mkdir(parents=True)
    hashes={}
    for p in paths:
        shutil.copy2(p,backup/p.name);hashes[p]=hashlib.sha256(p.read_bytes()).hexdigest()
    shutil.copy2(ROOT/'desktop/live/native/modeld.c',out/'original-modeld.c')
    rows=[];proposed={};cards=[]
    for i,p in enumerate(old,1):
        before=originals[p];reference=render(before,apply_output_gain=False)
        target,ref_rms=fingerprint(reference)
        best=[float('inf'),None,None]
        def candidate(x):
            values={**before['parameters'],'filter_mode':0,
                'cutoff_hz':float(np.clip(before['parameters']['cutoff_hz']*2**x[0],20,18000)),
                'filter_env_octaves':float(np.clip(before['parameters']['filter_env_octaves']+x[1],-6,8))}
            return {**before,'architecture':'modeld','parameters':values}
        def objective(x):
            patch=candidate(x);samples=render(patch,apply_output_gain=False)
            feat,_=fingerprint(samples)
            loss=float(np.mean((feat-target)**2))
            if loss<best[0]:best[:]=[loss,np.array(x),samples]
            return loss
        naive=objective([0,0])
        optimize.minimize(objective,[np.log2(1.2),.0],method='Powell',bounds=[(-.5,1.5),(-1.5,1.5)],
                          options={'maxfev':36,'xtol':.015,'ftol':.001})
        patch=candidate(best[1]);samples=best[2];_,new_rms=fingerprint(samples)
        patch['output_gain_db']=float(np.clip(before.get('output_gain_db',0)+20*np.log10(ref_rms/new_rms),-24,24))
        proposed[p]=patch
        gain_a=.1/max(1e-12,float(np.sqrt(np.mean(reference.astype(float)**2))))
        gain_b=.1/max(1e-12,float(np.sqrt(np.mean(samples.astype(float)**2))))
        safety=min(1,.9/max(np.max(abs(reference*gain_a)),np.max(abs(samples*gain_b))))
        wav(out/f'{i:02d}-before.wav',reference*gain_a*safety);wav(out/f'{i:02d}-after.wav',samples*gain_b*safety)
        (out/(p.stem+'-24db.json')).write_text(json.dumps(patch,indent=2)+'\n')
        row=dict(name=patch['name'],file=p.name,original_sha256=hashes[p],before={k:before['parameters'][k] for k in ('cutoff_hz','filter_env_octaves')},
                 after={k:patch['parameters'][k] for k in ('cutoff_hz','filter_env_octaves')},before_gain_db=before.get('output_gain_db',0),
                 after_gain_db=patch['output_gain_db'],unadjusted_spectral_error=naive,adjusted_spectral_error=best[0])
        rows.append(row)
        cards.append(f'<article><h2>{html.escape(patch["name"])}</h2><p>Before: 18 dB</p><audio controls src="{i:02d}-before.wav"></audio><p>After: 24 dB, adjusted</p><audio controls src="{i:02d}-after.wav"></audio></article>')
        print(f'{i}/{len(old)} {patch["name"]}: spectral error {naive:.6f} → {best[0]:.6f}',flush=True)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==hashes[p] for p in paths),'Library changed during migration'
    if args.apply:
        for p,patch in proposed.items():p.write_text(json.dumps(patch,indent=2)+'\n')
    (out/'report.json').write_text(json.dumps(dict(applied=args.apply,patches=rows,unchanged_patches=len(paths)-len(old),
        note='Full demonstration sequence; normalized time-varying spectral-band fit. Only cutoff, contour depth and clean gain adjusted. Numerical fit does not guarantee perceptual equivalence.'),indent=2)+'\n')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>24 dB patch migration</title><style>body{font:18px system-ui;max-width:850px;margin:40px auto;background:#19232b;color:#eee}audio{width:100%}article{margin:35px 0}</style><h1>18 → 24 dB patch migration</h1><p>Same notes, EQ and reverb; matched levels. Originals backed up. Approximate matches, not identical signals.</p>'+''.join(cards))
    (ROOT/'desktop/live/outputs/active-24db-migration.json').write_text(json.dumps({'folder':str(out)},indent=2)+'\n')
    print(out,flush=True)

if __name__=='__main__':main()
