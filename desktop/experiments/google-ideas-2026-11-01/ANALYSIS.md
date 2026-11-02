# Google recipe review and controlled experiments

Baseline: approved Bassline v1, preserved without modification. Every stored
checksum is verified before and after rendering. The experiment engine's default
output reproduces the approved full-resolution WAV sample-for-sample.

## What the Google response establishes

It is a plausible generic recipe for an aggressive electronic bass, not verified
production documentation for Melatonin. Public credits name Ricky Reed on bass
synthesizer, without identifying the instrument or the passage at 2:18:
https://www.qobuz.com/us-en/album/melatonin-tinashe/hbwww210xqmut

A targeted search did not establish Serum, Monster 7, particular oscillator
settings, clipping, multiband compression or sidechain settings on this track.
The three opaque Google goto citation links could not be resolved with the web
tool, so their original supporting content was not verified. No stronger claim
about the song's actual production should be drawn from this answer.

Serum's documented Direct route bypasses filters and effects:
https://xferrecords.com/web-manual/serum-2/routing-an-oscillator-or-filter
That validates the routing concept, not the claim it was used on Melatonin.

## Advice evaluated

| Suggestion | Assessment for this project |
| --- | --- |
| Aggressive wavetable / Serum required | Unsupported as an identification. Basic saw/pulse shapes may be enough; waveform implementation and sonic architecture are separate decisions. |
| Three to five unison voices | Not justified by our reference or user preference. Extra oscillators can introduce beating and increase oscillator workload. Keep the existing pair until a specific need is demonstrated. |
| Set everything two octaves down | Not a universal patch setting. Our MIDI notes already encode the desired register. B-flat0 is about 29.14 Hz; transposing it down two octaves would make the main oscillator about 7.28 Hz. |
| Clean sub bypass | Useful routing experiment. The approved sub bypasses the main filter but still shares the final nonlinear waveshaper. A truly separate clean sub changes that interaction. |
| Fast attack / 300-400 ms filter pluck | Worth auditioning, but fast attack is not synonymous with rubbery. Our envelope parameters are time constants plus curvature, not literal stage durations; copying knob numbers is invalid. |
| Heavy clipping / tube / diode | Possible creative effects, not proof of the source sound. Our experiments use simple soft/hard shaping, not claims of tube or diode circuit emulation. |
| Multiband compression | A separate processing hypothesis, not yet necessary. Adds crossovers, detectors, gain smoothing and tuning choices. Do not change the approved instrument just to imitate genre stereotypes. |
| Heavy sidechain compression | Depends on kick/groove context. Neither isolated target establishes kick-trigger routing or exact ducking settings. Defer to an arrangement test with a kick reference. |
| Boost 200-500 Hz | This primarily changes low-mid body/translation, not automatically high-frequency brightness. Test a small bell rather than an ambiguous shelf. |
| Cut below 20 Hz | Often useful headroom management, but not free: our sub on B-flat0 is ~14.57 Hz. A 20 Hz high-pass reduces that contribution. |

## Eight controlled auditions

No search optimizer is used here; this is a small hypothesis test. Notes, timings,
amp envelope, main filter algorithm and source preset are unchanged except where
explicitly listed. Main-soft-drive and hard-clip are compared to the clean-sub
variant, their stated parent; other variants are compared to the baseline.

| Number | Experiment | Upper/lower energy | Reference error |
| --- | --- | --- | --- |
| 00 | Bassline v1 control | -15.34 dB | 0.1591 |
| 01 | Faster filter attack, longer decay coefficient | -15.22 dB | 0.1589 |
| 02 | Sub bypasses final waveshaper | -15.39 dB | 0.1601 |
| 03 | Additional main-only soft drive, clean sub | -15.67 dB | 0.1628 |
| 04 | Main-only hard clipping, clean sub | -16.28 dB | 0.1745 |
| 05 | Oscillator A pulse, B remains mostly saw | -13.78 dB | 0.1411 |
| 06 | +2 dB bell at 350 Hz, Q .7 | -14.46 dB | 0.1422 |
| 07 | 20 Hz second-order high-pass | -15.21 dB | 0.1569 |

Energy balance is 400-6000 Hz relative to 22-400 Hz. Reference error is the
existing Mariana comparison metric; it is descriptive, not a listening-quality
ranking. The user has previously rejected a brighter, numerically closer sound.
Accordingly no variant replaces the baseline, including the lower-error pulse
or EQ variants. The clipping result does not support blindly adding heavy drive.

## Electribe implications

Prefer changes to existing envelopes/oscillator waves before adding voices or
large effects chains. A clean sub path and one biquad EQ/high-pass need only
small state and arithmetic additions, but actual DSP cost remains unmeasured.
Hard clipping is arithmetically cheap but adds aliasing risk; our current simple
2x oversampling is not a guarantee of acceptable alias rejection.

Wavetables are not inherently expensive. Small bandlimited tables could be a
good implementation alternative to per-sample oscillator math, subject to table
memory and interpolation/aliasing tests. This does not require copying a complex
Serum patch or increasing the number of oscillators.

The current double-precision C prototype uses transcendental math and is not a
Blackfin-ready engine. A future port needs fixed-point or otherwise efficient
math, coefficient updates/tables, profiling and memory-layout work. Desktop
speed does not prove Electribe real-time feasibility. Current DSP linker settings
limit the code/data placements; no device cycle budget has yet been measured.

## Listen and rerun

outputs/sampler-in-order.wav contains a 3.5-second excerpt of each numbered
variant, followed by .35 seconds of silence, in table order (30.8 seconds total).
Individual WAVs contain the full 12.923-second phrase. Auditions are RMS-adjusted
with peak caps to reduce loudness bias; original renders and processing settings
are reproducible from run.py and report.json.

Run from project root:

```
OPENBLAS_NUM_THREADS=1 python desktop/experiments/google-ideas-2026-11-01/run.py
python desktop/experiments/google-ideas-2026-11-01/verify.py
```

All files are experiments. Baseline v1, current.json and hardware firmware
remain untouched. Recommendation: audition the pulse and low-mid EQ ideas as
options, retain the clean-sub routing as a possible instrument feature, and
defer unison/multiband/sidechain expansion until listening evidence supports it.
