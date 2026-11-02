# Tinashe bass matching experiments

This is a new desktop floating-point synth core for reference matching. The
older Aleph preview and both hardware firmware trees remain separate. It is
not a circuit-accurate Moog/Mariana clone and has not been ported to Blackfin.

## Run

From the project root:

```
python desktop/matching/analyze.py
OPENBLAS_NUM_THREADS=1 python desktop/matching/fit.py --iterations 8
python desktop/matching/test_voice.py
python desktop/matching/audition.py
```

Requires Python 3, NumPy, SciPy and GCC. This run uses NumPy 2.3.5 and SciPy
1.16.3. The renderer builds locally from voice.c; no network or hardware
access is involved. Reference WAV is stored in references/tinashe/audio.
The fitting seed and original reference checksum are recorded in report.json.
Each run overwrites its logs/results/exports, not the reference or firmware.
To refine a previous result, archive its architecture-results.json first and
pass its path with `--warm-start`. Keep the old trial log and report alongside
it. Warm starts retain the previous architecture candidate if its validation
score is better. They do not establish that a perceptual match has been reached.

## Voice

Two anti-aliased saw/pulse oscillators with pulse width, blend and detuning;
separate sine sub and sub low-pass; independent amplitude and filter-envelope
decay; note retrigger and pitch glide; nonlinear mixer and output drive;
DC blocking. Internal sample rate is doubled and averaged for output. This
is modest oversampling, not a complete alias-rejection strategy.

Architecture candidates are a 12 dB state-variable filter and approximate
nonlinear two/four-stage feedback low-pass cascades (labelled ladder12/24).
These labels describe topology, not measured equivalence to Moog circuits.
The source uses scalar floating point and transcendental functions: CPU/DSP
cost and fixed-point conversion still need separate work before hardware use.

## Matching

Harmonic pitch templates are restricted to G/G-sharp/F/C/C-sharp/B-flat,
including octave changes. Spectral-flux onsets and pitch changes produce a
provisional event schedule. Some octave jumps may be transcription errors;
this is not a manually verified MIDI transcription. Gates are estimated.

Core settings are optimized on 1.4-second excerpts at 0, 15 and 30 seconds;
7, 22 and 43 seconds are reserved for choosing the filter architecture.
Loss combines two STFT resolutions and a 10 ms amplitude envelope after RMS
normalization, so it measures timbre/articulation independently of level.
Validation is used for architecture selection, not an independent final test.

A second stage fits cutoff offset and resonance to two-second excerpts every
six seconds; final automation interpolates those points. This explores the
user's filter-movement hypothesis; it does not identify the original producer's
automation. Window fits reset voice state and therefore only approximate the
continuous render. Envelope depth, distortion and cutoff can trade off.

The reference is 54 seconds, 44.1 kHz stereo, almost mono (correlation ~0.984).
About 0.31% of channel samples reach an int16 rail. This can indicate clipping
or limiting. It is not a pristine dry oscillator/filter measurement. We do not
copy the rail hits into the synth output just to lower a numerical error.

Outputs include baseline, fitted static and fitted automated WAVs, trial logs,
architecture comparisons, source checksum, parameters, export gains and a
candidate report. Numerical improvement alone does not establish a perceptual
match. Original phase, exact notes/gates, stereo/effects and hardware behavior
remain outside this first fit. User listening feedback is the next meaningful
check before treating any result as a successful recreation.

`audition.py` creates a level-matched reference-then-synth listening comparison
at 0, 7 and 24 seconds, a short synth preview and audit.json. The audit evaluates
continuous renders at five additional excerpts not explicitly used in fitting.
The audit uses the same recording and estimated note schedule and must not be
described as proof of generalization to other musical material.
It selects the lower-error static/automated output and writes best-candidate.wav
and best-preset.json. Those audit excerpts are consequently part of selection,
not an untouched final test. See RESULTS.md for the first three-round session.
