# Mariana reference: brighter rubber bass

Reference copied unchanged to references/mariana/audio/Mariana_2.wav.
It is 12.923 seconds, 44.1 kHz stereo PCM, peak about 0.38 and RMS about 0.093.
The screenshot notes describe the UK Res patch; exact numerical correspondence
between the photographs and this audio has not been independently established.

User-confirmed sequence (standard MIDI numbering):

G1 x3 -> G-sharp1 -> F1 -> C2 -> C-sharp2 -> B-flat1 -> C1 -> C-sharp1 -> B-flat0 -> G1

MIDI: 31, 31, 31, 32, 29, 36, 37, 34, 24, 25, 22, 31.
Twelve strong attacks align with this sequence from about 0.50 to 9.10 seconds.
Another attack at about 11.1 seconds is represented as a retrigger of the final G1,
not a different pitch. Onset and gate lengths are estimated; user did not supply
a MIDI file. See events.json for the exact schedule used.

## Architecture changes

The portable core now exposes independent amp/filter attacks, filter sustain and
sweep curvature, filter-to-pulse-width depth, filter keyboard tracking, global
tuning, and envelope-dependent resonance. These provide mechanisms for animated,
resonant bass instead of making only a static cutoff adjustment. Parameter
estimates are not claims about the Mariana preset's actual modulation routes.

The original 16-parameter render_voice API remains available with the new controls
disabled; its previous render was checked byte-for-byte unchanged. The new
23-parameter render_rubber_voice API is used only by this desktop experiment.
No hardware firmware has been ported, modified or flashed.

## Fit and comparison

Run from project root:

```
OPENBLAS_NUM_THREADS=1 python desktop/matching/mariana_fit.py --iterations 16
python desktop/matching/test_rubber.py
```

For refinement, save architectures.json, report.json and trials.jsonl to a new
run folder, then use --warm-start with the saved architectures.json and a new
seed. The first run is archived in runs/initial. The second uses seed 20261105,
24 iterations and that archive's architecture file. Each round overwrites the
current exports; the original reference and earlier Tinashe results remain intact.

The loss uses two STFT resolutions, amplitude envelopes, brightness trajectories,
spectral centroids and upper/lower spectral energy balance. The initial pass
lowered generic error while remaining too dark. The second pass adds explicit
energy-balance weighting to address that failure. Scores across these metric
versions are not directly comparable. Warm starts are rescored under the current
metric rather than reusing their historical error numbers.

Training and architecture-selection notes are recorded separately in report.json;
the latter are not an untouched final test. Full-recording error is reported
under the same metric for old and new patches, using the same supplied notes.
Gains and phase are not matched sample-for-sample. Stereo effects, Moog circuit
behavior and exact phase/reset behavior are not emulated. Voice math is at 2x
rate; downsampling is basic, and the inherited DC blocker has rate-dependent
cutoff. Training at 24 kHz and export at 48 kHz may differ slightly.

## Listening files

- rubber-bass.wav: full 48 kHz candidate on the supplied sequence.
- rubber-preview.wav: first 9.7 seconds, downsampled to 24 kHz.
- mariana-then-synth.wav: full reference, half-second gap, then candidate;
  RMS-matched with peak caps for a fairer listening comparison.
- previous-patch-same-notes.wav: previous patch on this note schedule.

These are listening candidates, not automatically verified perceptual matches.
Test coverage includes low B-flat0 pitch, stable bounds on all filter topologies,
release, repeatability, brightness response and export headroom.
