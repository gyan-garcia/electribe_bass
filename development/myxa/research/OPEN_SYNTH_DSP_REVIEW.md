# Open-source Model D references for MYXA

Research date: 2026-11-03. Scope: community listening reports, source inspection, and read-only measurements of the existing MYXA core. No replacement engine, preset changes, competitor listening test, or hardware performance claim is included.

## Recommendation

Use **Odin 2 as a warm analogue sound reference** and **Surge XT's SST filters as the main reference for a new experimental ladder**. Keep MYXA's approved engines available unchanged. The most promising experiment combines saturation within the ladder stages with independently adjustable resonance compensation, followed by envelope calibration. These are hypotheses to audition, not improvements established by a waveform score.

The published feedback does not establish an open-source winner for accurate Minimoog reproduction. The best-supported candidates are broader subtractive synths capable of a similar signal path. A close control layout alone says little about circuit behaviour.

## Shortlist and listening evidence

| Candidate | Architectural relationship | User evidence | Decision for MYXA |
| --- | --- | --- | --- |
| **Odin 2** | Three oscillator slots, analogue waveforms, ladder option, envelopes and modulation; considerably broader than a Model D | KVR: 4.57/5 from 7 reviews. Airlane1979 (2022) praises warmth; Trader One (2022) prefers its warmth to Surge and praises the filters. Other reviews mention bugs and workflow limitations. | First sound reference for warmth; oscillator and envelope implementation ideas. Not proof of accurate Model D resonance. |
| **Surge XT / SST filters** | Three oscillators per scene; several transistor-ladder models, selectable filter routing and modulation | KVR: 4.74/5 from 31 reviews. SoundTrue (2025) praises sound quality; mryan4 (2024, Linux) praises analogue and experimental range. Reviews assess the whole instrument. | Best filter-code reference and controlled comparison platform. Its flexibility makes it less directly comparable to a fixed Minimoog. |
| **Helm** | Two main oscillators plus sub, envelopes, modulation and drive; not a three-VCO Minimoog clone | KVR: 4.33/5 from 6 reviews. Duncle22 (2020) praises clarity; other users praise presets and character. Old, small sample. Repository archived February 2025. | Secondary reference for smoothing and articulation. Its included ladder is commented out in the inspected voice wiring: do not attribute the reviewed instrument's sound to that ladder. |
| **amsynth** | Two oscillators, dual envelopes, mono/legato modes, 12/24 dB filter | Useful established subtractive design, but insufficient comparable recent user evidence here to rank its Moog sound. | Useful simpler design, not a transistor-ladder donor. |
| **Bristol Mini** | Direct three-oscillator Mini-style layout with two contours, release switch and oscillator-3/noise modulation | The author's own documentation acknowledges a thinner sound and suggests warmer filtering and improved waveforms. Documentation screened; source not cloned or audited. | Layout/routing reference, lower priority for sound. |

Feedback sources: [Odin reviews](https://www.kvraudio.com/product/odin-2-by-thewavewarden/reviews), [Surge reviews](https://www.kvraudio.com/product/surge-xt-by-surge-synth-team/reviews), [Helm reviews](https://www.kvraudio.com/product/helm-by-matt-tytel/reviews), [Helm archive status](https://github.com/mtytel/helm), [amsynth architecture](https://amsynth.github.io/), [Bristol Mini documentation](https://bristol.sourceforge.net/mini.html).

The scores describe self-selected reviews of different versions, not matched-patch blind tests. They include workflow, presets and stability. The warmth comparison is one reviewer's opinion, not a measured consensus. No competitor audio was rendered or independently auditioned during this research.

Other screening: Faug has a direct Model D layout and public source, but no license file was found in the inspected checkout; it is not treated as a verified reusable open-source donor. MinimogueVA was not included because a reusable DSP source license was not verified. Commercial Model D emulations are outside this source-donor shortlist.

## What the code actually does

All inspected checkouts and their commits are recorded in `source-manifest.json`. Local clones are ignored under `vendor/research-synths/`; no third-party DSP has been copied into MYXA.

### MYXA: already an implicit-feedback ladder

`desktop/live/native/modeld.c:131` solves a nonlinear input/feedback junction using three Newton iterations, followed by four linear TPT one-pole stages. It already has a zero-delay-style feedback solve. Simply adding something called a ZDF ladder is not a useful diagnosis.

The distinction is **where the nonlinearities occur**: the poles themselves are linear, while the input junction and post-amplifier output saturate. The approved 18 dB variant uses the third output tap but retains the four-pole feedback loop (`modeld.c:247`). Changing that feedback topology would also change existing patches.

### Surge: nonlinear stages and optional compensation

[`VintageLadders.h`](https://github.com/surge-synthesizer/sst-filters/blob/87a171bcba52c014850848a29174a54f0adc6606/include/sst/filters/VintageLadders.h) contains Runge–Kutta and Huovilainen-style models. Their nonlinearities are distributed across the stages, so drive, resonance and input level interact differently from MYXA's current ladder. Compensated variants offer a useful way to compare low-end retention separately from resonance.

The RK implementation uses four extra integration steps with multiple derivative evaluations. The Huovilainen section uses thermal scaling, nonlinear stage updates and delay/phase compensation. Both are more involved than a four-pole label suggests. SST's SIMD implementation is not a drop-in Blackfin solution. Its own RK output reconstruction comment acknowledges a shortcut; do not assume every upstream detail is an ideal reference.

The [official Surge manual](https://surge-synthesizer.github.io/manual-xt/#filters) distinguishes its ladder models, compensated variants and CPU/accuracy tradeoffs. Its diode ladder is a different circuit family from the Model D's transistor ladder.

### Odin: useful oscillator design, not a more nonlinear ladder

[`LadderFilter.h`](https://github.com/TheWaveWarden/odin2/blob/265e9e227581357efb87ed7217381f8a40c5e2bf/Source/audio/Filters/LadderFilter.h) uses four linear TPT stages and a linear implicit feedback solve, with overdrive applied to their combined output. Resonance is capped at 3.88, deliberately avoiding self-oscillation. Copying this filter wholesale could remove behaviour MYXA needs.

[`AnalogOscillator.cpp`](https://github.com/TheWaveWarden/odin2/blob/265e9e227581357efb87ed7217381f8a40c5e2bf/Source/audio/Oscillators/AnalogOscillator.cpp) uses waveform tables, forms pulse waves by subtracting shifted saws, smooths pulse width, and adds controllable slow pitch drift. The saw difference has zero mean across duty cycles. This offers a useful comparison to MYXA's unbalanced narrow pulses. A large table bank costs memory, so a compact bandlimited implementation may fit the target better.

[`ADSR.cpp`](https://github.com/TheWaveWarden/odin2/blob/265e9e227581357efb87ed7217381f8a40c5e2bf/Source/audio/ADSR.cpp) combines linear attack with exponential decay/release and explicit retrigger/legato behaviour. Different curves are worth auditioning, without assuming Odin's curves match a physical Model D.

### Helm: distinguish available code from active code

[`ladder_filter.cpp`](https://github.com/mtytel/helm/blob/abdedd527e6e1cf86636f0f1e8a3e75b06ed166a/mopo/src/ladder_filter.cpp) includes nonlinear stage processing and parameter interpolation. However, its construction and connections are inside a comment in [`helm_voice_handler.cpp:468`](https://github.com/mtytel/helm/blob/abdedd527e6e1cf86636f0f1e8a3e75b06ed166a/src/synthesis/helm_voice_handler.cpp#L468). The active path instantiates a state-variable filter instead. Treat the ladder as algorithmic reference code requiring independent validation.

The same voice handler sends the current note into `PortamentoSlope` before frequency conversion. MYXA instead smooths frequency in Hz (`modeld.c:214`). A pitch-domain glide experiment could therefore change the musical feel of interval transitions without adding effects.

### amsynth: a different filter family

[`LowPassFilter.cpp`](https://github.com/amsynth/amsynth/blob/29818503d3d63b36948e9696741ae7d5c8c66997/src/core/synth/LowPassFilter.cpp) calculates biquad coefficients through a bilinear transform: one biquad for 12 dB, two cascaded for 24 dB. This is not a nonlinear transistor ladder. Matching the slope alone will not reproduce Model D drive/resonance behaviour.

## Measurements of the existing MYXA core

Reproduce from the repository root:

```sh
desktop/live/.venv/bin/python development/myxa/research/probe_current_dsp.py
```

The probe compiles a wrapper around the existing C core, uses NumPy for analysis, and writes ignored output under `desktop/live/outputs/open-synth-review/`. A research snapshot is saved as `current-dsp-measurements.json` next to this report. It verifies the core and all 102 user patches remain unchanged during the measurement.

### Resonance removes substantial bass level

Filter-only test: 50 Hz sine at amplitude 0.001, cutoff 1 kHz, 48 kHz output / 96 kHz internal rate. First 250 ms discarded. Output is the fourth pole; no amplifier, EQ, reverb or output saturation.

| Normalized resonance | 50 Hz gain |
| --- | --- |
| 0 | −0.04 dB |
| 0.3 | −6.83 dB |
| 0.5 | −9.52 dB |
| 0.7 | −11.57 dB |
| 0.9 | −13.24 dB |

This is expected behaviour for an uncompensated ladder, not automatically a defect. It supports testing an optional compensation mode for fullness. Compensation changes the reference behaviour and must not silently alter approved patches. Compare at matched loudness: a louder result is not sufficient evidence of better tone.

### Narrow pulses bias the filter

MYXA's 25% and 10% pulses have means of −0.5 and −0.8. The DC blocker comes after the nonlinear filter and amplifier, so it cannot undo the operating-point shift inside them.

At 50 Hz, cutoff 500 Hz and resonance 0.7, centering the input changed the filter's output mean from −0.133 to −0.0065 (25% pulse) and −0.211 to −0.0058 (10%). AC RMS changed only slightly. This demonstrates internal bias, not proven improvement or a large volume recovery. Audition either DC-balanced pulses or pre-filter AC coupling; real analogue coupling is frequency dependent and not equivalent to subtracting a mean.

### Antialiasing deserves a separate experiment

MYXA uses PolyBLEP for saw/pulse edges, an uncorrected geometric triangle, and averages two internal samples for downsampling. That final average is a weak boxcar filter rather than a proper half-band decimator.

An oscillator-only coherent FFT found increasing folded/non-harmonic energy at high notes. For example, the 10% pulse measured −22.2 dB relative to the fundamental around 498 Hz and −9.3 dB around 4.1 kHz. These deliberately isolated, bright-wave tests are not measurements of alias audibility in a dark bass patch. The musical low-pass filter can suppress some of that energy.

## Proposed experiments, in order

1. **Separate filter saturation from bass compensation.** Keep the existing engine as control. First compare its uncompensated and compensated variants, then a scalar stage-nonlinear ladder with compensation off/on. Start from the approved Moog Res patch, matching levels and envelope settings. Sweep cutoff, resonance and mixer level; include silence/high-resonance tests for self-oscillation, tuning and stability. Test the approved 18 dB output topology separately from a conventional 24 dB Model D path.
2. **Test pulse coupling independently.** Compare original pulses, DC-balanced pulses and a gentle pre-filter coupling stage with identical musical settings. Include narrow pulses, low notes and mixer feedback. Keep the old behaviour available.
3. **Improve downsampling and triangle generation.** Try a compact 2x half-band decimator and a bandlimited triangle. Measure added latency, alias rejection, code size and cost before considering higher oversampling. A heavier RK ladder is a desktop reference candidate, not the first embedded implementation.
4. **Calibrate articulation.** Compare attack/decay shapes, filter contour depth, retrigger/legato behaviour and pitch-domain glide against the Mariana recording. MYXA already retriggers from its current envelope level; do not add that as if it were absent. Optional slow drift should default off while matching references.
5. **Make the chosen model affordable.** MYXA already prepares static envelope/tuning coefficients. Its cutoff path still calls `exp2f`/`tanf`, and enabling filter modulation forces updates at every internal sample even when modulation amount is zero. Test an inactive-modulation fast path, bounded lookup approximations and interpolated control-rate updates. Preserve genuine audio-rate modulation where needed.

Use the same notes, gate timing and velocity for comparisons. Keep waveform/spectrum, envelope trajectories and high-resonance sweeps alongside listening results; do not rank by raw sample difference when oscillator phases are free-running. A short, level-matched listening shortlist should determine preference rather than numerical rank alone.

## Electribe feasibility and preservation

The existing Blackfin adapter uses software floating point; host speed is not hardware timing evidence. SIMD desktop implementations require adaptation, and extra nonlinear evaluations can be expensive. The ARM 128 KB region is not a universal cap on the complete DSP engine. Use the current linker maps and target memory layout, then measure worst-case cycles, stack use and audio continuity on the actual target before selecting a production model.

Keep this work in an experimental engine/version so existing Model D and Model D 18 presets retain their meaning. The approved engines, all 102 user patches, EQ/reverb, and firmware were not modified. No hardware was flashed. The existing uncommitted UK50 bank was preserved.

License observations from inspected source: Odin and Helm DSP headers are GPL-3.0-or-later, amsynth GPL-2.0-or-later, and SST generally GPL-3.0-or-later with additional retained notices in individual algorithms. Preserve those notices if adapting code. Faug's public availability is not a verified reuse license. This research adds no third-party implementation code to MYXA.
