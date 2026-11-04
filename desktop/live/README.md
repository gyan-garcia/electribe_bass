# Electribe Bass Lab

Standalone Linux synth with the approved bass engine and a separate Model D-style
prototype. No Electribe connection or firmware update is involved. Bassline v1
and bassline-pluck remain protected.

## Start

From the project root, run `bash run-synth.sh`, or run launch.sh in this folder.
An application launcher is also supplied as Electribe-Bass-Lab.desktop.

The MPK Mini input is selected and connected automatically when available.
Otherwise choose a MIDI input and press Connect MIDI. Choose your audio output
and press Start audio. The initial master level is -18 dB and audio never starts
automatically. Use wired headphones/speakers for responsive playing. Connected
Bluetooth speakers/headphones are also listed with a Bluetooth suffix through
the system PulseAudio/PipeWire compatibility service.

For Bluetooth: save edits, reopen the app after an update, select your speaker
(for example EDIFIER R1700BT · Bluetooth), and press Start audio. If it is missing,
connect it in Ubuntu Bluetooth settings, stop audio and press Refresh devices.
The first Bluetooth smoke test reported ~213 ms buffering; actual perceived delay
may be greater. This is suitable for auditioning but poor for tight live playing.

On this machine the built-in output is HDA Intel PCH / ALC3234 Analog (hw:0,0).
The silent smoke test opened this device at 48 kHz, 256 frames, with 10.67 ms
reported output buffering and zero underruns during the two-second check.
That is not measured key-to-speaker latency or a long-run stability guarantee.
If an output is occupied by another application, stop that playback or choose
another output. Device numbers can change; select by displayed name.

## Play and edit

The active library contains 26 patches, all in `presets/user/`. Model D uses a
fixed **24 dB/octave low-pass** filter. Filter type and slope selectors have been
removed. The six former 18 dB patches have adjusted cutoff, contour depth and
clean gain to approximate their original sound; the other 20 patches are unchanged.
Legacy 18 dB imports now load through the 24 dB engine. Historical audition files
remain research references. See `24DB-MIGRATION.md` for backups and comparisons.

- Select **Approved bass** or **Model D prototype** using the engine selector
  beside Patch. Switching engines releases held notes. Save edits before switching.
- Model D Init starts with one saw oscillator. Model D Bass and Model D Pluck are
  initial listening candidates. Model D Reference is an experimental reference
  fit, when generated, and is the default when first selecting Model D; none
  replaces the approved baseline. Model D Modulation
  demonstrates oscillator 3 as a modulation source.
- Last-note-priority monophonic playing, velocity, pitch bend (+/-2 semitones),
  sustain pedal (CC64), glide and optional legato. Note-on velocity zero releases.
- Both approved patches load from the patch list. The on-screen keys provide
  C1-B2 auditioning; the MPK's octave buttons reach lower notes such as B-flat0.
- Four tabs expose all 23 approved bass parameters; Model D has 47 controls in
  seven scrolling tabs. Waveforms, ranges and switches have named selections.
  Cutoff/resonance changes are smoothed
  over an 8 ms time constant; master/velocity gain use a 5 ms time constant.
  Other edits are currently block-boundary updates and may zipper if moved fast.
- Right-click an on-screen knob and select Map to MIDI. That knob highlights and
  shows Waiting for MIDI… until the next controller knob sends a normal CC. Once
  mapped, it displays the CC number and channel and follows that controller.
  The toolbar can also map the selected knob or cancel a pending assignment.
- Right-click again to cancel waiting or remove a mapping. Reassigning replaces
  the previous connection: one controller CC per software knob and vice versa.
  Clear MIDI mappings removes every assignment for the current session.
- Mappings are channel-specific and session-only. They survive patch changes,
  audio stops and reconnection within the running app, but reset on exit. They
  are kept separately for each engine and restored when switching back. They
  are not saved in presets or preferences. Older preferences.json mapping data
  is ignored; no previous file is deleted. Sustain, reset and all-notes-off CCs
  remain reserved; CC1 is available to learn. Mapping works with audio stopped.
- In Model D mode, unassigned CC1 controls Mod Wheel Amount. A learned CC1 mapping
  overrides this default. Turn on Oscillator Modulation or Filter Modulation to
  hear the selected sources, mix and depth through the wheel.
- Save As writes a new named patch into presets/user. Existing names get a numeric
  suffix; the original patches cannot be overwritten through the editor.
- Model D has a separate **Patch volume** field beside Master. This is clean
  output gain (-24 to +24 dB), saved with each patch and smoothed by the existing
  5 ms gain stage. It follows all voice distortion/filter processing and does
  not affect internal feedback. Output Drive continues to change saturation.
  Factory patches have been balanced against the approved bass's phrase RMS;
  Rubber v3 uses +11.84 dB. Older imported patches without the field default to
  0 dB; adjust Patch volume and Save As when needed. Master remains global.
  Changing the sound afterward may require readjusting volume; this is static
  compensation, not automatic gain control. The output meter/clamp still applies.
- Import reads supported JSON patches; it never executes engine_source paths.
- Panic immediately resets held notes and voice state at the next callback.
- Record WAV saves the stereo mono-duplicated output into outputs/live-recordings
  under the project root, using Los Angeles timestamps. Recording stops with a
  visible error if the writer cannot keep up; disk I/O runs outside the callback.

An unsaved-change prompt appears before replacing an edited patch or closing.
Imported approximate ladder patches can be played and identified by the filter
label, but the approved patches use the 12 dB SVF and the editor doesn't switch
architecture behind the user’s back. Source engine schemas/paths in saved JSON
are metadata; the application runs only its bundled native engine.

## Engine and validation

Model D mode is a new synthesis architecture, not a replacement filter bolted
onto the approved bass. Its documented scope and hardware limitations are in
MODEL-D.md. Save As stores engine identity and all its parameters in each patch.
The existing approved patch format remains supported.

native/voice.c is a stateful adaptation of the approved baseline source. The
oscillator, envelopes, filter and DC-blocker states persist across audio buffers.
The original oscillator/filter algorithms, coefficients and internal 2x sampling
remain intact for constant patches. Native process blocks allocate no memory;
the Python orchestration and MIDI queues are not a hard-real-time system.

The raw native engine is tested sample-for-sample against the archived source,
using block sizes 1, 7, 128, 256, 513 and 4096. Its entire approved phrase also
reproduces the archived 48 kHz PCM render exactly. The live output adds a master/
velocity gain stage and a final safety clamp, so a recording at the default
master level is intentionally quieter than the archived raw render.

Tests also cover note priority, sustain, zero-velocity note-off, pitch bend,
legato, panic, queue overflow recovery, MIDI Learn/channel filtering, exclusive
patch saving, GUI preset precision, recording and baseline checksums.

Run `.venv/bin/python -m unittest tests test_modeld test_patch_volume -v` from this folder.
`validate_modeld.py` measures desktop processing and cross-compiles an isolated
Blackfin object without touching firmware. `modeld_preview.py` regenerates factory
auditions without overwriting existing presets. `fit_modeld.py` runs a bounded,
seeded reference experiment and saves a new candidate; it additionally uses SciPy
from the existing matching environment. Device checking needs normal
desktop audio/MIDI access; run diagnose.py with the same LD_LIBRARY_PATH and
LIBRARY_PATH established in launch.sh. --smoke-audio opens a silent output for
two seconds; it does not send notes to the controller or play a test tone.

## Rubber refinement auditions

The new presets **Model D Rubber v3** and **Model D Rubber Resonant** are settings
for the same existing Model D core. Neither replaces an approved patch or the
previous reference candidate. Save edits and reopen the app to refresh its patch
list, then select Model D prototype and the named patch.

outputs/modeld-rubber-audition contains the solo candidates and short/full
comparisons, in this order: Mariana, previous Model D, Rubber v3, Resonant.
The clips use static RMS matching with a peak cap; no extra effect or sample
layer is added to the synthesized voice. summary.json records the source runs,
protected-file hashes and scores measured from the final 48 kHz renders.

refine_modeld_rubber.py performs a seeded search of the existing controls, with
extra weight on early timbre movement. It creates a unique run folder and saves
presets exclusively. --resonant constrains a contrasting low-drive/high-emphasis
search; --local-only --start-patch PATH refines a prior candidate. Optional
--label changes the saved candidate name. SciPy is required as in fit_modeld.py.
analyze_modeld_rubber.py RUN_FOLDER generates a plot of measured level and
brightness movement. These are proxies, not measurements of circuit cutoff.
package_modeld_rubber.py RUN_FOLDER... packages completed normal and resonant
runs into the listening comparison. Listening approval remains pending.

## Dependencies and scope

### Small dark room reverb

Both engines have a Reverb tab with Mix (0–100%) and Decay (0.15–2.5 seconds).
Mix defaults to zero and preserves the dry samples exactly. Save As stores both
controls per patch; old patches load dry. The signal order is voice → EQ →
reverb → patch/master gain → output clip guard. Panic and patch changes clear
the tail. Decay is a nominal feedback decay time; high frequencies fade faster.

The native mono algorithm uses four parallel damped comb delays followed by two
allpass diffusers, with a 180 Hz input high-pass and 2.8 kHz feedback damping.
Mix and feedback adjustments are smoothed over 20 ms. It allocates delay memory
only at creation (about 30 KiB at 48 kHz), with no FFT or convolution. This is
portable C, but Blackfin CPU cost and memory placement remain unverified.
Desktop offline previews include the effect within their existing render length.
The two effect controls currently do not support MIDI learn.

### Patch EQ

Both engines have three EQ knobs: Bass, Mid, and Treble (±12 dB).
Frequencies are fixed at 100 Hz, 700 Hz (Q 0.7), and 2500 Hz respectively.
All three at zero is flat; there is no enable switch or reset button.
Save As stores the settings per patch. Existing advanced EQ patches retain
exact settings when loaded; a visible note explains that editing any tone knob
converts them to the fixed tuning. Previously bypassed EQ starts at zero.
EQ knobs do not currently support MIDI learn.

The monochrome display shows the EQ response, not an audio spectrum. It uses
64 logarithmically spaced points from 20 Hz to 20 kHz and a fixed ±24 dB scale.
It redraws only on edits or patch loads, without audio capture or an FFT.
For a hardware port, the response calculation in eq_view.py can be translated
to C (complex operations can be replaced by real arithmetic) and rendered as
a polyline using the target display driver. Qt itself is desktop-only;
Electribe display integration and timing have not been implemented or verified.

The three native biquads follow the
[RBJ Audio EQ Cookbook](https://www.w3.org/TR/audio-eq-cookbook/), after the voice's
drive stages and before patch/master gain and the final output clip guard.
Coefficient and bypass changes use 20 ms smoothing. Boosting EQ can increase
output peaks; lower patch or master volume if the clipping indicator lights.
Offline Model D previews also apply the saved EQ. The original factory presets
and approved baselines are unchanged. Electribe DSP timing remains unmeasured.

setup.sh targets this Ubuntu 24.04 x86_64 environment. It keeps audio libraries
and build headers under vendor, Python packages under .venv, and compiled MIDI
wheels under wheels. It requires the system ALSA runtime, GCC/G++, pkg-config,
dpkg-deb and Python. Cached Ubuntu packages avoid a privileged installation.
The existing environment inherits installed PySide6/NumPy; requirements.txt pins
their versions for installation on another compatible environment. Cached native
wheels are specific to CPython 3.13 and x86_64; other Python versions need a rebuild.

The GUI never changes the system default audio output. Native ALSA outputs remain
available for low latency. If PortAudio lacks a pulse device, a dedicated worker
uses libpulse-simple to connect directly to the chosen PipeWire/PulseAudio sink.
Blocking writes stay off the GUI thread. This fallback reports buffering latency
but cannot report underrun counts, so the UI shows n/a. Stopping flushes queued
audio where the server allows. The input is read-only MIDI; no hardware is programmed.

This is the desktop testing instrument, not a VST or a finished Electribe port.
The C core still uses floating-point/transcendental math. Blackfin timing, fixed-
point adaptation, onboard UI and device patch storage remain later stages.
