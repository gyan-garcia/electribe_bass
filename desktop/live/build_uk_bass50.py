"""Curate a bass-focused bank in memory; install only 50 validated finalists.

No network, audio-device access, engine changes, or replacement of saved presets.
Run from the repository root with desktop/live/.venv/bin/python.
"""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import time
import wave

import numpy as np
from scipy import signal

from engine import NativeVoice
from eq import Equalizer
from model import ARCHITECTURES, MODEL_D_PARAMETERS, ROOT, read_patch, validate_patch
from modeld_preview import factory
from reverb import Reverb

OUT=ROOT/'desktop/live/outputs/uk-bass50'
BANK=ROOT/'presets/banks/uk-bass50'
SOURCES={
 'moog':{'title':'Moog Model D manual: bass and lead charts','url':'https://cdn.inmusicbrands.com/Moog/Model%20D/Minimoog_Model_D_Manual.pdf','basis':'Original chart architectures; redesigned controls, not verbatim imports.'},
 'dm':{'title':'Doctor Mix: Top 5 Greatest Minimoog Sounds','url':'https://www.youtube.com/watch?v=cxDTIpWvtzo','basis':'Single-saw contour bass and saw/square octave layering.'},
 'alex':{'title':'Alex Ball: The Prodigy Synth Tutorial','url':'https://www.youtube.com/watch?v=KwL2S5LRzFM','basis':'At 12:10: single low saw, resonant low-pass, short contour and drive. At 18:27: acid saw, octave movement, slides and distortion.'},
 'fatboy':{'title':'Synth History: interview with Fatboy Slim','url':'https://www.synthhistory.com/post/interview-with-fatboy-slim','basis':'Artist describes sample-based production and the TB-303; style context, not exact patch settings.'},
 'roland':{'title':'Roland: Beyond Acid','url':'https://articles.roland.com/beyond-acid-pushing-the-tb-303-into-new-sonic-territory/','basis':'Resonance, filter-envelope decay, waveform choice and slide as acid performance controls.'},
 'reese':{'title':'Marc Adamo / Attack: Reese Bass','url':'https://www.attackmagazine.com/technique/video-tutorials/reese-bass/','basis':'Reese sound-design reference; our detuned-oscillator versions are original Model D adaptations.'},
 'garage':{'title':'Attack: Making 3 Garage Basslines with Sublab','url':'https://www.attackmagazine.com/technique/synth-secrets/making-3-garage-basslines-with-sublab/','basis':'Triangle starting point; 38/53 ms attacks, filtered saturation, and contrasting softer and punchier bass roles.'},
 'sub':{'title':'Attack: Subby Bass with U-He Ace','url':'https://www.attackmagazine.com/technique/synth-secrets/subby-bass-with-u-he-ace/','basis':'Triangle sub, shaped amplitude, small pitch transient and saturation. No external chorus copied.'},
 'approved':{'title':'Existing MYXA approved bass architecture','url':'','basis':'User-approved resonant bass: local sonic reference; existing preset files are never modified.'}}
GROUPS={'Big Beat':10,'Acid':8,'Garage':8,'Jungle':8,'Rubber':8,'Lush':8}


def recipes():
    rows=[]
    def add(group,name,voices,cut,res,depth,decay,sustain,**kw):
        rows.append(dict(group=group,name=name,voices=voices,cut=cut,res=res,depth=depth,decay=decay,
                         sustain=sustain,**kw))
    # voices: waveform, octave, level, fine tuning in semitones. All recipes are
    # intentionally authored for our engine, rather than guessing analogue pots.
    add('Big Beat','Warehouse Bite',[(2,0,.8,0),(3,-1,.34,0)],160,.3,4.2,.23,.18,drive=1.8,feedback=.08,ampdec=.32,ampsus=.62,cue='Saw bite above a square foundation; short broken-beat notes.',sources=['alex','dm'])
    add('Big Beat','Essex Pressure',[(2,0,.88,0)],210,.67,3.1,.18,.04,drive=2.1,feedback=.12,ampdec=.25,ampsus=.7,cue='Driven single-saw growler; a Prodigy-influenced tone, not a record preset.',sources=['alex'])
    add('Big Beat','Boutique Bounce',[(2,0,.7,0),(0,0,.35,0)],190,.46,3.7,.35,.12,drive=1.4,ampdec=.4,ampsus=.55,glide=.018,cue='Springy resonant bass for sample-heavy big beat.',sources=['fatboy','dm'])
    add('Big Beat','Chemical Rubber',[(1,0,.8,0),(3,-1,.22,0)],120,.56,4.6,.51,.05,drive=1.15,attack=.009,ampdec=.62,ampsus=.25,cue='Longer vowel-shaped sweep with a solid sub octave.',sources=['alex','moog'])
    add('Big Beat','Concrete Stomp',[(3,0,.75,0),(2,1,.16,.02)],230,.18,2.6,.14,0,drive=2.6,feedback=.16,ampdec=.19,ampsus=.48,cue='Compact square-wave bass with a hard upper edge.',sources=['moog','alex'])
    add('Big Beat','Breaks Ripper',[(4,0,.72,0),(2,0,.25,.065)],260,.38,3.4,.27,.04,drive=2.3,ampdec=.33,ampsus=.62,cue='Narrow pulse and saw rasp; leave gaps around the kick.',sources=['alex','moog'])
    add('Big Beat','Rave Octave',[(2,0,.64,0),(2,1,.32,.012),(0,-1,.18,0)],170,.24,4.7,.22,.08,drive=1.8,ampdec=.28,ampsus=.5,cue='Octave-stacked attack with a triangle floor.',sources=['moog','dm'])
    add('Big Beat','Bristol Grit',[(1,0,.74,0),(0,0,.26,.012)],140,.16,2.1,.72,.22,drive=2.15,attack=.012,ampdec=.85,ampsus=.58,cue='Soft-fronted trip-hop bass with low-mid grit.',sources=['sub','fatboy'])
    add('Big Beat','Floorboard',[(2,0,.85,0),(0,-1,.18,0)],115,.07,3.2,.12,.1,drive=2.8,ampdec=.21,ampsus=.74,cue='Low-resonance distorted saw for dry, punchy basslines.',sources=['alex','dm'])
    add('Big Beat','Circuit Snarl',[(5,0,.68,0),(0,0,.25,0)],320,.61,2.4,.32,.07,drive=1.7,feedback=.19,ampdec=.38,ampsus=.48,cue='Thin pulse excites a resonant, snarling midrange.',sources=['moog'])
    add('Big Beat','Dark Alley',[(2,0,.8,0),(3,0,.2,-.03)],95,.32,3.5,.42,.05,drive=2.3,ampdec=.48,ampsus=.6,cue='Dark, driven bass with a brief opening transient.',sources=['alex'])
    add('Big Beat','Broken Amp',[(3,0,.76,0),(2,1,.21,-.06)],400,.11,1.8,.19,.02,drive=3,feedback=.22,ampdec=.26,ampsus=.45,cue='Rough square-wave bite, restrained feedback.',sources=['moog'])
    add('Acid','Brighton Acid',[(2,0,.85,0)],200,.72,4.1,.22,0,drive=1.5,glide=.045,ampdec=.2,ampsus=.9,cue='Saw acid voiced for big-beat patterns; perform the cutoff.',sources=['roland','fatboy','alex'])
    add('Acid','Claustro Saw',[(2,0,.82,0)],150,.81,4.7,.16,0,drive=1.9,glide=.035,ampdec=.18,ampsus=.85,cue='High-resonance saw with a fast, driven contour; inspired adaptation.',sources=['alex','roland'])
    add('Acid','Square Squelch',[(3,0,.8,0)],180,.76,3.6,.3,.02,drive=1.35,glide=.055,cue='Hollow square acid, less upper fizz than a saw.',sources=['roland'])
    add('Acid','Liquid Coil',[(4,0,.78,0)],110,.68,5.1,.54,.03,drive=1.05,attack=.006,glide=.07,ampsus=.8,cue='Pulse-driven liquid vowel with a longer decay.',sources=['roland','moog'])
    add('Acid','Acid Underpass',[(2,0,.73,0),(0,0,.13,0)],80,.63,4.4,.38,.04,drive=1.8,glide=.03,cue='Darker acid body, with a modest triangle reinforcement.',sources=['roland'])
    add('Acid','Rusty Needle',[(5,0,.78,0)],360,.83,2.7,.13,0,drive=1.7,ampdec=.17,ampsus=.65,cue='Sharp, short pulse squelch for busy sixteenths.',sources=['roland','moog'])
    add('Acid','Chrome Slide',[(2,0,.8,0)],285,.58,2.8,.64,.14,drive=1.3,glide=.1,ampdec=.7,ampsus=.8,cue='Longer held acid notes with audible portamento.',sources=['roland'])
    add('Acid','Bubble Circuit',[(3,0,.75,0)],85,.85,5.6,.26,0,drive=.85,attack=.008,glide=.025,ampdec=.32,ampsus=.55,cue='Round bubble at the bottom of a wide envelope sweep.',sources=['roland','moog'])
    add('Acid','Motorway',[(2,0,.8,0)],420,.66,1.9,.105,0,drive=1.8,glide=.02,cue='Fast and bright saw-acid pulse.',sources=['roland'])
    add('Acid','Green Pulse',[(4,0,.8,0)],210,.64,3.3,.38,.08,drive=1.2,glide=.04,cue='Medium-decay pulse acid with a restrained peak.',sources=['roland'])
    add('Garage','Two Step Triangle',[(0,0,.86,0)],185,.58,1.5,1.8,0,drive=1.8,attack=.038,ampdec=.86,ampsus=.18,release=1,cue='Soft triangle entry and sustained filter fall, adapted from SubLab Sound 1.',sources=['garage'])
    add('Garage','Velvet Sub',[(0,0,.88,0)],100,.14,.8,.62,.15,drive=2.1,attack=.053,ampdec=.872,ampsus=.3,release=1,cue='Dark, rounded sub with a deliberately soft front.',sources=['garage'])
    add('Garage','Organ Step',[(0,0,.7,0),(0,1,.28,0)],550,.1,1.4,.09,0,drive=1.05,ampdec=.24,ampsus=.48,cue='Octave triangle pluck; an organ-like role without claiming an M1 emulation.',sources=['sub','moog'])
    add('Garage','Hollow Swing',[(3,0,.68,0),(0,0,.3,0)],160,.31,2.6,.2,.03,drive=1.2,ampdec=.28,ampsus=.34,glide=.022,cue='Hollow square body with a small percussive knock.',sources=['garage','moog'])
    add('Garage','Rubber Sole',[(1,0,.78,0)],130,.48,4.4,.4,.06,drive=1.15,attack=.006,ampdec=.5,ampsus=.38,cue='Bouncy filter contour, stable single-oscillator low end.',sources=['garage','dm'])
    add('Garage','Tin Roof',[(0,0,.84,0)],340,.18,2.1,.14,.02,drive=1.4,ampdec=.21,ampsus=.38,fm=.095,cue='A small audio-rate pitch-modulation edge; not a DX-style FM reconstruction.',sources=['sub','moog'])
    add('Garage','Late Train',[(0,0,.82,0),(3,1,.12,0)],220,.22,2.2,.31,0,drive=1.6,ampdec=.32,ampsus=.52,glide=.065,cue='Rounded body with a square overtone that survives small speakers.',sources=['garage','sub'])
    add('Garage','Bellied Pluck',[(0,0,.72,0),(0,1,.2,0)],720,.21,1.1,.18,.06,drive=1.15,ampdec=.25,ampsus=.2,fm=.055,cue='Light metallic transient over a rounded octave core.',sources=['sub','moog'])
    add('Garage','Pirate Bounce',[(4,0,.66,0),(0,0,.32,0)],145,.42,3.3,.24,.06,drive=1.55,ampdec=.28,ampsus=.58,cue='Pulse pluck with a triangle body for syncopated basslines.',sources=['garage'])
    add('Garage','Night Bus',[(0,0,.9,0)],145,.22,1.4,.9,.2,drive=1.3,attack=.026,ampdec=1.1,ampsus=.4,release=1,cue='Long, restrained low end for sparse arrangements.',sources=['garage','sub'])
    add('Jungle','Concrete Reese',[(0,0,.22,0),(2,0,.55,-.09),(2,0,.55,.09)],1100,.17,.8,.45,.4,drive=1.7,ampdec=.6,ampsus=.88,cue='Detuned saw beating above an anchored triangle fundamental.',sources=['reese'])
    add('Jungle','Shadow Reese',[(0,0,.24,0),(2,0,.5,-.055),(2,0,.5,.055)],320,.26,2.3,.8,.18,drive=1.5,attack=.012,ampdec=.9,ampsus=.8,cue='Darker, slower Reese movement with a modest contour.',sources=['reese'])
    add('Jungle','Hoover Floor',[(0,0,.26,0),(2,0,.52,-.16),(3,1,.27,.14)],900,.32,2.5,.26,.18,drive=2,ampdec=.45,ampsus=.76,cue='Detuned rave bass; this engine has no Juno PWM, so it is a hoover-inspired voice.',sources=['reese','alex'])
    add('Jungle','Low Tide',[(0,0,.86,0),(0,1,.14,0)],140,.1,.6,.42,.5,drive=1.1,attack=.008,ampdec=.7,ampsus=.95,cue='Clean, sustained sub with a quiet octave cue.',sources=['sub'])
    add('Jungle','Rolling Sub',[(0,0,.82,0)],230,.16,1.6,.36,.08,drive=1.35,ampdec=.5,ampsus=.34,glide=.045,punch=.11,cue='Triangle roller with a subtle short pitch drop.',sources=['sub'])
    add('Jungle','Ragga Pulse',[(3,0,.65,0),(0,0,.3,0)],310,.21,2.7,.12,.04,drive=1.6,ampdec=.2,ampsus=.42,cue='Short, square-led pluck that leaves room for busy breaks.',sources=['moog','reese'])
    add('Jungle','Metal Step',[(0,0,.8,0),(2,1,.14,.03)],580,.36,1.8,.16,0,drive=1.6,ampdec=.25,ampsus=.36,fm=.14,cue='Harder audio-rate modulation texture with a controlled bass body.',sources=['sub','moog'])
    add('Jungle','Dread Weight',[(0,0,.55,0),(2,0,.36,-.04),(2,0,.36,.04)],185,.2,2.6,.55,.2,drive=1.9,ampdec=.7,ampsus=.72,cue='A restrained Reese folded into a warm sub.',sources=['reese','sub'])
    add('Jungle','Underwater Dub',[(0,0,.8,0),(3,1,.14,0)],390,.4,-1.5,.52,.2,drive=1.25,attack=.018,ampdec=.8,ampsus=.7,cue='An inverted filter contour opens into the body of a held note.',sources=['sub','moog'])
    add('Jungle','Pressure Wave',[(1,0,.6,0),(2,0,.36,.11)],620,.27,1.5,.35,.14,drive=2.2,ampdec=.5,ampsus=.75,cue='A raspier two-oscillator bass with less detuning than a wide Reese.',sources=['reese'])
    add('Rubber','Elastic Foundation',[(2,0,.74,0),(0,0,.28,0)],95,.41,4.7,.85,.1,drive=.65,attack=.012,ampdec=.95,ampsus=.28,arch='modeld18',cue='Open 18 dB ladder tap and a slow resonant vowel; approved-engine lineage.',sources=['approved','dm'])
    add('Rubber','Liquorice',[(1,0,.8,0),(0,-1,.14,0)],105,.53,4.2,.65,.08,drive=.8,attack=.016,ampdec=.78,ampsus=.36,arch='modeld18',cue='Triangle/saw blend, soft onset and a darker resonant fall.',sources=['approved','moog'])
    add('Rubber','Roundhouse',[(3,0,.6,0),(0,0,.38,0)],155,.34,3.7,.38,.08,drive=1.05,ampdec=.5,ampsus=.55,cue='Square warmth under a clean, quick vowel.',sources=['dm','moog'])
    add('Rubber','Bubblegum',[(4,0,.72,0),(0,0,.23,0)],85,.65,5.2,.58,.03,drive=.7,attack=.01,ampdec=.7,ampsus=.22,arch='modeld18',cue='A wide pulse sweep with prominent but controlled resonance.',sources=['approved','moog'])
    add('Rubber','Soul Pocket',[(2,0,.8,0)],330,.18,4.4,.6,.12,drive=1,attack=.004,ampdec=.3,ampsus=.65,cue='A refined single-saw soul contour; dry and direct.',sources=['dm'])
    add('Rubber','Syrup Slide',[(1,0,.7,0),(3,-1,.2,0)],180,.26,2.8,1.1,.16,drive=.9,attack=.012,ampdec=1.3,ampsus=.5,glide=.11,release=1,cue='Long glides and a slow rounded filter fall.',sources=['dm','approved'])
    add('Rubber','Warm Current',[(0,0,.55,0),(2,0,.4,.025)],140,.38,3.8,.72,.18,drive=1.25,attack=.02,ampdec=.9,ampsus=.52,cue='Sub-rich Moog-style bass with a little oscillator movement.',sources=['moog','sub'])
    add('Rubber','Rubber Mallet',[(0,0,.62,0),(4,0,.29,0)],420,.57,2.3,.19,0,drive=.85,ampdec=.28,ampsus=.18,punch=.06,cue='Short resonant knock with a gentle pitch transient.',sources=['sub','moog'])
    add('Rubber','Amber Envelope',[(2,0,.72,0),(0,1,.15,0)],115,.46,4.6,.95,.07,drive=.75,attack=.028,ampdec=1.1,ampsus=.3,arch='modeld18',cue='A slower swelling edge and a deep resonant tail.',sources=['approved'])
    add('Rubber','Soft Machine',[(1,0,.8,0)],200,.24,2.8,.44,.15,drive=.85,attack=.015,ampdec=.6,ampsus=.62,cue='Understated analogue bass for fuller arrangements.',sources=['dm'])
    add('Lush','Velvet Monolith',[(0,0,.35,0),(2,0,.42,-.035),(2,0,.42,.035)],900,.18,1.4,1.4,.55,drive=.8,attack=.12,ampdec=1.5,ampsus=.85,release=1,room=.14,tail=1.3,cue='Slow detuned mono bass with a small dark room.',sources=['reese','moog'])
    add('Lush','Glass Harbour',[(0,0,.6,0),(0,1,.24,.012),(2,1,.14,-.025)],1600,.27,1.6,1.1,.45,drive=.65,attack=.075,ampdec=1.2,ampsus=.72,release=1,room=.16,tail=1.5,cue='Rounded, bright octave shimmer; melodic mono voice.',sources=['moog','sub'],role='lead')
    add('Lush','Afterglow',[(1,0,.52,0),(2,-1,.24,-.035),(2,0,.32,.035)],520,.32,2.3,1.6,.35,drive=.9,attack=.065,ampdec=1.8,ampsus=.65,release=1,room=.12,tail=1.2,cue='Warm octave body with a gentle opening and close.',sources=['moog','reese'])
    add('Lush','Wide Orbit',[(2,0,.4,-.06),(2,0,.4,.06),(0,-1,.23,0)],2200,.12,.6,1.1,.65,drive=.85,attack=.09,ampdec=1.3,ampsus=.9,release=1,room=.18,tail=1.5,cue='Broad beating in a mono signal; no stereo widening.',sources=['reese','moog'])
    add('Lush','Fifth Avenue',[(2,0,.55,0),(0,0,.24,0),(2,0,.18,7)],1200,.24,2.2,.75,.3,drive=.8,attack=.035,ampdec=.95,ampsus=.7,release=1,room=.1,tail=1.1,cue='A quiet fixed fifth above a thick mono root.',sources=['moog'],role='lead')
    add('Lush','Night Bloom',[(0,0,.45,0),(4,0,.36,-.025),(2,1,.14,.035)],800,.4,-1.5,1.4,.18,drive=.8,attack=.16,ampdec=1.8,ampsus=.75,release=1,room=.16,tail=1.8,cue='Slow inverse contour with a subtle pulse edge.',sources=['moog'])
    add('Lush','Amber Brass',[(2,0,.48,0),(2,0,.42,.04),(3,-1,.18,0)],450,.2,3.1,.85,.65,drive=.85,attack=.09,ampdec=1.2,ampsus=.85,release=1,room=.09,tail=1.0,cue='Soft brass-like mono swell above an octave foundation.',sources=['moog'],role='lead')
    add('Lush','Deep Horizon',[(0,0,.48,0),(1,0,.38,-.03),(2,0,.3,.03)],260,.25,1.5,2,.6,drive=.7,attack=.055,ampdec=2,ampsus=.9,release=1,room=.1,tail=1.4,cue='Low, full sustained bass with gentle detuned movement.',sources=['reese','sub'])
    add('Lush','Silk Ribbon',[(0,0,.55,0),(4,1,.22,.02)],1400,.21,1.7,.8,.4,drive=.7,attack=.08,ampdec=1.1,ampsus=.8,release=1,room=.17,tail=1.4,cue='Airy pulse octave over a round core.',sources=['moog'],role='lead')
    add('Lush','Low Lantern',[(1,0,.7,0),(0,-1,.2,0)],400,.18,1.8,1.5,.4,drive=.85,attack=.1,ampdec=1.7,ampsus=.8,release=1,room=.12,tail=1.3,cue='Dark, slow mono sustain for sparse passages.',sources=['moog','sub'])
    return rows


def make_patch(row,variant):
    p=factory()['init']['parameters'].copy()
    p.update(osc1_level=0,osc2_level=0,osc3_level=0,noise_level=0,
             cutoff_hz=row['cut'],resonance=row['res'],filter_env_octaves=row['depth'],
             filter_attack_s=row.get('attack',.004),filter_decay_s=row['decay'],filter_sustain=row['sustain'],
             attack_s=row.get('attack',.004),amp_decay_s=row.get('ampdec',.35),amp_sustain=row.get('ampsus',.8),
             release_enabled=row.get('release',0),glide_s=row.get('glide',.012),
             keytrack_1=1,keytrack_2=1 if row['group'] in ('Rubber','Lush','Jungle') else 0,
             mixer_drive=row.get('drive',1),feedback_level=row.get('feedback',0),output_drive=1,
             mod_source_1=0,mod_source_2=1,mod_mix=1,mod_amount=.06 if row['group']=='Lush' else 0,
             lfo_rate_hz=.23 if row['group']=='Lush' else 2.0,lfo_wave=0,
             filter_mod_enabled=1,filter_mod_depth=.8,pitch_mod_enabled=0,pitch_mod_depth=0)
    for i,(shape,octave,level,tune) in enumerate(row['voices'],1):
        p.update({f'osc{i}_wave':shape,f'osc{i}_octave':octave,f'osc{i}_level':level,f'osc{i}_tune':tune})
    if row.get('fm'):
        p.update(osc3_wave=0,osc3_octave=1,osc3_level=0,osc3_keyboard=1,
                 mod_source_1=0,mod_mix=0,mod_amount=row['fm'],pitch_mod_enabled=1,
                 pitch_mod_depth=4,filter_mod_enabled=0)
    if row.get('punch'):
        p.update(mod_source_1=1,mod_mix=0,mod_amount=row['punch'],pitch_mod_enabled=1,
                 pitch_mod_depth=12,filter_mod_enabled=0)
    if variant==1:
        p['cutoff_hz']*=.86;p['resonance']=max(.04,p['resonance']-.035)
        p['mixer_drive']*=.9;p['filter_env_octaves']+=.2
    elif variant==2:
        p['cutoff_hz']*=1.16;p['resonance']=min(.9,p['resonance']+.025)
        p['filter_decay_s']*=.9;p['mixer_drive']*=1.08
    patch=validate_patch(dict(name=row['name'],architecture=row.get('arch','modeld'),parameters=p))
    patch['reverb']={'mix':row.get('room',0),'decay':row.get('tail',.6)}
    # Conservative, fixed-frequency three-band tone shaping stays portable.
    if row['group']=='Big Beat':
        patch['eq'].update(enabled=True,low_db=1.2,mid_db=.7,high_db=-.5)
    elif row['group']=='Jungle':
        patch['eq'].update(enabled=True,low_db=1.5,mid_db=-.7,high_db=-1)
    return validate_patch(patch)


def render(patch,rate=24000,mode='screen',wheel=None):
    if mode=='phrase':
        notes=[31,31,43,34,36,43,29,41,36,39,43,34]
        lengths=[.24,.24,.36,.24,.36,.24,.36,.24,.48,.24,.36,.6]
    elif mode=='stress':
        notes=[24,31,36,43,48,55,60];lengths=[1.0]*7
    else:notes=[31,36,43];lengths=[.65]*3
    if mode=='lush':
        notes=[43,48,55];lengths=[2.0]*3
    ends=np.cumsum([0]+lengths);frames=round((ends[-1]+(2.6 if mode in ('phrase','lush') else .45))*rate)
    controls=[np.zeros(frames,np.float32) for _ in range(5)]
    controls[0][:]=440*2**((notes[-1]-69)/12);controls[3][:]=1;controls[4][:]=patch['parameters']['resonance']
    active=np.zeros(frames,bool)
    for i,note in enumerate(notes):
        start=round(ends[i]*rate);end=round(ends[i+1]*rate)
        controls[0][start:end]=440*2**((note-69)/12)
        gateend=end-round(min(.04,lengths[i]*.15)*rate)
        controls[1][start:gateend]=1;controls[2][start]=1
        active[start+round(.015*rate):gateend]=True
    p=patch['parameters'].copy()
    if wheel is not None:p['mod_amount']=wheel
    settings=np.array([p[s.name] for s in MODEL_D_PARAMETERS],np.float64)
    out=np.zeros(frames,np.float32);voice=NativeVoice(rate,'modeld')
    try:
        for start in range(0,frames,512):
            end=min(start+512,frames)
            voice.process(out[start:end],[c[start:end] for c in controls],settings,ARCHITECTURES[patch['architecture']])
    finally:voice.close()
    eq=Equalizer(rate);room=Reverb(rate)
    try:
        eq.configure(patch['eq']);eq.process(out)
        room.configure(patch['reverb']);room.process(out)
    finally:eq.close();room.close()
    return out,active


def describe(audio,active,rate):
    if not np.isfinite(audio).all():raise ValueError('Non-finite audio')
    rms=float(np.sqrt(np.mean(audio[active].astype(float)**2)))
    peak=float(np.max(abs(audio)));dc=float(abs(np.mean(audio)))
    if rms<1e-6 or peak<1e-5:raise ValueError('Silent audio')
    _,spec=signal.welch(audio[active],rate,nperseg=4096)
    freq=np.fft.rfftfreq(4096,1/rate);total=float(spec.sum())+1e-20
    bass=float(spec[(freq>=28)&(freq<300)].sum()/total)
    infrasonic=float(spec[freq<22].sum()/total)
    bright=float(spec[freq>=3500].sum()/total)
    edges=np.geomspace(28,min(10000,rate*.45),33)
    features=[float(spec[(freq>=a)&(freq<b)].sum()/total) for a,b in zip(edges[:-1],edges[1:])]
    # Include phrase dynamics so two patches with similar spectra but different
    # contour timing are not treated as the same sound.
    n=len(audio)//12
    envelope=[float(np.sqrt(np.mean(audio[i*n:(i+1)*n].astype(float)**2))) for i in range(12)]
    envelope=np.array(envelope)/(max(envelope)+1e-12)
    # A linear-power comparison mostly measures the common fundamental of all
    # basses. Log bands give the quieter harmonics a useful say in curation.
    harmonic=np.log10(np.array(features)+1e-7)
    harmonic-=harmonic.mean()
    harmonic/=np.linalg.norm(harmonic)+1e-12
    vector=np.concatenate([harmonic,envelope*.2])
    vector/=np.linalg.norm(vector)+1e-12
    return dict(rms=rms,peak=peak,dc=dc,bass_fraction=bass,infrasonic_fraction=infrasonic,
                brightness_fraction=bright,crest_db=20*math.log10(peak/rms),vector=vector)


def quality(metrics,row,variant):
    # This is a technical usability heuristic, not a perceptual quality model.
    target=.18
    score=1.0
    score-=max(0,metrics['crest_db']-15)*.025
    score-=metrics['infrasonic_fraction']*1.5
    score-=max(0,metrics['brightness_fraction']-.25)*.6
    score-=max(0,target-metrics['bass_fraction'])*.35 if row['group']!='Lush' else 0
    score-=min(.2,metrics['dc']/metrics['rms'])*.2
    score-=variant*.001
    return float(score)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def safe(name):return re.sub('-+','-',re.sub('[^A-Za-z0-9_-]+','-',name)).strip('-')
def write_wav(path,audio):
    assert np.isfinite(audio).all() and np.max(abs(audio))<.98
    with wave.open(str(path),'wb') as w:
        w.setparams((1,2,48000,0,'NONE','not compressed'))
        w.writeframes(np.round(audio*32767).astype('<i2').tobytes())


def verify_existing():
    catalog=json.loads((BANK/'catalog.json').read_text())
    assert len(catalog['patches'])==50
    assert len(list((ROOT/'presets/user').glob('UK50-*.json')))==50
    measures=[]
    for row in catalog['patches']:
        path=ROOT/row['file'];patch=read_patch(path)
        assert sha(path)==row['sha256'],f'Saved patch differs from bank: {path}'
        for wheel in (None,1):
            audio,mask=render(patch,48000,'stress',wheel=wheel)
            metrics=describe(audio,mask,48000)
            peak=float(np.max(abs(signal.resample_poly(audio,4,1))))*10**(patch['output_gain_db']/20)
            assert peak<.85 and metrics['rms']>1e-6,(row['name'],peak)
            measures.append(dict(name=row['name'],full_wheel=wheel==1,true_peak=peak))
        for key in ('audio','wheel_audio'):
            with wave.open(str(OUT/row[key])) as wav:
                assert wav.getframerate()==48000 and wav.getnchannels()==1 and wav.getsampwidth()==2
    snapshot=OUT/'protected-before.json'
    if snapshot.exists():
        assert all(sha(ROOT/p)==h for p,h in json.loads(snapshot.read_text()).items()),'A pre-existing user patch differs from the build snapshot'
    (OUT/'verification.json').write_text(json.dumps(dict(patches=50,keyboard_notes=[24,31,36,43,48,55,60],
        oversampling=4,measurements=measures),indent=2)+'\n')
    print('PASS: 50 patches; 100 normal/full-wheel checks at 48 kHz; 100 valid WAV files; saved source hashes match.')


def main():
    parser=argparse.ArgumentParser();actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--install',action='store_true');actions.add_argument('--verify',action='store_true')
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.verify:
        verify_existing();return
    protected={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'presets/user').glob('*.json')}
    if any(Path(p).name.startswith('UK50-') for p in protected):
        raise SystemExit('UK50 presets already exist; refusing to replace saved patches.')
    started=time.monotonic();candidates=[];audit=[]
    rows=recipes();assert len(rows)==62
    for i,row in enumerate(rows):
        variants=[]
        for v in range(3):
            patch=make_patch(row,v);audio,active=render(patch)
            m=describe(audio,active,24000);score=quality(m,row,v)
            variants.append(dict(row=row,patch=patch,metrics=m,score=score,variant=v))
            audit.append(dict(recipe=row['name'],variant=v,technical_score=score))
        candidates.append(max(variants,key=lambda c:c['score']))
        (OUT/'progress.json').write_text(json.dumps(dict(stage='screening',recipes=i+1,total=62,seconds=time.monotonic()-started)))
        if (i+1)%10==0:print(f'Screened {i+1}/62 recipes',flush=True)
    selected=[]
    for group,count in GROUPS.items():
        pool=[c for c in candidates if c['row']['group']==group]
        chosen=[]
        while len(chosen)<count:
            def rank(c):
                similarity=max((float(np.dot(c['metrics']['vector'],p['metrics']['vector'])) for p in selected+chosen),default=0)
                return c['score']-.22*max(0,similarity-.9)
            best=max(pool,key=rank);chosen.append(best);pool.remove(best)
        selected.extend(chosen)
    assert len(selected)==50
    report=[];prepared=[]
    for index,candidate in enumerate(selected,1):
        row=candidate['row'];patch=candidate['patch']
        patch['name']=f'UK50 {index:02d} {row["group"]} - {row["name"]}'
        # Calibrate after EQ/reverb, also checking full-wheel modulation and
        # keyboard extremes at the actual desktop sample rate.
        ordinary,active=render(patch,48000,'stress')
        raised,_=render(patch,48000,'stress',wheel=1)
        m=describe(ordinary,active,48000)
        peak=max(float(np.max(abs(signal.resample_poly(a,4,1)))) for a in (ordinary,raised))
        gain=min(.25/m['rms'],.82/peak)
        patch['output_gain_db']=round(max(-24,min(24,20*math.log10(gain))),2)
        patch=validate_patch(patch);gain=10**(patch['output_gain_db']/20)
        assert peak*gain<.85,(patch['name'],peak*gain)
        assert m['rms']*gain>.025,(patch['name'],'very low level')
        mode='lush' if row['group']=='Lush' else 'phrase'
        phrase,mask=render(patch,48000,mode)
        phrase*=gain*.126
        stem=safe(patch['name']);path=ROOT/'presets/user'/(stem+'.json')
        write_wav(OUT/(stem+'.wav'),phrase)
        # The page contrasts normal and full mod wheel without touching a device.
        wheel=(raised*gain*.126).astype(np.float32)
        write_wav(OUT/(stem+'-wheel.wav'),wheel)
        metrics={k:float(v) for k,v in m.items() if k!='vector'}
        record=dict(number=index,name=patch['name'],file=str(path.relative_to(ROOT)),audio=stem+'.wav',wheel_audio=stem+'-wheel.wav',
                    family=row['group'],role=row.get('role','bass'),description=row['cue'],sources=row['sources'],
                    provenance='Original source-informed sound design / adapted recipe; not an artist-used preset',
                    architecture=patch['architecture'],variant=candidate['variant'],technical_score=candidate['score'],
                    output_gain_db=patch['output_gain_db'],metrics=metrics,max_pre_master_peak=peak*gain,
                    audition_peak=float(np.max(abs(phrase))),playing_range='MIDI 31-55 (G1-G3)' if row['group']!='Lush' else 'MIDI 43-67 (G2-G4)',
                    wheel='Audio-rate pitch colour' if row.get('fm') else 'Filter-envelope pitch transient' if row.get('punch') else 'Triangle LFO to cutoff; full wheel increases movement')
        report.append(record);prepared.append((path,patch))
        (OUT/'progress.json').write_text(json.dumps(dict(stage='final validation',finalists=index,total=50,seconds=time.monotonic()-started)))
        if index%10==0:print(f'Validated {index}/50 finalists',flush=True)
    encoded=[json.dumps(p['parameters'],sort_keys=True)+p['architecture'] for _,p in prepared]
    assert len(set(encoded))==50,'Duplicate settings'
    assert all(sha(ROOT/p)==h for p,h in protected.items()),'Existing user patch changed'
    if args.install:
        created=[]
        try:
            for (path,patch),record in zip(prepared,report):
                with path.open('x') as f:f.write(json.dumps(patch,indent=2)+'\n')
                created.append(path);record['sha256']=sha(path)
                read_patch(path)
        except BaseException:
            for path in created:path.unlink()
            raise
    catalog=dict(name='MYXA UK Bass 50',status='Curated audition bank; listening approval remains subjective',
                 patch_count=50,bass_count=sum(r['role']=='bass' for r in report),sources=SOURCES,patches=report,
                 method=dict(recipes=62,in_memory_candidates=186,selection='Technical usability plus spectral/envelope diversity within six style quotas. Only 50 finalists written as patches.',
                             technical_metric_is_not_perceptual_ranking=True),
                 limits=['Model D-style core, not a complete Sub 37/303/FM/Juno emulation.',
                         'Mono synthesis and room; no chorus, delay, stereo unison, sampled attacks, oscillator sync or 303 accent circuitry.',
                         'Hardware CPU/memory budget unchanged by this desktop preset bank; no firmware flashing.'])
    BANK.mkdir(parents=True,exist_ok=True)
    (BANK/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    (OUT/'screening.json').write_text(json.dumps(audit,indent=2)+'\n')
    (OUT/'protected-before.json').write_text(json.dumps(protected,indent=2)+'\n')
    (OUT/'report.json').write_text(json.dumps(dict(installed=args.install,elapsed_s=time.monotonic()-started,existing_preserved=len(protected),
        engine_sha256=sha(ROOT/'desktop/live/native/modeld.c'),**catalog),indent=2)+'\n')
    cards=[]
    for r in report:
        links=' · '.join(f'<a href="{SOURCES[s]["url"]}">{html.escape(SOURCES[s]["title"])}</a>' if SOURCES[s]['url'] else html.escape(SOURCES[s]['title']) for s in r['sources'])
        cards.append(f'<article data-family="{r["family"]}"><h2>{html.escape(r["name"])}</h2><p>{html.escape(r["description"])}</p><audio controls preload="none" src="{r["audio"]}"></audio><details><summary>Mod wheel audition and playing notes</summary><p>{html.escape(r["wheel"])}. {r["playing_range"]}. {r["architecture"]}.</p><audio controls preload="none" src="{r["wheel_audio"]}"></audio><p>{links}</p></details></article>')
    buttons='<option value="all">All 50</option>'+''.join(f'<option>{g}</option>' for g in GROUPS)
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MYXA UK Bass 50</title><style>body{font:17px system-ui;background:#141719;color:#eee;max-width:850px;margin:2em auto;padding:1em}article{padding:1em;margin:1em 0;background:#20272b;border-radius:12px}p{line-height:1.5}audio{width:100%}a{color:#88dacc}select{padding:.7em;font:inherit}h2{font-size:1.15em}</style><h1>MYXA UK Bass 50</h1><p>42 bass patches and eight lush mono voices. Original sound designs informed by the sources below each patch. These are artist-inspired tones and adapted recipes, not authenticated record presets.</p><p>Auditions use the desktop default master level. Use headphones or speakers that reproduce bass. Choose a style:</p><select id="family">'+buttons+'</select>'+''.join(cards)+'<script>document.getElementById("family").onchange=e=>{document.querySelectorAll("article").forEach(x=>x.hidden=e.target.value!=="all"&&x.dataset.family!==e.target.value)};document.querySelectorAll("audio").forEach(a=>a.onplay=()=>document.querySelectorAll("audio").forEach(b=>{if(a!==b)b.pause()}))</script>')
    (OUT/'progress.json').write_text(json.dumps(dict(stage='complete',patches=50,installed=args.install,seconds=time.monotonic()-started)))
    print(f'Complete: 50 finalists; installed={args.install}; preserved={len(protected)}; '+str(OUT/'index.html'),flush=True)

if __name__=='__main__':main()
