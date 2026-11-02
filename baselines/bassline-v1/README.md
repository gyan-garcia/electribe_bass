# Bassline v1 — approved current baseline

Approved by the user on 2026-11-01: “lets keep this as our current bassline”.
This is the filter-only refined version, not the gentle intermediate or the
earlier rejected electro-sounding patch.

- preset.json: exact approved parameters and local source/event paths.
- voice.c: exact synthesis source, preserved independently of experiments.
- events.json: audition note sequence and estimated timing.
- preview.wav: exact short preview the user approved.
- bassline-48k.wav: full-resolution render from the same refinement.
- experiment-report.json: original experiment parameters, scores and provenance.
- SHA256SUMS: checksums of the preserved baseline files.

Architecture: two mostly-saw main oscillators with slight detuning, separate
sine sub/filter, driven mixer, 12 dB state-variable main filter, independent
amp/filter envelopes, filter keyboard tracking and output saturation.
Pulse-width and resonance modulation are disabled in this patch.

Keep this baseline intact. Future experiments should save new versions and
compare against it; do not silently replace it with a higher-scoring candidate.
User approval establishes the current working sound, not circuit equivalence
to Mariana/Model D or approval to flash hardware. This remains desktop DSP.
