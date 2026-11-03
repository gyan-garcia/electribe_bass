# First MYXA device test preparation

Status: preparation only. No hardware access, RAM loading or flash writes executed.
Current artifact is an isolated ARM/DSP dry, muted probe, not SYSTEM.VSB.

## Established loading path and outstanding inputs

The pinned Freetribe debugging.md describes an ARM debugger (JLink or Raspberry
Pi/OpenOCD) and loading the ARM ELF. That ARM application uploads the DSP loader
via SPI; a separate DSP debugger is not mandatory to execute it. Its .gdbinit
contains automatic target connection, ELF loading and continuation commands.
Do not start it inadvertently during source inspection. No debugger connection
has been tested for the user's unit and no flash-compatible MYXA update package
has been built or validated.

Primary recovery reference inspected:
https://github.com/bangcorrupt/hacktribe/wiki/Debrick

This distinguishes factory SYSTEM.VSB updates from RAM/debugger loading, and
describes an SBL loading the factory application into external RAM. This is
useful recovery evidence, not proof that our on-chip-linked image can be wrapped
in a stock update header or that the same process works on this particular unit.
No recovery commands are automated here.

Before a device session, establish exact hardware model/revision, installed
firmware, accessible/working debugger and connection/power arrangements, backups
of user patterns/samples/global settings, and a verified restoration route for the
unit's factory firmware. Internal sample/pattern flash and bootloader regions
must not be treated as spare storage or erased by a test loader. A RAM-loaded
program can still write peripherals/flash, so RAM loading alone is not a safety
proof. Review all reachable initialization paths before approval.

## Muted bring-up sequence

After explicit authorization for the exact hardware operation:

1. Verify the identified debugger/target and capture baseline boot behavior.
2. Use a reviewed RAM-only probe-loading procedure; leave physical audio muted.
   Do not run a factory updater or flash commands as part of this stage.
3. Confirm ARM reaches app_init/app_run, DSP reports readiness and patch ACKs
   arrive. Inspect decoder rejection/timeout counters and check normal controls.
4. Observe panel event IDs before replacing temporary mappings. Confirm pad order,
   press/release/velocity, encoder direction, master Volume path, dedicated Pan,
   Sample Edit, Stop and octave buttons. Envelope changes should agree with the displayed pickup/target labels, with
   no abrupt parameter jumps.
5. Confirm serial MIDI channel filtering, sustained notes, octave shifts while
   held, pitch bend, mod wheel, hard panic, disconnect/retry and rapid patch load.
6. Observe stack high-water and DSP processing deadlines under maximum resonance,
   enabled modulation, repeated notes and continuous panel/MIDI traffic. Do not
   infer target timing from host benchmarks or successful cross-compilation.
7. Only after measured timing/output routing checks, prepare a separate reviewed
   audible build with conservative startup level and explicit output enablement.
   Current source always writes physical left/right zero; no runtime control can
   unmute it. Audible testing is not performed by these instructions.

## Available timing observations

The ARM shell polls the existing DSP profile service every 100 ms while not
loading a patch. In the debugger inspect:

- myxa_profile_period: latest SPORT frame period in DSP cycles.
- myxa_profile_cycles: latest reported module processing cycles.
- myxa_profile_peak_permille: peak utilization among received reports.
- myxa_profile_reports and myxa_profile_observed_overruns.

The source profile service reports g_module_cycles and sport0_period. Polling
samples observations and can miss overruns. These counters do not establish
worst-case execution time; a DSP-side per-frame accumulator and stack watermark
must be used for the final deadline gate. Existing runtime DSP floating-point and
library behavior is also not proved by host sample parity.

## Local evidence so far

Actual ARM callback tests cover all current knob/encoder shortcuts, pickup
switching, MIDI channel, held-pad octave changes, panic and simulated timing/link
recovery. Actual DSP command tests cover complete patch/note adoption and hard
panic reset; stereo output tests cover pan/master/protection with hardware slots
still zero. All 38 desktop tests pass and core dry comparisons remain exact on
host. The ARM/DSP probe links; artifacts live only in ignored build directories.

Outstanding product work includes five-second MYXA animation, remaining panel
IDs/LED feedback, EQ/stereo reverb on DSP, patch-save UI/backend and SD hardware.
Sampling/sequencing are deferred. Nothing in this document declares the device
ready to install or claims the product is finished.
