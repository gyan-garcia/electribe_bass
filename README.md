# Electribe Bass Lab

A playable Linux monophonic synthesizer and development project for a future
Korg Electribe 2 / Electribe Sampler 2 custom bass instrument.

The current instrument runs on the desktop with MIDI input, audio output,
patch editing and saving, session MIDI Learn and WAV recording. It includes
the approved two-oscillator/sub bass engine and an independent Model D-style
prototype with three oscillators, noise, a ladder-style filter and modulation.

Model D Rubber v3 is the current sound-matching candidate. It is inspired by
a Mariana bass reference; this is not proprietary Moog/Behringer code or a
claim of circuit-equivalent emulation. The approved original bass stays separate.

## Start on Ubuntu

The existing setup targets Ubuntu 24.04 x86_64 with Python, GCC/G++, pkg-config,
dpkg-deb, the system ALSA runtime and a graphical desktop. Dependencies are
downloaded into the project; setup does not install system packages with sudo.

```sh
git clone https://github.com/gyan-garcia/electribe_bass.git
cd electribe_bass
bash desktop/live/setup.sh
bash run-synth.sh
```

Choose a MIDI input and audio output, then Start audio. An attached AKAI MPK
Mini is selected automatically when available. Wired audio is best for playing;
connected Bluetooth outputs are supported with additional latency. Audio never
starts automatically. The default master volume is -18 dB.

Select **Model D prototype → Model D Rubber v3** for the latest candidate.
**Patch volume** is clean gain saved with Model D patches, separate from drive
and the global master. Factory patches have static level compensation against
the approved bass. Right-click a synth knob to map it to the next MIDI CC;
these mappings last for the session and are separate for each engine.

Save As creates a new file in `presets/user/`, which is local and ignored by Git.
See [desktop instructions](desktop/live/README.md),
[Model D architecture](desktop/live/MODEL-D.md) and
[validation history](desktop/live/VALIDATION.md).

## Checks

After setup:

```sh
cd desktop/live
.venv/bin/python -m unittest tests test_modeld test_patch_volume -v
```

There are 27 current checks, including exact original bass waveform regression,
native block continuity, Model D synthesis, patch volume scaling, save/recall,
MIDI behavior, editor switching, recording and Bluetooth backend selection.
They do not require a physical MIDI controller or play sound on a device.

Optional matching and plotting tools also need:

```sh
desktop/live/.venv/bin/python -m pip install -r desktop/live/requirements-matching.txt
```

Run that command from the project root. Matching tools require local reference
recordings, which are deliberately excluded from the repository. Place your
own permitted files at `references/mariana/audio/Mariana_2.wav` and
`references/tinashe/audio/Tinashe_bass.wav`. The desktop app and main test suite
work without them. All preserved baseline WAVs are synthesized regression fixtures.

## Firmware development

The separate [firmware build instructions](development/README.md) pin Freetribe,
its submodules and ARM/Blackfin tools. Bootstrap clones the upstream source;
this repository tracks the build scripts, version locks and small local patch.
Downloaded tools, nested source checkouts and firmware binaries stay local.

The Model D core can be cross-compiled as an isolated Blackfin object. Actual
DSP timing, fixed-point optimization, firmware integration, onboard editing
and device patch storage remain future work. **No hardware has been flashed.**

## Repository contents

- `desktop/live/`: current GUI, native engines, tests and matching tools.
- `presets/`: approved pluck and experimental Model D settings.
- `baselines/bassline-v1/`: immutable approved source, patch and audio fixtures.
- `desktop/matching/` and `desktop/experiments/`: earlier research and experiments.
- `development/`: reproducible Freetribe build scripts and dependency locks.

Reference recordings/screenshots, virtual environments, tools, build outputs,
recordings, personal presets and historical run logs are ignored. Existing
third-party code retains its own notices; Freetribe and dependencies are fetched
from their upstream projects rather than republished here.
