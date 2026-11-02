# Preferred voice, filter-only refinement

Status: candidate for listening, not an approved final match.

The independent run evaluated 1,716 candidates over ~164 seconds and stopped
at the optimizer's convergence/plateau limits. The core was frozen to the
previously preferred voice, not the rejected electro-sounding Mariana fit.

## Preserved exactly

12 dB state-variable filter algorithm, oscillator saw/pulse blend and width,
oscillator mix and detuning, sub path, amplifier attack/decay/sustain/release,
mixer/output drive, resonance, tuning and glide. Pulse-width and resonance
modulation remain off. Tests compare every frozen parameter exactly.

## Selected filter settings

Resting cutoff ~72.7 Hz; filter envelope depth ~5.73 octaves; attack time
constant ~15.8 ms; decay time constant ~99 ms; sustain ~0.018; curve exponent
~0.51; keyboard tracking ~0.86. These are implementation parameters, not
equivalent Mariana knob readouts or literal measured attack/decay durations.
The amp attack remains the old ~25 ms time constant. Filter and amp therefore
no longer reach their peaks together, while the oscillator/amp character stays
unchanged.

The gentle candidate interpolates halfway from the preferred filter settings,
using a geometric midpoint for resting cutoff. It is an explicit intermediate
setting, not a mix of reference audio into the synthesizer.

## Comparisons

All three outputs use identical detected notes/gates, continuous voice state
and the same engine. Auditions are RMS-adjusted with peak caps.

| Candidate | Whole Mariana phrase loss | Reserved-note loss | Upper/lower band energy |
| --- | --- | --- | --- |
| Preferred starting patch | 0.21927 | 0.26514 | -17.97 dB |
| Filter refinement | 0.15907 | 0.19503 | -15.34 dB |
| Gentle intermediate | 0.17093 | 0.21038 | -15.93 dB |

Reference band balance is -13.84 dB (400-6000 Hz relative to 22-400 Hz).
The selected refinement reduces reserved-note error about 26% relative to the
restored starting patch. That is a numerical comparison, not a percentage of
perceptual similarity. These results are not claimed to score better than the
rejected electro patch; preserving user preference takes priority.

Training and selection use separate note instances; the four final audit note
instances were excluded from both. All instances belong to the same performance,
and the scoring approach was developed on these recordings. This is not an
independent musical generalization test.

## Verification and deliverables

Four test groups pass: frozen settings, WAV headroom/duration/initial silence,
source checksum and deterministic render, and search/audit separation.
preferred-preset.json, refined-preset.json and gentle-preset.json preserve the
settings. They are desktop development presets, not hardware-loadable files.

Use preferred-refined-gentle.wav to compare the original preferred voice and
both variations. Use mariana-then-refined.wav for the direct target comparison.
The refined-preview.wav and gentle-preview.wav files cover the initial note
sequence. Earlier experiments and both references are preserved. No hardware
firmware was modified or flashed.

The actual rubbery feel and acceptable timbral distance require user listening
judgment. The broader goal remains incomplete until the first patch is approved.
