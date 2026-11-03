# Video-derived Model D banks

These 49 playable adaptations use the existing **24 dB Model D engine**. They
do not modify the engine or the three previously saved user patches. They are
source-based recreations, not verified identical reproductions of the videos.

## Doctor Mix: five sounds

[Top 5 Greatest Minimoog Sounds](https://www.youtube.com/watch?v=cxDTIpWvtzo):

| Patch | Start | Core settings |
| --- | --- | --- |
| DM - Hip-Hop Lead | 0:54 | One saw, glide, triangle vibrato |
| DM - Soulful Bass | 3:34 | One low saw, plucked amp and filter with sustain |
| DM - Spaceship | 6:47 | Saw oscillator with oscillator-3 pitch modulation |
| DM - Power Bass | 9:18 | Saw at 16 ft, square an octave below |
| DM - Super Lead | 12:49 | Three saws at 8/16/32 ft, open filter, glide |

Settings were inferred from the spoken instructions and selected panel frames.
The video often changes controls while playing and does not provide exact Hz,
seconds, or fixed patch snapshots. The saved values represent one usable state.
Spaceship is the oscillator-modulation variation, not the alternate filter-only
variation. Super Lead includes our room reverb; the demonstrated external delay
is not implemented. Mod wheel and oscillator-3 frequency are performance controls.

Short musical excerpts were also examined numerically. Bounded searches of
cutoff/contour/decay/resonance improved the normalized harmonic-spectrum metric
for Hip-Hop Lead and Soulful Bass; those two refinements were retained. The
Power Bass change barely improved the metric and was rejected. Super Lead was
left as instructed. These comparisons infer note pitches and onset timing and
do not establish perceptual identity or measure the full performance/effects.
The measured results are in `doctor-mix-refinement.json`.

## TimLfk: 44 sounds

[Behringer Model D Presets/Patches](https://www.youtube.com/watch?v=J33nnF19Qnk)
demonstrates the 44 named charts on pages 55-76 of
[Moog's official manual](https://cdn.inmusicbrands.com/Moog/Model%20D/Minimoog_Model_D_Manual.pdf).
The bank uses the `TL -` prefix and preserves those chart names. The video's
"Droning Bass Intro" is called "Droning Brass Intro" in Moog's chart.

The normalized pointer positions, waveform/range selections, switches, wheel
positions and video timestamps are saved in `timlfk-charts.json`. They were
extracted from the manual's vector diagrams, accounting for the alternating page
offsets, and spot-checked visually. Blank controls use neutral defaults.
Source media and the original PDF stay in ignored local output folders.

## Adaptation limits

- The analogue control transfer curves have not been measured. Manual cutoff
  uses an approximate logarithmic 10 Hz-20 kHz mapping, clamped to our 20 Hz-
  18 kHz range. Resonance maps to 0-1.1 and contour to 0-8 octaves. Sustain is
  linear. Envelope times interpolate the printed time ticks; attacks above 3 s
  and decays above 5 s are shortened and flagged per patch.
- Original range/waveform/mixer selections are retained. Pitch tuning uses the
  printed +/-7 semitone scale. LO stays on the engine's LO oscillator path;
  untracked audio oscillator frequency is approximate. Dedicated LFO speed,
  glide curves, and modulation depth are approximate too.
- Arrows by the wheel indicate movement. Selected ordinary keyboard patches
  start with the wheel down; effect patches retain the indicated modulation.
- Feedback uses the existing engine's return path, which differs from the
  hardware's normalized external input. Filter-only patches use a tiny noise
  seed to start the existing self-oscillating ladder. Audio-rate modulation,
  resonant pitch tracking and waveform phase can differ from hardware.
- TimLfk describes light reverb and tape saturation in the recording. These
  patches use a very small room send and the engine's existing saturation, not
  a model of that external tape processor. The two banks have not all been
  fitted to reference audio.

## Install and audition

Run `desktop/live/.venv/bin/python desktop/live/video_patch_bank.py` from the
repository root. It installs missing files in `presets/user`, never overwrites an
existing filename, validates all settings, and renders four-note auditions.
Clean patch gain is calibrated over C2-C6 and full-wheel modulation, within the
engine's +/-24 dB range. Existing user files are checked for byte-level changes.

The local listening page, WAVs and validation report are under
`desktop/live/outputs/video-recreation/`. Audio checks cover finite output,
non-silence and clipping, not a listening approval. Restart the desktop synth to
refresh its selector. All new patches belong to the Model D family.
