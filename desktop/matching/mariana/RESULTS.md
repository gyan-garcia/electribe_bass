# Brighter rubber bass: second listening candidate

The exact user note sequence replaces the earlier estimated Tinashe octave
schedule for this experiment. Pitch onsets are detected from the clean Mariana
recording, with one additional final G1 retrigger near 11.1 s.

Two search rounds evaluated 8,013 core candidates: 3,213 initial and 4,800 refined.
The first round improved generic spectral error but remained too dark. Refinement
explicitly weighted high/low harmonic energy balance. Because the loss changed,
scores are compared only within the same metric version.

The selected topology is the approximate nonlinear two-stage low-pass cascade
(ladder12), not a claim to model the actual Mariana filter circuit.

The working patch has a ~2.1 ms filter attack, separate ~3 ms amp attack,
~421 ms filter decay, shaped filter sweep (~1.90 curvature), low resting cutoff
(~47 Hz), ~5.34 octaves filter envelope, strong keyboard tracking, moderate
resonance, slight envelope/resonance coupling and a small amount of pulse-width
envelope movement. These are fitted prototype values, not recovered Mariana
settings. The sub oscillator and driven mixer remain part of the voice.

## Measurements against the supplied Mariana phrase

Upper/lower spectral energy uses 400-6000 Hz relative to 22-400 Hz:

| Signal | Balance |
| --- | --- |
| Mariana reference | -13.84 dB |
| Previous patch on the same notes | -18.05 dB |
| Updated candidate | -14.52 dB |

The brightness-balance error is about 0.69 dB, compared with 4.21 dB previously.
Combined full-recording spectral/envelope/brightness loss decreases from ~0.221
to ~0.119 under the revised metric. This is not a perceptual-match percentage.
The full recording and architecture-selection excerpts have been used in
selection; these numbers are descriptive, not an independent listening test.

## Listening and tests

rubber-preview.wav is a short RMS-adjusted candidate. mariana-then-synth.wav
plays the complete original followed by the new synth, with level matching.
rubber-bass.wav is the full 48 kHz candidate; preset.json and events.json hold
the settings and note schedule.

Four new test groups pass: extended parameter stability/release/repeatability,
cutoff-to-brightness response, note sequence/export integrity, and the parameter
count guard. Three existing voice test groups pass including B-flat0 tuning;
the old 16-parameter API was verified to render identically to the saved engine.
C source passes -Wall -Wextra -Werror syntax checks.

The rubbery texture still requires a listening judgment. The engine is desktop
floating point, not a Blackfin port, and no hardware firmware was changed.
