# First patch: preserve the preferred sound

This experiment restores the user's preferred Tinashe candidate and freezes
its architecture. It does not use the rejected brighter/electro patch as a base.

## Frozen instrument

- Two mainly saw oscillators: blend, width, oscillator levels and detune fixed.
- Separate sine sub and its existing filter, fixed.
- 12 dB state-variable main filter, same algorithm and resonance.
- Amp envelope, mixer drive, output drive, glide and tuning fixed.
- Pulse-width modulation and resonance modulation disabled.

Only resting filter cutoff, filter-envelope depth, decay, attack, sustain,
sweep curvature and filter keyboard tracking may change. This is patch
refinement within one instrument, not another architecture search.

voice-snapshot.c preserves the exact core used. preferred-patch.json preserves
the starting parameters. The new controls are already present in that core;
no additional synthesis mechanisms were added for this experiment.

## References and scoring

The direct Mariana recording uses the user-specified notes and detected attacks.
The model renders the entire phrase continuously before comparisons, so filter
and oscillator state carry across notes. Training notes are separate from
candidate-selection and final audit notes. This avoids the former short-window
state resets, although all notes still belong to the same reference performance.

The objective weighs Mariana comparison 70%, the original Tinashe intro 20%,
and a spectral-change penalty relative to the preferred patch 10%. The Tinashe
check only covers its first 1.3 seconds; it is not a full-song validation.
Mariana loss includes spectra, amplitude, brightness trajectory and band balance.
The user preference remains more authoritative than these numerical weights.

Search stages: coarse cutoff/envelope fit, seven-parameter envelope refinement,
then bounded local refinement. Stop on numerical plateau or the stage limits.
The best diverse candidates are evaluated on selection notes; final audit notes
are checked only after selection. Source/reference hashes and every evaluated
candidate are recorded. Envelope times are exponential time constants, not
literal time-to-peak labels equivalent to Mariana knobs.

## Run and listen

From project root:

```
OPENBLAS_NUM_THREADS=1 python desktop/matching/patch1/refine.py
python desktop/matching/patch1/test_refinement.py
python desktop/matching/patch1/summarize.py
```

Requires the existing NumPy/SciPy/GCC environment. Each run overwrites this
experiment's outputs/logs; it does not overwrite earlier experiments, references
or hardware firmware. The preferred source patch remains separate.

Listening files:

- preferred-same-phrase.wav: restored starting patch.
- refined-same-phrase.wav: the selected filter-only refinement.
- gentle-same-phrase.wav: an intermediate, less changed filter setting.
- preferred-refined-gentle.wav: those three in order with half-second gaps.
- mariana-then-refined.wav and mariana-then-gentle.wav: reference first, then synth.
- refined-preview.wav and gentle-preview.wav: short versions.
- refined-48k.wav and gentle-48k.wav: full-resolution, pre-audition-gain renders.

All listening comparisons use RMS adjustment with peak caps. report.json stores
settings, objective components, shortlist, baseline and audit scores. Preset JSON
exports are desktop development patches, not Electribe-loadable patch files.

These are candidates requiring a listening judgment. They do not demonstrate
Mariana/Model D circuit equivalence, exact MIDI transcription, or real-time
Blackfin feasibility. Hardware remains untouched.

See RESULTS.md for the recorded run. The separate summarize.py command exports
the saved presets and brightness measurements without rerunning optimization.
