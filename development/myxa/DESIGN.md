# MYXA v1 firmware design

Status: initial design, not hardware-validated. No hardware flashing is authorized
by this document. Desktop sound reference: commit 17eb21d. Foundation: pinned
Freetribe source 5fe6658a6038fea70c8e802ae61d8a67bf22ff3a.

## Product scope

A dedicated monophonic bass synthesizer for Electribe sampler 2. No sampling,
multiple parts, or sequencing. Preserve the desktop synth and reference renders
as regression fixtures; never optimize the hardware sound silently.

Required: patch selection and on-device editing/saving, chromatic pad keyboard,
serial MIDI input with channel selection, cutoff/resonance controls, overall
Volume, patch Pan, three-band EQ, stereo room reverb, stereo output and a
five-second MYXA startup animation. Ship UK Res Bass, BOSS 03 and Moog Res.

## Evidence and unknowns

Pinned docs report a 128×64 pixel display, panel callbacks, serial MIDI over TRS,
ARM/DSP communication and audio module API. USB and SD-card drivers are listed
as planned, not completed. Do not promise USB MIDI in v1. The existing monosynth
example has KNOB_RES, KNOB_EG, KNOB_LEVEL and ENCODER_CUTOFF; BUTTON_AMP_EG is a
button. User's tentative Amp/EG-to-drive mapping needs physical control
identification. Pan and master Volume implementation must be traced through the
panel, codec and analog path; an analog master volume may work without firmware.

The ARM linker currently uses 128 KiB on-chip code/data and a separate 8 KiB
vectors/stack region. Prior build used 117152 bytes of the 128 KiB region. This
is not a full hardware memory inventory. External DDR exists in initialization
source but usable capacity, correctness and execution placement are unverified.
Blackfin linker declarations include 64 KiB code plus a 16 KiB code/cache region,
two 32 KiB data banks and 4 KiB scratch. Physical placement restrictions matter.

## Architecture

ARM application owns panel/UI, note arbitration, MIDI parsing/channel filtering,
patch editing, storage, and communication with DSP. DSP owns oscillators, audio
rate envelopes/modulation, filter, EQ, pan, reverb and output protection. Existing
Freetribe CPU envelopes are replaced or bypassed for this engine, not run twice.

Signal path:
three oscillators/noise → mixer drive/feedback → ladder filter → amplitude/output
drive → DC removal → EQ → dry pan + stereo room send → stereo wet/dry mix →
patch gain → overall digital gain if needed → output protection → L/R codec.
Retain the desktop processing order where this diagram is abbreviated. Port
oscillator phase, envelopes and nonlinear filter behavior before optimization.
Use the 18 dB ladder output for the initial three patches. Keep 24 dB as a
supported engine option if cost permits; do not change patch filter mode silently.

Stereo reverb is NOT implemented in the current desktop engine. Prototype there
first. Evaluate a shared delay network with two decorrelated output taps rather
than blindly doubling the mono network. Pan controls dry position and spatial
send; the wet field retains width. Define center level against desktop fixtures
so equal-power panning does not accidentally change existing patch loudness.

ARM sends versioned commands: note on/off, parameter update, panic, and full
patch transaction. Commands carry sequence IDs; patch transfer uses begin/data/
commit and acknowledgement. DSP adopts a complete validated patch at a safe
processing boundary, never partially received values. Bound queue size, coalesce
continuous controls, prioritize note-off/panic, and recover from protocol errors.
No filesystem access, dynamic allocation or unbounded work in audio processing.

## Resource gate before feature integration

Produce ARM/DSP linker maps listing code, static data, stack reserves, heap,
transport buffers, display buffers, delays and lookup tables. A single packed
128×64 monochrome framebuffer is 1024 bytes; avoid stored full-frame animation
sequences. Current mono room delays use about 30 KiB at 48 kHz, excluding other
DSP data; stereo must be budgeted explicitly. SD filesystem code also competes
for ARM memory. Desktop floating-point performance is not evidence of Blackfin
performance. Measure worst-case DSP time at maximum resonance, modulation,
reverb decay and simultaneous panel/MIDI activity. Target at least 25% processing
headroom, subject to measured scheduling constraints. Resolve memory placement
before implementing the complete UI. Test external memory before relying on it.

## Performance controls

| Control | Function | State |
|---|---|---|
| Cutoff | Filter cutoff | Required; source uses encoder event |
| Resonance | Filter resonance | Required; knob exists in example |
| Amp/EG area | Mixer drive | Provisional; button vs knob ambiguity |
| Pan | Equal-power dry position and reverb send position | Required; event mapping to audit |
| Volume | Final listening level, not recalled by patch | Required; analog/digital path to audit |
| Pads | 16 consecutive semitones beginning on C | Required |
| Octave controls | Shift pad keyboard by octaves | Proposed physical buttons pending audit |
| Data/value selector | Browse patches and edit selected menu values | Proposed |
| Write/Save action | Save or Save As | Proposed physical binding pending audit |

Absolute knobs use pickup after patch recall. Relative encoders use increments,
not pickup. Display parameter name/value and a pickup-direction cue. Mixer drive
changes tone; it must not replace the overall Volume function. Smooth continuous
DSP controls. Patch gain and pan belong to the patch; master Volume does not.

Pad default proposal: MIDI note 36 through 51, C through D-sharp. Note numbers
are authoritative because octave labels differ between products. Octave shifts
must clamp to MIDI range. Track each held pad's original note so changing octave
while held cannot cause stuck notes. Pad velocity capability remains to verify;
use a documented fixed velocity if unsupported.

Pads and MIDI share one last-note-priority stack, keyed by source/channel/note.
Releasing the newest note returns to the previous held note. Sustain applies to
MIDI notes. Legato/glide follow patch settings. Handle overlapping pad/MIDI notes,
repeated note-ons, velocity-zero note-offs, all-notes-off and all-sound-off.
Channel change clears held MIDI notes and sustain. MIDI channel is global 1–16
or Omni, persisted separately. Support pitch bend, mod wheel and sustain; define
bend range explicitly in the shared schema. A bounded overflow triggers a safe
note-state reset. Provide a physical panic gesture after the button audit.

## Screen and interaction

Boot state: mute audio, show a procedural waveform (0–1 s), morph/reveal MYXA
(1–3 s), hold MYXA (3–5 s). Run initialization concurrently without blocking
control tasks. At five seconds show the patch screen only when ready; otherwise
show initialization progress or an actionable error. Never unmute an unready DSP.

Home: patch name, edited marker, MIDI channel, compact selected parameter/value.
Knob movement temporarily highlights its parameter; return to home without
losing edits. Pages: Sound, Filter/Envelope, EQ, Reverb, MIDI/System, Save.
Advanced oscillator/modulation settings remain accessible via parameter pages;
physical knobs need not expose every parameter at once. EQ has Bass/Mid/Treble
and a small static response curve, no FFT. Reverb has Mix/Decay only.

Patch browse previews names, not destructive loads; confirm to load. If dirty,
offer Save / Discard / Cancel before replacement. Save As edits a name with a
character cursor and creates a new entry; overwriting requires confirmation.
After load, reset notes/effect tails and ramp audio to avoid discontinuities.
Exact button assignments remain a design task, not established hardware facts.

## Patch format and storage

Embed the three factory patches as immutable data; available with no SD card.
Save user patches under /MYXA/PATCHES on SD. Maintain just current/edit patch
buffers and a paged directory cache in RAM, not all patches. No fixed library
size promise until filesystem and browsing limits are measured.

Proposed binary format: magic MYXA, schema version, engine identifier, payload
length, stable patch ID, UTF-8 name (bounded to 32 bytes), stable parameter-ID /
32-bit value entries, and CRC32. Encode endianness explicitly, not native C struct
layout. Validate ranges, enums, lengths and finiteness before adoption. Reject
unsupported major versions; preserve defined defaults for missing optional fields.
Target under 1 KiB for current parameter counts, budget up to 2 KiB with metadata;
this is a design estimate, not a measured format size. Provide desktop JSON ↔
MYXA conversion and round-trip tests before shipping patches.

Save transaction: write a temporary file, flush/close, reopen and verify, preserve
previous valid copy, then promote the new file. Do not assume FAT rename is
power-loss atomic. Recovery scans temp/backup files and chooses a verified version;
show success only after completion. Fault-test card removal and power loss at
every transaction stage. If card absent/full/read-only, retain edits in RAM and
show the reason. Save must not block audio. Persist global MIDI channel/pad octave
in a separate versioned settings file; use defaults when unavailable.

SD work requires driver, block I/O and filesystem integration. Audit driver and
filesystem licensing. Avoid internal flash writes until a safe reserved region,
wear strategy and DSP/flash shared-SPI arbitration are established.

## Delivery stages and acceptance

1. Hardware audit: verify model/revision, control IDs, display primitives, audio
   channel routing, SD interface and memory maps. Deliver control map and budgets.
2. Shared engine/schema: portable dry core and patch conversion. Compare three
   factory renders with desktop references, pitch, envelopes, resonance and aliasing.
3. DSP integration: prove real-time performance and stable memory/stack usage;
   stereo dry output and pan first, then EQ and stereo room within measured limits.
4. ARM instrument: pad/MIDI arbitration, direct controls, pickup, patch browse,
   parameter pages and MYXA animation. Test queues and patch transactions on host.
5. Storage: card support, naming, save/load/recovery; verify desktop round trips.
6. Hardware validation: only after explicit authorization and a verified recovery
   procedure. Check stuck notes, output levels, left/right isolation, boot failures,
   prolonged play, rapid patch changes, MIDI bursts and writes while playing.

A build or emulator pass is not a hardware pass. No automatic flashing, factory
firmware overwrite, or promotion of altered-sounding optimizations. If resources
cannot support a required feature, present measured alternatives before reducing
scope. Preserve all approved desktop patches and baseline fixtures.
