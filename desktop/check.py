import hashlib
import math
from pathlib import Path
import struct
import subprocess
import wave


def tone_energy(samples, frequency):
    coefficient = 2 * math.cos(2 * math.pi * frequency / 48000)
    previous = previous_previous = 0.0
    for sample in samples:
        current = sample + coefficient * previous - previous_previous
        previous_previous, previous = previous, current
    return previous**2 + previous_previous**2 - coefficient * previous * previous_previous


root = Path(__file__).resolve().parent
paths = sorted((root / 'outputs').glob('*.wav'))
assert len(paths) == 3
hashes = {path: hashlib.sha256(path.read_bytes()).digest() for path in paths}
for path in paths:
    with wave.open(str(path)) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()) == (1, 2, 48000, 384000)
        samples = struct.unpack('<384000h', audio.readframes(384000))
    peak = max(abs(sample) for sample in samples) / 32768
    rms = math.sqrt(sum((sample / 32768)**2 for sample in samples) / len(samples))
    assert 0.001 < rms < 0.5 and peak < 0.99, (path, peak, rms)
    assert max(abs(sample) for sample in samples[-480:]) < 1000
    if path.name == 'sustained-bass.wav':
        stable = samples[48000:144000]
        energy = tone_energy(stable, 55)
        assert energy > 10 * max(tone_energy(stable, frequency) for frequency in (27.5, 54, 56))
    print(f'{path.name}: format, signal level, release passed')
subprocess.run([str(root / 'build/render')], cwd=root, check=True)
assert all(hashlib.sha256(path.read_bytes()).digest() == digest for path, digest in hashes.items())
print('A1 tuning and deterministic rendering passed')
