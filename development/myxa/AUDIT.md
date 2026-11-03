# MYXA integration audit — initial pass

## Verified in pinned source

- cpu/src/apps/monosynth/monosynth.c: knob IDs level 0x00, pitch 0x02,
  resonance 0x03, EG intensity 0x04, modulation depth 0x05, attack 0x06,
  decay 0x08, modulation speed 0x0a. Encoder IDs oscillator 0x01,
  cutoff 0x02, modulation 0x03. Amp EG button 0x20.
- dsp/src/modules/monosynth/monosynth.c module_process accepts input/output
  pointers and writes out[0] and out[1]. Both currently receive the same sample.
  Stereo adapter slots exist; physical output routing still needs hardware tests.
- cpu/src/kernel/service/svc_panel.c notes that continuous trigger-pad mode uses
  KNOB_EVENT messages. Do not interpret every knob message as a rotary control.
- cpu/cpu.lds and dsp/dsp.lds are the linker-map audit entry points.
- Pinned docs features.md lists USB and SD drivers as planned.

## Proposed panel map after user photos

Stable performance controls: cutoff, resonance, filter EG amount, glide,
patch level, pan, modulation rate/depth, mixer drive on Sample Edit, reverb
Mix on Insert FX Edit and Decay on Insert FX selector. Oscillator selector
changes oscillator 1 waveform. Value encoder navigates and edits menus.
Amp EG button selects amp vs filter envelope for Attack/Decay, with visible
screen/LED state. Shared envelope controls need per-target pickup states.
Part arrows shift keyboard octave; pads are chromatic. Write opens save,
Exit returns home, Stop is panic. All assignments beyond source-confirmed IDs
remain provisional until panel event verification. Master Volume may be analog.

Source-confirmed IDs must be tested against the photographed unit. Pan, sample
Edit, effects controls, navigation, pad order and release events still need a
complete event table. Do not infer numeric IDs from physical position.

## Important engine limits

The current Model D engine does not expose independent amp/filter release time
parameters: release uses its existing decay convention and release enable.
Do not implement an apparently independent release control without first
extending and testing the desktop engine. Amp/Filter Attack and Decay switching
can use existing parameters. The current reverb is mono; stereo design is pending.

## Initial shared contract

export_schema.py generates schema.json and parameters.h from desktop parameter
ranges and the three approved patches. IDs start at 1 and are frozen by checking
against the existing schema on regeneration. Engine IDs retain desktop 3/4.
54 float32 values take 216 bytes per patch before name/header/checksum and any
parameter-ID encoding. This is not the final SD wire format. Native C structures
must never be written directly to disk or SPI. Pan starts centered. Fixed EQ
conversion rejects enabled custom frequency/Q tuning rather than altering sound.

## Next implementation gates

1. Capture actual ELF section sizes and placement for both processors; inspect
   stacks, heap, DSP library footprint and external-memory initialization.
2. Complete panel event table and define MIDI/pad arbitration independent of UI.
3. Cross-compile the shared sound core and adapter. Floating-point cost and
   sample-by-sample callback overhead must be measured before choosing numeric
   optimizations. Keep original reference output for comparison.
4. Define bounded serialized patch transport with validation and atomic adoption.
5. Add UI/boot animation and SD driver/filesystem after memory placement is viable.

No desktop engine, original patch or firmware image was changed by this pass.

## Measured baseline ELF and dry adapter results

Run `bash development/myxa/check_dry.sh` from repository root. Detailed section
placements and ELF hashes are generated in build/memory.json (ignored build data).

| Region | Linked occupied span | Capacity |
|---|---:|---:|
| ARM on-chip | 117152 | 131072 |
| ARM vectors/stack | 8192 | 8192 |
| DSP L1 code | 9888 | 65536 |
| DSP code/cache | 0 | 16384 |
| DSP data A | 12320 | 32768 |
| DSP data B | 0 | 32768 |

DSP scratch has no linked sections, but its 4096 bytes supply the stack via linker
symbols. Do NOT count that as spare delay memory. Zero linked sections elsewhere
do not establish runtime availability or cache configuration. ARM page_table
occupies 16384 bytes; bfin_ldr occupies 19480 bytes. Crucially the DSP loader is
embedded in the ARM image: DSP growth can consume ARM space too. The budgets
are separate at execution time but coupled by the current boot packaging.

The isolated dry_adapter.o cross-compiles for the upstream BF527/BF523 flags:
5740 bytes text/readonly data, 540 bytes BSS, no initialized writable data.
These are OBJECT sizes, not a linked firmware estimate. Math/runtime imports
remain unresolved and will add code. The adapter uses software float/double
helpers, exp/expf/exp2f, powf and tanf. Its single-sample bridge recalculates setup
coefficients every callback: unsuitable to declare real-time ready without
profiling and likely coefficient caching/control-rate refactoring.

Host dry bridge comparison against the desktop engine produced identical samples
for all three factory patches over a one-second note/octave/release sequence,
using matching float32-quantized patch values. This proves host bridge parity,
not Blackfin numerical parity, timing, long-term stability or hardware sound.
The old Blackfin compiler does not support -fstack-usage; stack usage needs
alternative static analysis and runtime high-water measurement.

Next: link an isolated MYXA firmware target to expose runtime-library and loader
size costs, then separate control coefficient preparation from sample processing
with parity tests. Do not add stereo effects or SD/UI code until memory placement
and dry-engine timing strategy are established. Existing firmware build remains
unchanged; the adapter is not yet connected to ARM commands or physical audio.

## Isolated full-link probe result

`python3 development/myxa/link_probe.py` copies the pinned checkout into a unique
ignored build directory, adds a MYXA DSP module, and invokes the existing ARM
monosynth build with that DSP loader. The probe module ignores legacy ARM
parameter commands, runs Moog Res dry internally and writes zeros to both audio
outputs. It is a size/timing integration probe, NOT playable release firmware.
The original checkout and baseline artifacts are untouched. GNU99 is enabled
only for the new module. Upstream DSP -mfast-fp is retained; target numeric parity
still requires testing. Existing cycle instrumentation surrounds module_process
in dsp/src/kernel/main.c; no cycle values have been measured on hardware.

Observed result: DSP link succeeds; ARM link fails with OC_RAM overflow of 2464
bytes (133536 required vs 131072 available). Do not flash these outputs.

DSP linked GNU size totals: text/readonly 26208 bytes, data 1092 bytes, BSS 3272
bytes. These aggregate categories are not per-bank budgets. Loader length grows
from 19480 to 27380 bytes (+7900). ARM footprint grows by 16384 bytes: the larger
loader shifts the 16 KiB-aligned page table from 0x80014000 to 0x80018000, adding
alignment overhead as well as loader data. The limit was not artificially raised.

Next actions: inspect ARM section ordering/alignment to avoid wasted padding,
and replace the retained CPU monosynth/LEAF envelope app with the minimal MYXA
control app (DSP already owns envelopes). Measure each change with the linker
map. If sufficient durable headroom is unavailable, validate external-memory
placement/boot-loader staging before adding filesystem and menus. Merely recovering
2464 bytes would not establish enough room for the finished instrument.

The probe still uses per-sample transcendental setup and software floating point;
successful DSP linking is not evidence that 48 kHz deadlines can be met. Cache
control coefficients with desktop parity checks before hardware timing trials.

## ARM placement and minimal shell experiment

Two controlled builds now succeed without changing the physical memory limits:

| Build | ARM application region used | Reserved MMU table | Free application span |
|---|---:|---:|---:|
| Original layout + old app + MYXA DSP | 133536 (overflow) | included | -2464 |
| Compact layout + old app + MYXA DSP | 103968 | 16384 | 10720 |
| Compact layout + MYXA shell + MYXA DSP | 60616 | 16384 | 54072 |

The compact layout splits the original 128 KiB into 112 KiB application space
and a fixed 16 KiB MMU table at 0x8001c000. It retains the original vectors and
stack addresses. Linker assertions check table size and alignment. The table is
NOLOAD: startup's _config_cache_mmu explicitly writes every one of its 4096
entries before CP15TtbSet. This is source-verified, not hardware-verified.
The application region includes its original 2048-byte heap reservation; free
span is not additional heap unless explicitly allocated. No DDR assumption is
needed for these successful links.

arm_probe_app.c replaces CPU monosynth/LEAF with an initialization/heartbeat
shell. Kernel device services remain, but no instrument control/UI/storage
features have been implemented in that shell. Removed app code/data recover
43352 bytes beyond placement savings. This does not imply finished MYXA will
fit within that margin. Final GUI, queues, filesystem, MIDI/note state and stack
must be budgeted as implemented. Source libraries may still compile while dead
sections are discarded by the linker; compiler warnings alone do not imply
those libraries remain in the final binary.

verify_probe.py checks MMU location, heap/stack bounds, loader presence and absence
of the old LEAF/mempool symbols in the minimal build. Both probes passed. Baseline
cpu.bin and bfin.ldr hashes still match development/README.md exactly. DSP remains
the silent dry timing probe, and none of these artifacts is approved for flashing.
Next: eliminate per-sample parameter preparation in the sound core with host
parity tests, then add a bounded control protocol and MIDI/pad state to the ARM
shell. Hardware timing and boot tests remain outstanding.

## Prepared-coefficient optimization

The shared desktop C source now exposes synth_prepare and synth_process_prepared.
The firmware adapter prepares once at patch initialization and again on explicit
parameter updates; no parameter comparison scan or coefficient preparation occurs
inside its per-sample loop. The desktop synth_process API remains compatible and
prepares once per block. Cached data occupies 252 additional static DSP bytes.
Envelope coefficients, glide, smoothing, DC removal, tuning ratios, pink-noise
coefficients and keyboard tracking depth are cached. Pitch tracking, modulation,
filter cutoff and nonlinear processing remain dynamic. Parameter preparation
must run at a safe boundary; concurrent writes to the cache are not supported.
The probe setter only rejects bad indices/nonfinite values: production transport
must additionally enforce schema ranges/enums before calling it.

Validation: 38 desktop tests pass. All three dry factory bridge comparisons are
sample-exact on host. A frozen pre-change source in fixtures/modeld-before-cache.c
also matches sample-exactly through 100 update segments per patch, cycling all 47
voice parameters and varying notes, gates and triggers, including enabled pitch/
filter modulation. These are host comparisons, not target floating-point proof.

The optimized minimal ARM/DSP probe links and memory invariants pass. DSP totals:
26056 text/readonly, 1092 data, 3524 BSS bytes (vs 26208/1092/3272 before).
ARM application free span is 54224 bytes. Disassembly shows local LINK frame
sizes of 24 bytes in synth_prepare and 256 in synth_process_prepared; these exclude
saved registers, caller frames, library calls and interrupts and are NOT worst-case
stack bounds. The reserved DSP scratch stack remains 4096 bytes. Hardware stack
watermark and worst-case cycle measurements are still required.

No unmeasured speedup is claimed. This removes settings-dependent transcendental
work from each sample callback but leaves substantial software math in the audio
path. Next: bounded validated control transport and MIDI/pad state, followed by
hardware timing only with an approved recovery/install procedure.

## Note/control integration probe

control.h supplies a bounded 32-entry last-note stack keyed by MIDI channel or
pad source. Repeated note-on replaces the prior entry; note-off for an unknown
note is harmless. MIDI sustain, CC120/123, velocity-zero note-off and channel
changes are handled. Overflow clears old held/sustain state before accepting the
new note. Pads do not inherit MIDI sustain. MIDI channel setter accepts 0=Omni,
1–16=channel, but a settings UI and persistence remain to be connected.

ARM shell now registers serial MIDI note/CC callbacks and panel trigger callbacks.
Pad base is MIDI 36. Each pad remembers its pressed note; continuous pressure
updates do not retrigger. Accepts normal 0–15 indices and continuous 0x11-based
IDs based on upstream examples; physical order/event behavior still needs testing.
There is no octave-button mapping yet. Pending note updates are coalesced into
one current-state snapshot per app_run, with a retained trigger bit. A press and
release between dispatches may be inaudible; the released state takes precedence.

The snapshot fits one existing Freetribe module parameter message: command ID
0x7000, high-byte tag 0xa1, sequence byte, trigger/gate bits, 7-bit velocity/note.
This avoids torn pitch/gate updates. Sequence is diagnostic only for now; no
acknowledgement/retry/watchdog has been implemented. Existing SPI transport
reliability/queue failure behavior remains an integration gate before audible
hardware use. No full patch transaction protocol is implemented yet.

DSP accepts snapshot note state and voice parameter IDs 1–47 encoded as float32
bits within the existing int32 field. Generated min/max/discrete tables reject
invalid, fractional-enum and nonfinite values. Unsupported EQ/reverb/pan IDs are
rejected in this dry-only probe. The module processes note-driven audio internally
but always writes zero to physical left/right outputs. It currently scales the
diagnostic sample linearly by velocity; final gain law/legato/mod-wheel/pitch-bend
and note fallback retrigger policy must be matched to the desktop before release.
No claim of complete MIDI implementation is made.

Tests: bounded note-state C tests pass with ASan/UBSan (leak detection disabled
because this environment prevents LeakSanitizer under tracing; core allocates no
heap). Actual DSP decoder host tests verify note decoding, range/NaN/enum rejection
and silent outputs. Linked ARM/DSP control probe succeeds; initial measured ARM
free application span 51200 bytes. Physical callbacks, transport timing and note
response remain untested on hardware.

## Recovery and expression update

Performance snapshots now use three existing parameter messages: staged note
(0x7000), staged expression (0x7001), CRC32 commit (0x7002). Expression carries
14-bit bend, 7-bit modulation amount and the matching 8-bit sequence. CRC32 uses
explicit little-endian bytes; the DSP applies only complete matching snapshots.
Readback at 0x7003 acknowledges the entire note word. Duplicate acknowledgements
cannot retrigger notes; stale/out-of-order sequence advances are rejected while
the link is live. After timeout a new sequence may resynchronize. This assumes
ordered Freetribe transport and bounded in-flight traffic, not hostile replay
protection. A full patch transaction and parameter-change retransmission are
still separate future work.

ARM keeps one snapshot outstanding, retries every 50 ms, and clears held notes,
pad latches and pending triggers after five unanswered intervals. It then sends
a silent snapshot. Complete snapshots refresh every 200 ms. DSP clears the dry
voice and gain after 24000 samples (500 ms at 48 kHz) without a fresh accepted
snapshot. Retrying a timed-out snapshot does not revive its old note. This is a
sample-clock watchdog; an independent hardware watchdog would still be needed
for a stalled DSP/audio task. Physical outputs remain unconditionally zero.

Pitch bend uses ±2 semitones with signed MIDI center 8192 and applies to the active
MIDI channel; pads remain unbent. CC1 updates global modulation amount, consistent
with the desktop's unmapped Model D mod wheel. CC121 resets bend/sustain, CC120
panics, and CC123 clears channel-held notes/sustain to match the current desktop
implementation. MIDI channel selection clears MIDI-held notes and bend states.
The legato API controls note-on/fallback retriggering; default off. This is not yet
a patch-saved legato setting or on-device menu. Pedal/CC fallbacks do not retrigger,
matching desktop behavior. Velocity follows (velocity/127)^0.7 and 5 ms gain
smoothing with quantized factory patch gain; pitch and velocity persist during
release. Master gain is unity in the internal diagnostic path, unlike the desktop
UI's adjustable master. Audio-rate gain coefficient is cached, not recalculated
per sample. Modulation/envelopes/glide retain the original engine behavior.

Validation: actual ARM callback/retry code tested with deterministic clock/link
stubs; actual DSP decoder tested for partial/corrupt snapshots, duplicate retries,
timeout, restart, pitch/modulation and velocity gain target. Bounded note-state
sanitizer tests also pass. ARM/DSP link and memory invariants pass; ARM free
application span is now 42760 bytes. This remains a host-validated muted probe,
not evidence of physical MIDI latency, cable-loss handling, or DSP deadline safety.

## Patch loading, panel controls and first screen

The ARM shell now browses the three embedded factory patches with main encoder
ID 0x00 and loads using Menu/Enter (0x09). Exit (0x0d) cancels browsing/confirmation.
An edited patch requires a second Enter to confirm discard; no saving is implied.
These IDs are source-confirmed in upstream zontar/monosynth examples, not yet
physically verified. A screen shows active patch name, edited marker, browse name
or transfer state, and the most recently touched parameter/value. Rendering is
capped at 10 Hz and uses the pinned uGUI 6x8 font on a 128x64 surface. Its exact
renderer was exercised on host and the generated pixel image inspected.

Cutoff encoder 0x02 changes cutoff logarithmically. Knob 0x03 controls resonance;
0x04 controls filter-envelope amount. Absolute knobs require pickup near/crossing
the recalled value; cutoff is relative and needs no pickup. Sample Edit's knob
ID has not been verified, so mixer drive temporarily uses Shift (0x0a) + EG Int.
Switching Shift resets pickup for the shared knob. The normalized drive-pot API
is available for the eventual dedicated knob mapping. No guessed hardware ID is
installed. Edits are coalesced, validated on DSP, read back and retried with bounds.
They set the local edited indicator; this is not SD persistence.

Patch transfer uses BEGIN (0x7100), 54 indexed float32 DATA words (0x7200+index),
COMMIT (0x7101) and ACK readback (0x7102). BEGIN contains schema tag 0xb1, engine
ID and a serial. Each word is acknowledged before the next is sent, with bounded
50 ms retries. COMMIT checks all fields, ranges/enums and a CRC32-derived ordered
fold across header and values. No partial patch reaches active parameters. Apply
occurs in the DSP service/main loop between audio calls, prepares coefficients
once and resets notes/voice/gain. A repeated COMMIT after a lost ACK is idempotent.
A valid BEGIN silences the internal voice while staging; invalid/incomplete data
leave the prior parameter set intact. Failed/ambiguous transfers block new note
input and show Load failed; Enter restarts a complete transfer. Performance note
traffic is paused during transfer; the next accepted snapshot restarts its state.

All 54 settings are retained, including effects and pan, but this remains a dry
probe. In particular UK Res Bass and BOSS 03 contain active EQ/reverb settings:
their complete desktop sound is NOT reproduced yet. The screen labels FX pending
and MUTED. No analog or digital physical output has been enabled.

Tests exercise all three complete transfers, incomplete/corrupt commits, duplicate
commit ACK recovery, edit confirmation/cancel, pickup crossing and relative cutoff.
Existing control/recovery tests still pass. Both firmware targets link; memory
invariant checks pass with 11632 bytes of free ARM application span after the
screen and patch workflow. Budget must be revisited before filesystem additions.
Screen/UI size is substantial; no external RAM capacity is assumed. No flashing.

## Storage memory checkpoint

See STORAGE_BUDGET.md for measured attribution and reproducible configurations.
Removed generic printf formatting and the unused window update from the text-only
screen: 12184 ARM bytes recovered with representative pixel-identical rendering.
Normal probe free span: 23816 bytes. A separately enabled official FatFs R0.16
footprint probe, including small browser/recovery buffers, links with 10752 bytes
free. It has NOT READY disk stubs, not an SD driver. External DDR is not yet
justified merely by the old UI footprint; real driver/save logic size and an
explicit headroom gate will decide. No storage or hardware writes occurred.

## SD interface source audit

Decoded existing PINMUX10=0x88222222 and verified MMCSD0 CLK/CMD/DAT0..3 against
local register-header definitions; startup enables the same controller. No
complete card driver exists. Adjacent GPIO4_0/1 are not sufficient evidence for
card-detect/write-protect. Source hash report: build/sd-interface.json, generated
by audit_sd_interface.py. See SD_INTERFACE.md for clock/power/wiring unknowns and
the bounded native read-only probe plan. No guessed MMIO implementation or driver
size claim was introduced; no card hardware was accessed.

## Patch record/recovery implementation

PATCH_FILES.md specifies the implemented 392-byte versioned record and two-slot
recovery state machine. Tests pass for every byte-boundary interrupted write,
corrupt/truncated records, backend failures, conflict/version handling and C/Python
factory-patch byte parity. No FAT/SD driver or Save UI is connected. Optional
filesystem + record footprint probe links with 6216 free ARM bytes and 928-byte
MyxaStore state, below the intended 8 KiB margin. Hardware driver and filesystem
power-loss durability remain unverified; no automatic storage enablement follows.

## Bass-first dry stereo diagnostic path

Sampling/sequencing remain deferred per user direction. output.h now provides
one centered mono dry source into equal-power stereo pan, then smoothed per-channel
master gains, ±0.98 clipping and signed Q1.31 conversion. Pan uses cosine/sine
only on changes; sample processing uses cached targets. Startup digital master
is -18 dB. Center is about -3 dB per channel under the standard equal-power law;
this is an explicit per-channel level change from the earlier duplicated mono
output. It is not stereo reverb or a stereo oscillator engine.

The actual module invokes this stage and exposes Q1.31 L/R diagnostics, but writes
zero unconditionally to the physical Freetribe output slots. No compile option
silently enables physical output. Nonfinite audio clears diagnostic output and
resets the voice. Software master command 0x7004 accepts 0..1 with readback and is
global, not patch saved; no physical master-volume event is assumed. The physical
Volume control path still needs analog/codec/panel verification.

Validated live Pan and patch output gain now apply and read back. Patch commit
recalls Pan and gain. Level's confirmed event ID 0x00 controls saved patch dB;
Shift + Level temporarily controls Pan, both with per-target pickup. Dedicated
Pan event ID remains unverified. Existing cutoff/resonance/EG and temporary drive
mappings are unchanged. Actual panel behavior still needs a hardware session.

Host sanitizer tests cover pan energy/endpoints, master ramp/mute, clipping,
nonfinite input and bounded Q1.31 conversion. Actual module tests verify notes
reach both diagnostic channels, left pan silences right, software volume silences
both, and physical output remains zero. ARM callback tests include Level/Pan
pickup. All 38 desktop tests and frozen dry-core parity comparisons pass.

Both ARM/DSP probes link. Combined filesystem+record budget variant leaves 3704
bytes ARM free, worsening the already insufficient storage margin. It still has
no real SD driver. The bass-only build omits those optional storage probes and
remains the playable-prototype path. No sampling/sequencing code, card access,
firmware installation or physical audio enablement was introduced.

## Bass controls and device-test preparation

PANEL_MAP.md records the expanded source-backed mappings and temporary shortcuts.
Host tests pass for amp/filter timing pickup, glide, LFO/depth, oscillator shape,
MIDI-channel changes, octave clamps and release of notes held across octave shifts.
Shift+Play and accepted MIDI CC120 now send a checksummed hard-panic snapshot;
DSP resets voice/gain rather than leaving a release tail. Normal release is
unchanged. The source-backed master/pan/edit/button mapping gaps remain explicit.
FIRST_DEVICE_TEST.md records the debugger-based loading path in pinned Freetribe
and the inspected upstream recovery guide; no SYSTEM.VSB install path is assumed.
ARM polls existing DSP profiling and retains sampled utilization counters for a
future authorized device test, not a claimed worst-case measurement. Host tests
verify the counter arithmetic. All 38 desktop tests pass; isolated build succeeds.
No hardware load, flash operation or audio output enablement occurred.
