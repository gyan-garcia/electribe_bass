# First live application build — 2026-11-01

Ten automated test groups pass. In particular:

- Raw native output is sample-identical to the archived engine across block
  boundaries of 1, 7, 128, 256, 513 and 4096 frames.
- The complete archived Bassline v1 48 kHz PCM render is reproduced exactly.
- MIDI priority/sustain/velocity-zero note-off, pitch bend, legato, panic,
  queue overflow recovery, CC Learn and input-channel filtering are tested.
- Patch saving creates new exclusive files and preserves all approved hashes.
- GUI loading retains the full preset precision, independent of knob displays.
- WAV recording finalizes stereo headers and captures identical left/right data.

The latest callback benchmark is in outputs/callback-benchmark.json. Typical
rendering was about 0.13 ms per 256-frame buffer with ~0.17 ms p99 in the initial
check, against a 5.33 ms audio buffer period. Results vary with load; this is not
hard-real-time certification, end-to-end latency, or a Blackfin benchmark.

The physical ALSA MIDI port MPKmini2:MPKmini2 MIDI 1 28:0 was opened successfully.
The two-second silent device test opened the built-in ALC3234 Analog output at
48 kHz/256 frames, reported 10.67 ms output latency, and recorded zero underruns
and no callback errors. The check produced silence, not audible test notes.
Actual keyboard performance and speaker/headphone sound still require user play.

The graphical window was rendered offscreen and visually checked. A normal
desktop instance was launched with audio stopped and MPK auto-connection enabled.
The application log is outputs/app.log; device details are outputs/device-check.json.

No privileged system installation was completed. PortAudio and ALSA build headers
were downloaded/extracted into vendor; Python MIDI/audio packages were installed
in the project venv, with a compiled CPython 3.13 RtMidi wheel cached locally.
The original Qt/NumPy runtime is inherited from the existing Python environment.
Exact installed versions are in outputs/environment.json.

Bluetooth follow-up: two additional tests pass for listing system Bluetooth sinks
when PortAudio lacks a pulse device and selecting/stopping the fallback backend.
A silent playback connection to EDIFIER R1700BT passed, reporting ~213 ms buffering.
The libpulse-simple backend does not expose underrun counters; zero in the initial
Bluetooth diagnostic was an unmeasured counter, not evidence of zero underruns.
There are now 12 passing automated test groups. Existing open app instances need
a restart to load this backend; unsaved edits are not discarded automatically.

Bassline v1, bassline-pluck and the firmware sources were not changed by this app.
The existing earlier CPU Makefile path patch remains the only firmware-tree diff.

Session MIDI mapping update: 14 automated test groups now pass. New tests cover
right-click opening the Map to MIDI action without changing the knob value,
visible waiting/highlight, CC assignment, cancellation/removal, one-to-one remap,
reserved pedal CCs, mappings surviving patch changes, and fresh empty mappings
in a replacement window. Mapping actions are checked not to write files and
startup is checked not to read the old preferences.json mapping data. Existing
baseline audio parity and integrity checks continue to pass.

## Separate Model D prototype — 2026-11-01

23 tests now pass (outputs/modeld-tests.log). The nine new checks cover all
factory patch schemas/discovery, independent oscillator waveforms and ranges,
sample-identical processing across buffer sizes, noise and modulation routing,
filter modes and self-oscillation, 60 seeded extreme parameter combinations,
exclusive patch saving, per-engine session MIDI maps and GUI engine switching.
Pending notifications from another engine are ignored by its replacement UI.
All original 14 tests, including exact baseline audio parity, still pass.
All seven archived Bassline v1 checksums pass independently.

outputs/modeld-validation.json records a 48 kHz / 256-frame desktop render
median of 0.109 ms for bass (p99 0.229 ms), and 0.148 ms with filter FM (p99
0.211 ms), against a 5.333 ms buffer period. This includes Python orchestration,
but not physical device or end-to-end MIDI/audio timing. No new physical audio
test was performed; existing device checks above describe earlier versions.

The isolated core cross-compiles with the pinned Blackfin compiler using the
firmware's existing bf527 CPU flag. Its object contains 7,984 bytes before
linking maths libraries, and has unresolved software float and transcendental
calls. This proves source compatibility only. On-device speed, complete memory
usage, DSP integration and fixed-point optimization remain unverified.

The reference tuning experiment evaluated 541 candidates with seed 20261101.
The weighted score on notes excluded from search fell from 0.17783 to 0.13860
(lower is better). These are internal spectral/envelope metrics, not a measured
percentage of perceptual similarity. The result is Model D Reference — candidate,
not a new approved baseline. outputs/modeld-fit contains the trial history,
configuration/report, solo WAV and Mariana → approved bass → candidate audition.

The new GUI was rendered and visually checked offscreen. Existing desktop
instances were not terminated or restarted, protecting any unsaved edits.
Firmware sources and hardware remain untouched by this update.

## Settings refinement for rubbery movement — 2026-11-01

Three further settings-only experiments evaluated 4,637 candidates. The native
Model D source is unchanged (SHA256 9b852eecfba5e9e6bf4a365cf4339764ace9e3534a6e92d3a9e748bbdb13dded).
The objective now targets Mariana directly and emphasizes early moving spectral
bands in addition to the existing spectral/envelope measures. Trials include
oscillator mixtures, mixer drive, feedback, emphasis, contours, glide and
keyboard tracking. One run deliberately constrains a stronger-emphasis contrast.

The packaged primary candidate is Model D Rubber v3; the contrast is Model D
Rubber Resonant. With the same movement metric applied to final 48 kHz renders,
the score on notes excluded from the main search is 0.20516 for the previous
Model D candidate, 0.15611 for Rubber v3 and 0.17762 for Resonant. These metrics
cannot establish a subjective match. Check notes are from the same recording
and were used for candidate selection, not an independent final blind test.

outputs/modeld-rubber-audition/summary.json identifies all three source runs,
their reports, metrics and protected-file hashes. Full JSONL trial histories,
presets and source snapshots are retained in each successful run directory.
All 23 tests still pass (outputs/rubber-tests.log), and all seven archived
baseline checksums pass. The approved patch, pluck, previous Model D candidate
and both synthesis engines remain unchanged. Nothing was flashed or restarted.

## Clean Model D patch volume

27 tests pass, including four new checks for legacy/default gain handling,
bounded finite values, patch volume save/recall, samplewise linear waveform
scaling, smooth live edits and GUI/engine switching. Native synthesis parameters
are unchanged by clean gain. The original raw bass audio still matches exactly.

All 14 Model D factory presets now contain output_gain_db, statically calibrated
against the approved bass's raw phrase RMS. Every phrase matches within 0.005 dB
of that reference in this calibration, with peak headroom at the default master.
Rubber v3 uses +11.84 dB; the resonant candidate uses +21.84 dB. This is phrase
RMS matching, not a perceptual loudness guarantee for every note or later edit.
The existing final clamp can still engage at high master levels or after edits.

balance_modeld.py retains backups and a report in a unique ignored output folder.
Only factory output_gain_db metadata was added; all synthesis parameter values
remain identical. No native oscillator/filter code, approved baseline or pluck
preset was changed. The new GUI was rendered and visually checked offscreen.
