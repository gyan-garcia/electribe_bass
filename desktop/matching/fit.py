import argparse
import ctypes
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np
from scipy import optimize, signal
from scipy.io import wavfile

from analyze import ROOT, REFERENCE, analyze, load_audio

NAMES = ['pulse_blend', 'pulse_width', 'detune_cents', 'sub_level', 'cutoff_hz',
         'filter_env_octaves', 'filter_decay_s', 'attack_s', 'amp_decay_s',
         'amp_sustain', 'release_s', 'resonance', 'mixer_drive', 'sub_cutoff_hz',
         'glide_s', 'output_drive']
BASE = np.array([0.5, 0.5, 0.7, 0.15, 160, 3.5, 0.15, 0.003, 0.22,
                 0.35, 0.07, 0.35, 1.4, 180, 0.003, 1.0], dtype=np.float64)
INDICES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12]
BOUNDS = [(0, 1), (.15, .85), (-7, 7), (0, .65), (40, 1200), (0, 6),
          (.03, .7), (.001, .025), (.04, .7), (.05, .9), (0, .93), (.5, 4)]
ARCHITECTURES = ['svf12', 'ladder12', 'ladder24']


class Renderer:
    def __init__(self, events, rate=24000, library_path=None, function_name='render_voice'):
        self.events = events
        self.rate = rate
        self.settings_count = 23 if function_name=='render_rubber_voice' else 16
        library = ctypes.CDLL(str(library_path or ROOT/'voice.so'))
        self.function = getattr(library,function_name)
        pointer = np.ctypeslib.ndpointer(dtype=np.float32, flags='C_CONTIGUOUS')
        self.function.argtypes = [pointer]*6 + [ctypes.c_int, ctypes.c_int,
                                  np.ctypeslib.ndpointer(dtype=np.float64, flags='C_CONTIGUOUS'), ctypes.c_int]
        self.function.restype = None

    def controls(self, start, duration):
        frames = round(duration*self.rate)
        pitch = np.full(frames, 49, dtype=np.float32)
        gate = np.zeros(frames, dtype=np.float32)
        trigger = np.zeros(frames, dtype=np.float32)
        for event in self.events:
            left = round((event['start']-start)*self.rate)
            right = round((event['end']-start)*self.rate)
            if right <= 0 or left >= frames:
                continue
            begin, end = max(0, left), min(frames, right)
            pitch[begin:end] = event['frequency']
            gate[begin:max(begin, min(end, right-round(.025*self.rate)))] = 1
            trigger[begin] = 1
        return pitch, gate, trigger

    def render(self, settings, architecture, controls, cutoff=None, resonance=None):
        if np.shape(settings)!=(self.settings_count,):
            raise ValueError(f'Expected {self.settings_count} voice parameters')
        frames = len(controls[0])
        if any(np.shape(control)!=(frames,) for control in controls):
            raise ValueError('Voice control lengths must agree')
        output = np.zeros(frames, dtype=np.float32)
        cutoff = np.ones(frames, dtype=np.float32) if cutoff is None else np.ascontiguousarray(cutoff, dtype=np.float32)
        resonance = np.full(frames, settings[11], dtype=np.float32) if resonance is None else np.ascontiguousarray(resonance, dtype=np.float32)
        if cutoff.shape!=(frames,) or resonance.shape!=(frames,):
            raise ValueError('Automation lengths must agree')
        self.function(output, *controls, cutoff, resonance, frames, self.rate,
                      np.ascontiguousarray(settings, dtype=np.float64), architecture)
        if not np.all(np.isfinite(output)):
            raise ValueError('Non-finite audio')
        return output


def features(audio, rate):
    rms = np.sqrt(np.mean(audio.astype(np.float64)**2))
    normalized = audio / max(rms, 1e-8)
    spectra = []
    for window in (512, 2048):
        frequencies, _, transformed = signal.stft(normalized, rate, nperseg=window,
                                                  noverlap=window-window//4)
        keep = (frequencies >= 30) & (frequencies <= 7000)
        spectra.append(np.log1p(20*abs(transformed[keep])))
    blocks = len(audio)//240
    envelope = np.sqrt(np.mean(normalized[:blocks*240].reshape(blocks, 240)**2, axis=1))
    return spectra, np.log1p(envelope*4)


def distance(actual, target):
    spectral = np.mean([np.mean(abs(left-right)) for left, right in zip(actual[0], target[0])])
    envelope = np.mean(abs(actual[1]-target[1]))
    return float(spectral + .12*envelope)


def save_wav(path, audio, rate):
    peak = float(np.max(abs(audio)))
    if not np.isfinite(peak) or peak < 1e-5:
        raise ValueError('Invalid render')
    gain = min(1.0, .89/peak)
    wavfile.write(path, rate, np.round(np.clip(audio*gain, -.99, .99)*32767).astype(np.int16))
    return {'raw_peak': peak, 'export_gain': gain,
            'rms': float(np.sqrt(np.mean((audio*gain)**2)))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iterations', type=int, default=8)
    parser.add_argument('--seed', type=int, default=20261101)
    parser.add_argument('--warm-start', type=Path)
    args = parser.parse_args()
    previous = json.loads(args.warm_start.read_text()) if args.warm_start else []
    subprocess.run(['gcc', '-O3', '-fPIC', '-shared', str(ROOT/'voice.c'), '-lm',
                    '-o', str(ROOT/'voice.so')], check=True)
    analysis = json.loads((ROOT/'analysis.json').read_text()) if (ROOT/'analysis.json').exists() else analyze()
    reference = load_audio(REFERENCE)
    renderer = Renderer(analysis['events'])
    output = ROOT/'outputs'
    output.mkdir(exist_ok=True)
    train_starts = [0, 15, 30]
    validation_starts = [7, 22, 43]
    duration = 1.4
    def prepare(starts):
        return [(renderer.controls(start, duration), features(reference[round(start*24000):round((start+duration)*24000)],24000)) for start in starts]
    training, validation = prepare(train_starts), prepare(validation_starts)
    log = (ROOT/'trials.jsonl').open('w')
    started = time.monotonic()
    trials = 0
    best_by_architecture = []
    def evaluate(settings, architecture, samples):
        errors = []
        for controls, target in samples:
            audio = renderer.render(settings, architecture, controls)
            if np.max(abs(audio)) > 1.5 or np.sqrt(np.mean(audio**2)) < 1e-5:
                return 100.0
            errors.append(distance(features(audio,24000),target))
        return float(np.mean(errors))
    for architecture, name in enumerate(ARCHITECTURES):
        baseline_train = evaluate(BASE, architecture, training)
        baseline_validation = evaluate(BASE, architecture, validation)
        def objective(values):
            nonlocal trials
            settings = BASE.copy()
            settings[INDICES] = values
            error = evaluate(settings, architecture, training)
            trials += 1
            log.write(json.dumps({'trial': trials, 'architecture': name, 'training_loss': error,
                                   'parameters': dict(zip(NAMES, settings.tolist()))})+'\n')
            log.flush()
            return error
        initial = BASE.copy()
        initialization = 'latinhypercube'
        if previous:
            initial = np.array([previous[architecture]['parameters'][name] for name in NAMES])
            generator = np.random.default_rng(args.seed+architecture)
            lower,upper = np.array(BOUNDS).T
            population = initial[INDICES] + generator.normal(0,.12,(48,len(INDICES)))*(upper-lower)
            population = np.clip(population,lower,upper)
            population[-12:] = generator.uniform(lower,upper,(12,len(INDICES)))
            initialization = population
        result = optimize.differential_evolution(objective, BOUNDS, maxiter=args.iterations,
                    popsize=3, seed=args.seed+architecture, polish=False, tol=.001,
                    x0=initial[INDICES], init=initialization, updating='immediate')
        settings = BASE.copy()
        settings[INDICES] = result.x
        heldout = evaluate(settings, architecture, validation)
        if previous and heldout > previous[architecture]['validation_loss']:
            settings = initial
            heldout = previous[architecture]['validation_loss']
        item = {'architecture': name, 'architecture_index': architecture,
                'training_loss': evaluate(settings,architecture,training), 'validation_loss': heldout,
                'baseline_training_loss': baseline_train, 'baseline_validation_loss': baseline_validation,
                'parameters': dict(zip(NAMES, settings.tolist()))}
        best_by_architecture.append(item)
        (ROOT/'architecture-results.json').write_text(json.dumps(best_by_architecture,indent=2))
        print(name, 'training', result.fun, 'validation', heldout, flush=True)
    selected = min(best_by_architecture, key=lambda item:item['validation_loss'])
    settings = np.array([selected['parameters'][name] for name in NAMES])
    architecture = selected['architecture_index']
    automation = []
    for start in range(0,54,6):
        sample_duration = min(2,54-start)
        controls = renderer.controls(start,sample_duration)
        target = features(reference[start*24000:round((start+sample_duration)*24000)],24000)
        def section_score(values):
            tuned=settings.copy()
            tuned[4]*=2**values[0]
            tuned[11]=values[1]
            return distance(features(renderer.render(tuned,architecture,controls),24000),target)
        initial = section_score([0,settings[11]])
        result = optimize.differential_evolution(section_score,[(-2.5,2.5),(0,.93)],
                    seed=args.seed+start,maxiter=5,popsize=4,polish=False,x0=[0,settings[11]])
        automation.append({'time':start,'cutoff_multiplier':2**float(result.x[0]),
                           'resonance':float(result.x[1]),'initial_loss':initial,
                           'fitted_loss':float(result.fun)})
        print('section',start,'loss',initial,'->',result.fun,flush=True)
    final_renderer=Renderer(analysis['events'],48000)
    controls=final_renderer.controls(0,54)
    timeline=np.arange(54*48000)/48000
    cutoff=np.interp(timeline,[point['time'] for point in automation],[point['cutoff_multiplier'] for point in automation])
    resonance=np.interp(timeline,[point['time'] for point in automation],[point['resonance'] for point in automation])
    initial_audio=final_renderer.render(BASE,architecture,controls)
    fixed_audio=final_renderer.render(settings,architecture,controls)
    final_audio=final_renderer.render(settings,architecture,controls,cutoff,resonance)
    statistics={}
    for name,audio in [('baseline',initial_audio),('fitted-static',fixed_audio),('fitted-automated',final_audio)]:
        statistics[name]=save_wav(output/f'{name}.wav',audio,48000)
    save_wav(output/'reference.wav',reference,24000)
    summary={'status':'candidate; perceptual match not established', 'seed':args.seed,
             'iterations':args.iterations,'warm_start':str(args.warm_start) if args.warm_start else None,
             'reference_sha256':hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
             'voice_source_sha256':hashlib.sha256((ROOT/'voice.c').read_bytes()).hexdigest(),
             'trials':trials,'seconds':time.monotonic()-started,
             'training_windows':train_starts,'validation_windows':validation_starts,
             'window_duration':duration,'architectures':best_by_architecture,
             'selected':selected,'automation':automation,'output_statistics':statistics,
             'limitations':['Provisional transcription; no manual MIDI timing verification.',
                            'Mono timbre and amplitude features; no stereo/effects reconstruction.',
                            'Independent window fits reset voice state; section automation approximate.',
                            'Validation used for architecture selection, not independent final testing.',
                            'Desktop floating-point core; not ported or timed on Blackfin.',
                            'Not a circuit-accurate Model D or Mariana emulation.']}
    (ROOT/'report.json').write_text(json.dumps(summary,indent=2))
    log.close()
    print('Finished',trials,'trials;',selected['architecture'],flush=True)


if __name__=='__main__':
    main()
