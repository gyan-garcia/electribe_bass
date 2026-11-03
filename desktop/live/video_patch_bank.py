"""Install video-derived Model D patches and render device-free auditions.

Existing filenames are never overwritten. See presets/video-banks/README.md.
This tool does not download media or require the PDF extraction dependencies.
"""
import hashlib
import html
import json
import math
import re
from pathlib import Path
import wave

import numpy as np

from engine import NativeVoice
from model import ARCHITECTURES, MODEL_D_PARAMETERS, ROOT, read_patch, validate_patch
from modeld_preview import factory
from reverb import Reverb

OUT = ROOT/'desktop/live/outputs/video-recreation'
MANUAL = 'https://cdn.inmusicbrands.com/Moog/Model%20D/Minimoog_Model_D_Manual.pdf'
VIDEOS = {'DM':'https://www.youtube.com/watch?v=cxDTIpWvtzo',
          'TL':'https://www.youtube.com/watch?v=J33nnF19Qnk'}


def base(name):
    patch=factory()['init']
    patch['name']=name
    p=patch['parameters']
    p.update(osc1_level=0, osc2_level=0, osc3_level=0, mod_source_2=0,
             mod_mix=0, mod_amount=0, feedback_level=0, release_enabled=0)
    return patch


def doctor_mix():
    rows=[]
    def add(name,time,**p):
        patch=base('DM - '+name)
        patch['parameters'].update(p)
        rows.append(dict(patch=validate_patch(patch),video=VIDEOS['DM']+'&t='+str(time),
                         source='spoken walkthrough and panel close-ups',limitations=[]))
    add('Hip-Hop Lead',54,osc1_level=.8,osc1_wave=2,osc1_octave=0,
        cutoff_hz=2866.3621181644617,resonance=.04,filter_env_octaves=0,attack_s=.002,
        amp_sustain=1,amp_decay_s=.12,glide_s=.065,osc3_keyboard=0,
        osc3_wave=0,osc3_fixed_hz=5.5,pitch_mod_enabled=1,pitch_mod_depth=.8,
        mod_amount=.2)
    add('Soulful Bass',214,osc1_level=.8,osc1_wave=2,osc1_octave=-1,
        cutoff_hz=347.29905598505337,resonance=.18010465057825636,filter_env_octaves=4.536977555188767,
        filter_attack_s=.002,filter_decay_s=.5966761462304526,filter_sustain=.12,
        attack_s=.002,amp_decay_s=.22,amp_sustain=.65,release_enabled=1)
    add('Spaceship',407,osc1_level=.8,osc1_wave=2,osc1_octave=0,
        cutoff_hz=6500,resonance=.08,filter_env_octaves=0,
        attack_s=.002,amp_sustain=1,amp_decay_s=.15,osc3_keyboard=0,
        osc3_wave=2,osc3_fixed_hz=8,pitch_mod_enabled=1,pitch_mod_depth=12,
        mod_amount=.8)
    rows[-1]['limitations']=['Oscillator-modulation version. Use mod wheel and Oscillator 3 Untracked Frequency to sweep the effect; not the alternate filter-only version.']
    add('Power Bass',558,osc1_level=.8,osc1_wave=2,osc1_octave=-1,
        osc2_level=.65,osc2_wave=3,osc2_octave=-2,osc2_tune=.015,
        cutoff_hz=500,resonance=0,filter_env_octaves=2.7,
        filter_attack_s=.001,filter_decay_s=.24,filter_sustain=.2,
        attack_s=.001,amp_decay_s=.26,amp_sustain=.7,release_enabled=1)
    add('Super Lead',769,osc1_level=.65,osc2_level=.65,osc3_level=.65,
        osc1_wave=2,osc2_wave=2,osc3_wave=2,osc1_octave=0,osc2_octave=-1,
        osc3_octave=-2,osc3_keyboard=1,cutoff_hz=18000,resonance=0,
        filter_env_octaves=0,attack_s=0,amp_sustain=1,amp_decay_s=.08,glide_s=.08)
    rows[-1]['patch']['reverb']={'mix':.12,'decay':.7}
    rows[-1]['limitations']=['The demonstrated external delay is unavailable; this patch includes only our small-room reverb.']
    return rows


def time_setting(position, attack=False):
    # Printed contour ticks: 0, 10, 200, 600 ms, then 1, 5, 10 seconds.
    # Their pointer angles span a non-linear scale; interpolate measured ticks.
    x=[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1]
    y=[0,.01,.2,.6,.8,1,2,5,7,9,10]
    return float(np.interp(position,x,y))


def manual_bank():
    charts=json.loads((ROOT/'presets/video-banks/timlfk-charts.json').read_text())
    rows=[]
    for index,chart in enumerate(charts):
        name=chart['name'].replace('‘',"'").replace('’',"'")
        patch=base('TL - '+name)
        p=patch['parameters'];k=chart['knobs'];s=chart['switches'];sel=chart['selections']
        limits=[]
        def switch(name,default=0):
            return default if s.get(name) is None else s[name]
        for osc in range(1,4):
            selection=sel.get(f'osc{osc}_range',3)
            p[f'osc{osc}_wave']=sel.get(f'osc{osc}_wave',2)
            p[f'osc{osc}_octave']=selection-3 if selection else 0
            p[f'osc{osc}_low']=int(selection==0)
            tune=(k.get(f'osc{osc}_tune',.5)-.5)*14
            p[f'osc{osc}_tune']=round(max(-7,min(7,tune)),3)
            p[f'osc{osc}_level']=k.get(f'osc{osc}_level',0)*switch(f'{osc}_on')
        p.update(osc3_keyboard=switch('osc3_keyboard',1),noise_level=k.get('noise_level',0)*switch('noise_on'),
                 noise_color=switch('noise_color'),keytrack_1=switch('keytrack_1'),keytrack_2=switch('keytrack_2'),
                 pitch_mod_enabled=switch('pitch_mod'),filter_mod_enabled=switch('filter_mod'),
                 mod_source_1=switch('source1'),mod_source_2=switch('source2',int('lfo_rate' in k)),
                 mod_mix=k.get('mod_mix',0),mod_amount=chart['wheel'],lfo_wave=chart.get('lfo_wave',0),
                 pitch_mod_depth=12,filter_mod_depth=5,
                 lfo_rate_hz=.05*1000**k.get('lfo_rate',.5),
                 glide_s=2*k.get('glide',0)**2*switch('glide'),release_enabled=switch('release',1),
                 filter_sustain=k.get('filter_sustain',0),amp_sustain=k.get('amp_sustain',1),
                 resonance=min(1.1,1.1*k.get('resonance',0)),
                 cutoff_hz=max(20,min(18000,10*2000**k.get('cutoff',.5))),
                 filter_env_octaves=8*k.get('contour',0))
        # Charts showing an arrow next to the wheel describe a gesture, not
        # a permanent full-depth modulation. Start low on keyboard patches.
        if chart['name'] in ('Sawyer = Bass','Kraft Bass','Sub Bass','Classic Stanley','Nothin’ Lead','The Jump','Outlaw'):
            p['mod_amount']=0
        if p['osc3_low']:
            # Keep the original LO oscillator calculation, not an extra LFO.
            p['osc3_fixed_hz']=2
        elif not p['osc3_keyboard']:
            p['osc3_fixed_hz']=220
        for source,target,maximum,default in [('filter_attack','filter_attack_s',3,0),('filter_decay','filter_decay_s',5,.2),('amp_attack','attack_s',3,0),('amp_decay','amp_decay_s',5,.2)]:
            value=time_setting(k[source]) if source in k else default
            if value>maximum:limits.append(f'{source} shortened from {value:.2f}s to {maximum}s (engine limit).')
            p[target]=max(0 if 'attack' in source else .005,min(maximum,value))
        if switch('external_on') and k.get('external_level',0)>.01:
            p['feedback_level']=.7*k['external_level']
            limits.append('Normalized external-input feedback approximated by the existing engine feedback path.')
        if not any(p[f'osc{i}_level'] for i in range(1,4)) and p['noise_level']==0:
            # Seed the existing resonant filter, as analogue circuit noise would.
            p['noise_level']=.0001
            p['resonance']=1.1
            limits.append('Filter-only sound: tiny noise seed starts resonance. Oscillator phase, tracking and modulation can differ from hardware.')
        if name=='West Coast Ghost Lead':
            p['cutoff_hz']=440/(110/49)**((p['keytrack_1']+2*p['keytrack_2'])/3)
        patch=validate_patch(patch)
        patch['reverb']={'mix':.035,'decay':.45}
        rows.append(dict(patch=patch,video=VIDEOS['TL']+'&t='+str(int(chart['video_start_s'])),
                         manual=MANUAL+'#page='+str(chart['page']),source='official manual vector chart',
                         limitations=limits))
    return rows


def render(patch, notes=(48,55,60,67), rate=24000, segment=1.6, wheel=None):
    size=round(rate*segment);frames=size*len(notes)
    controls=[np.zeros(frames,np.float32) for _ in range(5)]
    controls[3][:]=1;controls[4][:]=patch['parameters']['resonance']
    for i,note in enumerate(notes):
        start=i*size
        controls[0][start:start+size]=440*2**((note-69)/12)
        controls[1][start:start+int(size*.65)]=1
        controls[2][start]=1
    p=patch['parameters'].copy()
    if wheel is not None:p['mod_amount']=wheel
    params=np.array([p[s.name] for s in MODEL_D_PARAMETERS],np.float64)
    out=np.zeros(frames,np.float32);voice=NativeVoice(rate,'modeld')
    try:
        for start in range(0,frames,256):
            end=min(start+256,frames)
            voice.process(out[start:end],[c[start:end] for c in controls],params,ARCHITECTURES['modeld'])
    finally:voice.close()
    assert np.isfinite(out).all(),patch['name']
    return out


def slug(name):
    return re.sub('-+','-',re.sub('[^A-Za-z0-9_-]+','-',name)).strip('-')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    existing={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'presets/user').glob('*.json')}
    rows=doctor_mix()+manual_bank()
    report=[]
    for row in rows:
        patch=row.pop('patch');name=patch['name'];path=ROOT/'presets/user'/(slug(name)+'.json')
        trials=[render(patch,notes=(36,48,60,72,84)),render(patch,notes=(36,48,60,72,84),wheel=1)]
        peak=max(float(np.max(abs(a))) for a in trials)
        if peak<1e-7:raise ValueError('Silent patch: '+name)
        patch['output_gain_db']=round(max(-24,min(24,20*math.log10(.85/peak))),2)
        patch=validate_patch(patch)
        if not path.exists():
            with path.open('x') as handle:handle.write(json.dumps(patch,indent=2)+'\n')
        actual=read_patch(path)
        low=any(word in name for word in ('Bass','Kick','Toms'))
        audio=render(actual,notes=(48,51,53,48) if low else (60,67,72,64),rate=48000)
        room=Reverb(48000)
        try:
            room.configure(actual['reverb']);room.process(audio)
        finally:room.close()
        audio*=.126*10**(actual['output_gain_db']/20)
        assert np.isfinite(audio).all() and 1e-7<float(np.max(abs(audio)))<.98,name
        target=OUT/(slug(name)+'.wav')
        with wave.open(str(target),'wb') as handle:
            handle.setparams((1,2,48000,0,'NONE','not compressed'))
            handle.writeframes(np.round(audio*32767).astype('<i2').tobytes())
        report.append(dict(name=name,file=str(path.relative_to(ROOT)),audio=target.name,
                           peak=float(np.max(abs(audio))),rms=float(np.sqrt(np.mean(audio**2))),
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest(),**row))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in existing.items())
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    sections=[]
    for title,prefix in [('Doctor Mix: five Minimoog sounds','DM'),('TimLfk: 44 Model D patches','TL')]:
        cards=[]
        for row in report:
            if not row['name'].startswith(prefix):continue
            links=f'<a href="{row["video"]}">Video reference</a>'
            if row.get('manual'):links+=f' · <a href="{row["manual"]}">Moog chart</a>'
            warning=' '.join(row['limitations'])
            cards.append(f'<article><h3>{html.escape(row["name"])}</h3><audio controls preload="none" src="{row["audio"]}"></audio><p>{links}</p><p>{html.escape(warning)}</p></article>')
        sections.append('<h2>'+title+'</h2>'+''.join(cards))
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Video patch banks</title><style>body{background:#181a1b;color:#eee;font:17px system-ui;max-width:850px;margin:3em auto;padding:1em}article{border-bottom:1px solid #555;padding:1em}a{color:#a9d6ff}audio{width:100%}p{line-height:1.5}</style><h1>Video patch banks</h1><p>Playable adaptations in the existing 24 dB Model D engine. These recordings use a simple test phrase, not the video performance. Source links let you compare. Numerical checks verify sound output, not a perceptual match.</p>'+''.join(sections))
    print(f'Installed/validated {len(report)} patches; preserved {len(existing)} existing files. '+str(OUT/'index.html'))


if __name__=='__main__':main()
