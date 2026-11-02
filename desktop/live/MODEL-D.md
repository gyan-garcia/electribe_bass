# Model D-style desktop prototype

This mode is an independent engine. The approved bass engine, its archived
source and recordings, and bassline-pluck remain available. The Model D mode
implements the following playable signal path:

Three oscillators + noise → driven mixer + optional feedback → nonlinear
four-pole filter → amp contour → output drive and DC removal.

Each oscillator has its own waveform, octave range, tuning, low-frequency
switch and mixer level. Choices are triangle, triangle/saw blend (reverse saw
on oscillator 3), saw, square and two pulse widths. Oscillator 3 can ignore the
keyboard and use a fixed frequency. Low Frequency overrides its base frequency
to 2 Hz before octave/tuning, on any oscillator. The waveform shapes and range
calibration are approximations, not measurements of a physical Model D.

The mixer includes white/pink-like noise, input drive and an internal feedback
path approximating the idea of an output-to-input cable. This does not expose
an external audio input. The filter offers 24 dB low-pass/high-pass responses,
emphasis into self-oscillation, signed envelope depth and independent one-third /
two-thirds keyboard control switches. Both on give full tracking, calibrated
around G1 (49 Hz). High-pass is inspired by Behringer's additional mode.

Filter and amp each have attack, decay and sustain. The shared Decay on Key
Release switch enables releases using the corresponding decay knob, otherwise
a 5 ms anticlick fade applies. Attack reaches 99.9% by its displayed time;
decay moves 99% toward sustain by its displayed time; release falls 60 dB by its
displayed time. These timing conventions differ from the approved bass engine's
time constants. Retriggering begins from the current contour level. Last-note
priority, velocity gain, glide, sustain, legato and pitch bend remain available.

The modulation bus blends oscillator 3 or filter contour with noise or the
dedicated triangle/square LFO. Wheel amount scales the mix. Separate switches
and depth controls route it to oscillator pitch and filter cutoff. Oscillator 3
feeds the bus with a one-internal-sample delay, including when pitch modulates
all three oscillators. Assigning a MIDI knob to a discrete control selects a
legal named value. Session mappings are isolated between engines.

## Implementation and limits

The core is original C using two-times oversampling, integer phase accumulators,
polyBLEP saw/pulse edges, a four-stage TPT ladder-style filter and a nonlinear
feedback solve. It is not a transistor-by-transistor Model D emulation. The
triangle and mixed waveform are analytic approximations. Pink-like noise uses
three weighted low-pass noise bands. Two-sample averaging is the current
downsampling filter; strong drive and audio-rate modulation can still alias.
Very high oscillator frequencies clamp to 22% of the internal sample rate.

Levels, cutoff, emphasis, drive, feedback and wheel amount smooth over an 8 ms
time constant. Other controls change at block boundaries. Filter coefficients
normally refresh every eight internal samples; filter modulation refreshes them
every internal sample. This is a cost/quality choice, not physical circuit behavior.

The implementation uses a zero-delay feedback formulation related to virtual
analog filter methods, but does not implement the complete nonlinear circuit
model described by [Huovilainen, DAFx 2004](https://dafx.de/paper-archive/2004/P_061.PDF).

## Electribe scope

An isolated embedded object compiles using the project's existing Blackfin
toolchain, with allocation wrappers removed by MODEL_D_EMBEDDED. The core allows
caller-owned state and allocates nothing inside its processing routine. Its
desktop state is 160 bytes and the initial Blackfin object has 7,984 bytes of
code/data before linking libraries. These are not full firmware memory budgets.

Crucially, the Blackfin object still calls software floating-point helpers and
transcendental maths. Desktop speed does not establish on-device speed. Lookup
tables / fixed-point work, actual DSP cycle measurements and firmware integration
are required before claiming real-time operation on the Electribe. No firmware
was changed or flashed for this work.

## Reproduce and audition

Run `bash run-synth.sh` from the project root. Save and close an older running
copy first, then reopen to load the new code. Select Model D prototype, choose
a patch, connect the MPK and start audio. The app initially opens the approved
bass engine and leaves audio stopped.

From desktop/live, run:

```sh
.venv/bin/python -m unittest tests test_modeld -v
.venv/bin/python validate_modeld.py
.venv/bin/python modeld_preview.py
.venv/bin/python fit_modeld.py
```

The last command is optional and uses the existing SciPy matching environment.
It holds the oscillator architecture fixed and adjusts nine knobs. Its objective
weights the Mariana example 65% and the approved bass character 35%. Five notes
train the search; other notes in the same recordings check the shortlist. This
is a numerical aid to listening, not proof of a perceptual match or generalization.
Results go to outputs/modeld-fit and a new candidate preset. Existing presets
are never overwritten. The comparison WAV plays Mariana, approved bass, then
the candidate, with half-second gaps and matched RMS subject to peak limiting.

No candidate becomes the baseline automatically. The next decision is listening
to whether the new architecture retains the rubbery sound you want.
