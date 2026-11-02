import json
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parent
REFERENCE = ROOT.parents[1] / 'references/tinashe/audio/Tinashe_bass.wav'


def load_audio(path, rate=24000):
    original_rate, audio = wavfile.read(path)
    if np.issubdtype(audio.dtype, np.integer):
        audio = audio.astype(np.float64) / (2 ** (np.iinfo(audio.dtype).bits - 1))
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    divisor = np.gcd(original_rate, rate)
    return signal.resample_poly(audio, rate // divisor, original_rate // divisor)


def analyze():
    rate = 24000
    audio = load_audio(REFERENCE, rate)
    hop = 240
    frequencies, times, spectra = signal.stft(audio, rate, nperseg=4096, noverlap=4096-hop)
    magnitude = abs(spectra)
    notes = np.array([note for note in range(24, 61) if note % 12 in (7, 8, 5, 0, 1, 10)])
    scores = []
    for note in notes:
        fundamental = 440 * 2 ** ((note - 69) / 12)
        bins = np.arange(1, 9) * fundamental * 4096 / rate
        harmonics = np.array([np.interp(position, np.arange(len(frequencies)), magnitude[:, frame])
                              for frame in range(magnitude.shape[1]) for position in bins]).reshape(-1, 8).T
        score = np.sum(harmonics / np.arange(1, 9)[:, None], axis=0)
        score *= (harmonics[0] / (magnitude.max(axis=0) + 1e-12)) ** 0.5
        scores.append(score)
    chosen = notes[np.argmax(scores, axis=0)]
    chosen = signal.medfilt(chosen, 7)
    high = magnitude[(frequencies > 180) & (frequencies < 6000)]
    novelty = np.maximum(0, np.diff(np.log1p(high * 100), axis=1)).mean(axis=0)
    novelty = np.r_[0, novelty]
    peaks, _ = signal.find_peaks(novelty, distance=12, prominence=max(0.002, np.std(novelty)*0.35))
    changes = np.flatnonzero(np.diff(chosen) != 0) + 1
    starts = sorted(set([0] + list(peaks) + list(changes)))
    merged = []
    for frame in starts:
        if not merged or times[frame] - times[merged[-1]] >= 0.10:
            merged.append(frame)
    events = []
    for index, frame in enumerate(merged):
        start = max(0, float(times[frame]) - 0.025)
        end = float(times[merged[index+1]]) - 0.025 if index+1 < len(merged) else len(audio)/rate
        if end-start < 0.08:
            continue
        center = min(len(chosen)-1, frame+5)
        note = int(chosen[center])
        events.append({'start': round(start, 5), 'end': round(end, 5), 'midi': note,
                       'frequency': round(440*2**((note-69)/12), 6)})
    result = {'sample_rate': rate, 'duration': len(audio)/rate, 'events': events,
              'method': 'Harmonic template pitch estimates restricted to user note classes; spectral-flux onsets. Octaves/timing provisional.'}
    (ROOT/'analysis.json').write_text(json.dumps(result, indent=2))
    print('Events:', len(events), 'MIDI distribution:', dict(zip(*[item.tolist() for item in np.unique([event['midi'] for event in events], return_counts=True)])))
    print('First events:', events[:12])
    return result


if __name__ == '__main__':
    analyze()
