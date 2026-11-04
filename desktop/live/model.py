from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from eq import DEFAULT as EQ_DEFAULT, validate as validate_eq

from reverb import DEFAULT as REVERB_DEFAULT, validate as validate_reverb

ROOT=Path(__file__).resolve().parents[2]
USER_PATCHES=ROOT/'presets/user'
ARCHITECTURES={'svf12':0,'ladder12':1,'ladder24':2,'modeld':3,'modeld18':4}


@dataclass(frozen=True)
class Parameter:
    name: str
    label: str
    group: str
    minimum: float
    maximum: float
    logarithmic: bool=False
    multiplier: float=1
    suffix: str=''
    choices: tuple=()

    def from_position(self,position):
        fraction=max(0,min(1000,position))/1000
        if self.logarithmic:
            return self.minimum*(self.maximum/self.minimum)**fraction
        value=self.minimum+(self.maximum-self.minimum)*fraction
        return float(round(value)) if self.choices else value

    def position(self,value):
        if self.logarithmic:
            fraction=math.log(value/self.minimum)/math.log(self.maximum/self.minimum)
        else:
            fraction=(value-self.minimum)/(self.maximum-self.minimum)
        return round(max(0,min(1,fraction))*1000)


PARAMETERS=[
    Parameter('pulse_blend','Saw → Pulse','Oscillators',0,1),
    Parameter('pulse_width','Pulse Width','Oscillators',.08,.92),
    Parameter('detune_cents','Oscillator Detune','Oscillators',-25,25,suffix=' ct'),
    Parameter('sub_level','Sub Level','Oscillators',0,.8),
    Parameter('cutoff_hz','Cutoff','Filter',20,10000,True,suffix=' Hz'),
    Parameter('filter_env_octaves','Envelope Depth','Filter',0,8,suffix=' oct'),
    Parameter('filter_decay_s','Filter Decay','Envelopes',.01,3,True,1000,' ms'),
    Parameter('attack_s','Amp Attack','Envelopes',.0002,1,True,1000,' ms'),
    Parameter('amp_decay_s','Amp Decay','Envelopes',.01,4,True,1000,' ms'),
    Parameter('amp_sustain','Amp Sustain','Envelopes',0,1),
    Parameter('release_s','Amp Release','Envelopes',.01,5,True,1000,' ms'),
    Parameter('resonance','Resonance','Filter',0,.94),
    Parameter('mixer_drive','Mixer Drive','Drive & Motion',.1,5),
    Parameter('sub_cutoff_hz','Sub Cutoff','Filter',20,3000,True,suffix=' Hz'),
    Parameter('glide_s','Glide','Drive & Motion',0,1,False,1000,' ms'),
    Parameter('output_drive','Output Drive','Drive & Motion',.1,2),
    Parameter('tune_cents','Master Tuning','Oscillators',-100,100,suffix=' ct'),
    Parameter('filter_attack_s','Filter Attack','Envelopes',.0002,1,True,1000,' ms'),
    Parameter('filter_sustain','Filter Sustain','Envelopes',0,1),
    Parameter('filter_curve','Sweep Curve','Filter',.25,3),
    Parameter('pulse_env_depth','Pulse Envelope','Drive & Motion',-.35,.35),
    Parameter('filter_key_tracking','Keyboard Tracking','Filter',0,1.5),
    Parameter('resonance_env_depth','Resonance Envelope','Drive & Motion',-.35,.5)]
NAMES=[parameter.name for parameter in PARAMETERS]
SPECS={parameter.name:parameter for parameter in PARAMETERS}

WAVES=('Triangle','Triangle / Saw','Saw','Square','Pulse 25%','Pulse 10%')
RANGES=("32′ (-2 oct)","16′ (-1 oct)","8′ (0 oct)","4′ (+1 oct)","2′ (+2 oct)")
SWITCH=('Off','On')
MODEL_D_PARAMETERS=[]
for oscillator in range(1,4):
    group=f'Oscillator {oscillator}'
    waves=WAVES if oscillator!=3 else ('Triangle','Reverse Saw','Saw','Square','Pulse 25%','Pulse 10%')
    MODEL_D_PARAMETERS.extend([
        Parameter(f'osc{oscillator}_wave','Waveform',group,0,5,choices=waves),
        Parameter(f'osc{oscillator}_octave','Range',group,-2,2,choices=RANGES),
        Parameter(f'osc{oscillator}_tune','Tuning',group,-7,7,suffix=' st'),
        Parameter(f'osc{oscillator}_low','Low Frequency',group,0,1,choices=SWITCH)])
MODEL_D_PARAMETERS.extend([
    Parameter('osc3_keyboard','Keyboard Follow','Oscillator 3',0,1,choices=SWITCH),
    Parameter('osc3_fixed_hz','Untracked Frequency','Oscillator 3',.1,2000,True,suffix=' Hz'),
    Parameter('osc1_level','Oscillator 1','Mixer',0,1),
    Parameter('osc2_level','Oscillator 2','Mixer',0,1),
    Parameter('osc3_level','Oscillator 3','Mixer',0,1),
    Parameter('noise_level','Noise','Mixer',0,1),
    Parameter('noise_color','Noise Colour','Mixer',0,1,choices=('White','Pink-like')),
    Parameter('mixer_drive','Mixer Drive','Mixer',.2,5),
    Parameter('feedback_level','Feedback Cable','Mixer',0,.7),
    Parameter('output_drive','Output Drive','Mixer',.2,2),
    Parameter('cutoff_hz','Cutoff','Filter',20,18000,True,suffix=' Hz'),
    Parameter('resonance','Resonance','Filter',0,1.1),
    Parameter('filter_env_octaves','Contour Amount','Filter',-6,8,suffix=' oct'),
    Parameter('filter_mode','Filter Type','Filter',0,1,choices=('Low-pass','High-pass')),
    Parameter('keytrack_1','Keyboard Control ⅓','Filter',0,1,choices=SWITCH),
    Parameter('keytrack_2','Keyboard Control ⅔','Filter',0,1,choices=SWITCH),
    Parameter('filter_attack_s','Filter Attack','Contours',0,3,False,1000,' ms'),
    Parameter('filter_decay_s','Filter Decay / Release','Contours',.005,5,True,1000,' ms'),
    Parameter('filter_sustain','Filter Sustain','Contours',0,1),
    Parameter('attack_s','Amp Attack','Contours',0,3,False,1000,' ms'),
    Parameter('amp_decay_s','Amp Decay / Release','Contours',.005,5,True,1000,' ms'),
    Parameter('amp_sustain','Amp Sustain','Contours',0,1),
    Parameter('release_enabled','Decay on Key Release','Contours',0,1,choices=SWITCH),
    Parameter('glide_s','Glide','Modulation',0,2,False,1000,' ms'),
    Parameter('tune_cents','Master Tuning','Modulation',-100,100,suffix=' ct'),
    Parameter('lfo_rate_hz','LFO Rate','Modulation',.05,200,True,suffix=' Hz'),
    Parameter('lfo_wave','LFO Waveform','Modulation',0,1,choices=('Triangle','Square')),
    Parameter('mod_source_1','Mod Source 1','Modulation',0,1,choices=('Oscillator 3','Filter Contour')),
    Parameter('mod_source_2','Mod Source 2','Modulation',0,1,choices=('Noise','LFO')),
    Parameter('mod_mix','Source 1 → Source 2','Modulation',0,1),
    Parameter('mod_amount','Mod Wheel Amount','Modulation',0,1),
    Parameter('pitch_mod_enabled','Oscillator Modulation','Modulation',0,1,choices=SWITCH),
    Parameter('pitch_mod_depth','Pitch Mod Depth','Modulation',0,12,suffix=' st'),
    Parameter('filter_mod_enabled','Filter Modulation','Modulation',0,1,choices=SWITCH),
    Parameter('filter_mod_depth','Filter Mod Depth','Modulation',0,6,suffix=' oct')])
MODEL_D_NAMES=[parameter.name for parameter in MODEL_D_PARAMETERS]


def engine_key(architecture):
    return 'modeld' if architecture in ('modeld','modeld18') else 'bass'


def parameters_for(architecture):
    return MODEL_D_PARAMETERS if engine_key(architecture)=='modeld' else PARAMETERS


def specs_for(architecture):
    return {parameter.name:parameter for parameter in parameters_for(architecture)
            if not (engine_key(architecture)=='modeld' and parameter.name=='filter_mode')}


def validate_patch(data):
    if not isinstance(data,dict) or data.get('architecture') not in ARCHITECTURES:
        raise ValueError('Unsupported synth architecture')
    values=data.get('parameters',{})
    parameters=parameters_for(data['architecture'])
    if not isinstance(values,dict) or set(values)!={parameter.name for parameter in parameters}:
        raise ValueError(f'The patch must contain the {len(parameters)} supported parameters for its engine')
    checked={}
    for parameter in parameters:
        value=values[parameter.name]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError(f'Invalid value for {parameter.label}')
        if not parameter.minimum<=value<=parameter.maximum:
            raise ValueError(f'{parameter.label} is outside the supported range')
        if parameter.choices and value!=round(value):
            raise ValueError(f'{parameter.label} requires a discrete selection')
        checked[parameter.name]=float(value)
    # Keep the reserved native slot and old engine ID readable, but canonicalize
    # imported patches to the single supported Model D filter.
    architecture=data['architecture']
    if engine_key(architecture)=='modeld':
        architecture='modeld'
        checked['filter_mode']=0.0
    result={'format':'electribe-desktop-patch-v2' if engine_key(data['architecture'])=='modeld' else 'electribe-desktop-patch-v1',
            'name':str(data.get('name','Untitled'))[:80],
            'architecture':architecture,'parameters':checked}
    if engine_key(data['architecture'])=='modeld':
        gain=data.get('output_gain_db',0)
        if isinstance(gain,bool) or not isinstance(gain,(int,float)) or not math.isfinite(gain) or not -24<=gain<=24:
            raise ValueError('Patch volume must be between -24 and +24 dB')
        result['output_gain_db']=float(gain)
    result['eq']=validate_eq(data.get('eq',EQ_DEFAULT))
    result['reverb']=validate_reverb(data.get('reverb',REVERB_DEFAULT))
    return result


def read_patch(path):
    return validate_patch(json.loads(Path(path).read_text()))


def save_patch(name,data,directory=None):
    name=name.strip()
    if not name or len(name)>80:
        raise ValueError('Choose a patch name between 1 and 80 characters')
    patch=validate_patch({**data,'name':name})
    directory=Path(directory) if directory is not None else USER_PATCHES
    directory.mkdir(parents=True,exist_ok=True)
    stem=re.sub(r'[^A-Za-z0-9_-]+','-',name).strip('-') or 'patch'
    for number in range(1,10000):
        path=directory/(stem+('' if number==1 else f'-{number}')+'.json')
        try:
            with path.open('x') as handle:
                json.dump(patch,handle,indent=2)
                handle.write('\n')
            return path
        except FileExistsError:
            continue
    raise ValueError('Too many patches with this name')


def patch_paths():
    # Factory/experiment files remain reference archives, outside the active library.
    return sorted(USER_PATCHES.glob('*.json'))


class Notes:
    def __init__(self):
        self.order=[]
        self.down=set()
        self.sustain=set()
        self.bends={}

    @property
    def active(self):
        return self.order[-1] if self.order else None

    def note_on(self,channel,note,velocity):
        key=(channel,note)
        self.order=[entry for entry in self.order if entry[:2]!=key]
        self.down.add(key)
        self.order.append((channel,note,velocity))

    def note_off(self,channel,note):
        key=(channel,note)
        self.down.discard(key)
        if channel not in self.sustain:
            self.order=[entry for entry in self.order if entry[:2]!=key]

    def pedal(self,channel,value):
        if value>=64:
            self.sustain.add(channel)
        else:
            self.sustain.discard(channel)
            self.order=[entry for entry in self.order if entry[0]!=channel or entry[:2] in self.down]

    def release_channel(self,channel):
        self.order=[entry for entry in self.order if entry[0]!=channel]
        self.down={key for key in self.down if key[0]!=channel}
        self.sustain.discard(channel)

    def panic(self):
        self.order.clear()
        self.down.clear()
        self.sustain.clear()
        self.bends.clear()
