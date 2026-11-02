# First reference-matching session

Reference: the user's 54-second Tinashe_bass.wav. User confirms octave patterns
on G, G-sharp, F, then C, C-sharp, B-flat. Exact event transcription is provisional.

## Search performed

Three deterministic search rounds evaluated 7,020 core parameter candidates:
972 initial, 3,600 refined, 2,448 further refined, plus the section-automation
searches. Historical logs/reports are in runs/initial and runs/refined; current
trials.jsonl and report.json describe the last round. Seeds and the original
reference checksum are preserved. Reproduce each round using its recorded seed,
iteration count and warm-start architecture-results.json.

| Round | Best architecture-selection loss | Selected filter |
| --- | --- | --- |
| Initial | 0.106707 | approximate 24 dB feedback cascade |
| Refined | 0.101004 | 12 dB state-variable |
| Further refined | 0.100650 | 12 dB state-variable |

The last round improved that score by only about 0.35%, indicating diminishing
returns for this search and event schedule. It does not establish convergence
to a perceptual match or a globally optimal setting.

## Current candidate

The 12 dB state-variable design is best in this experiment. This result does not
identify Mariana's implementation or the original recording's synthesizer.
The patch favors mostly saw waveform, ~3.45 cents oscillator detuning, modest
sine sub, strong mixer drive, low resting cutoff (~46 Hz), ~4.22 octaves of
filter-envelope depth and ~283 ms filter-envelope decay. These are parameters
of this prototype, not recovered Mariana values. Amp attack is near its search
upper bound (~25 ms), which may partly compensate for onset estimation error.

Across five additional excerpts, static-patch loss was 0.131290 versus baseline
0.145051: about 9.49% lower numerical error. The automated version scored
0.132746, so the static version is retained for best-candidate.wav and the
listening comparison. These excerpts were then used for output selection;
they are no longer an independent final validation set.

Section filter automation remains an alternative experiment. Its worse audit
score does not disprove filter movement in the song. Cutoff, resonance, drive,
envelope and pitch errors can confound one another, and six-second automation
spacing may miss the actual movement.

## Listen and reproduce

- outputs/fitted-preview.wav: first eight seconds of the current candidate.
- outputs/best-candidate.wav: full 54-second candidate, mono 24 kHz PCM.
- outputs/reference-then-synth.wav: three level-matched pairs at 0, 7, 24 s;
  each pair is reference 3 s, gap .5 s, candidate 3 s, gap 1 s.
- outputs/best-preset.json: parameters, chosen architecture, reference checksum.
- outputs/fitted-static.wav and fitted-automated.wav: full 48 kHz source renders.

Run python desktop/matching/audition.py to regenerate listening outputs from
the stored full renders. The preview exports are downsampled, peak-capped and
not a measure of bit-exact hardware behavior.

Tests pass for tuning of all six note classes and octave variants, deterministic
rendering, silence, note release, random bounded settings on all three filter
architectures, and full-render duration/headroom. The older Aleph preview checks
also still pass. No hardware firmware was modified or flashed.

Status: **a fitted approximation, not a confirmed sound match**. Remaining work
includes listening evaluation, verifying MIDI octave/timing estimates, and
testing richer envelope/filter/drive behavior where the reference differs.
No claim of autonomous perceptual verification is made from spectral scores.
