# SD-card interface audit and read-only bring-up plan

Status: source configuration decoded; hardware adapter not enabled. No device,
card or memory-mapped register was accessed during this audit.

## Established by local pinned source

`python3 development/myxa/audit_sd_interface.py` checks the actual configuration
against the supplied register-header definitions and records source SHA-256s in
build/sd-interface.json. It fails on a conflicting mux/controller definition.

- per_pinmux.c writes PINMUX10 = 0x88222222.
- The low six mux fields select MMCSD0_CLK, CMD and DAT0..3 respectively.
- The high two select GPIO4_1 and GPIO4_0. Their location beside the SD signals
  does NOT establish card-detect or write-protect function/polarity.
- startup.c enables PSC0's HW_PSC_MMCSD0 module.
- soc_AM1808.h declares MMCSD0 base 0x01c40000. The project uses AM1808-named
  register headers on AM1802; confirm any accessed feature against AM1802 docs.
- The pinned docs list an SD driver as planned. There is no complete driver or
  disk I/O adapter in this source tree. Register headers are not a working driver.

The source therefore supports native MMC/SD0 as the intended interface rather
than SPI. It does not by itself prove the slot's physical wiring on every board.
The user's exterior photos establish the unit type but cannot establish PCB nets.

## External primary references

- TI AM1802 product/documentation: https://www.ti.com/product/AM1802
- TI AM1802 System Reference Guide SPRUGX5A:
  https://www.ti.com/lit/ug/sprugx5a/sprugx5a.pdf
- SD Association physical-layer specification archive:
  https://www.sdcard.org/downloads/pls/archives/
- SD Association Physical Layer Simplified Specification v7.10:
  https://www.sdcard.org/cms/wp-content/themes/sdcard-org/dl.php?f=Part1_Physical_Layer_Simplified_Specification_Ver7.10.pdf

TI search/index evidence agrees with the supplied mux names and register base;
that is processor documentation, not an Electribe board schematic. A public
Electribe teardown was also inspected, but supplies no sufficient slot-net,
card-detect, power-control or clock evidence for this implementation. No electrical
assignment was taken from comments/forum speculation.

## Still required before a hardware adapter

1. Board revision and an authoritative slot-net map, or verified board tracing/
   documented known-working initialization for that revision. Never drive an
   unidentified GPIO as card power or chip select.
2. Identify card presence/polarity, or explicitly validate a command-timeout
   detection policy that does not depend on a guessed switch pin. Write protect
   is unnecessary for a read-only test but remains a future saving requirement.
3. Verify slot voltage/power source, power sequencing and stabilization. Do not
   enable voltage switching/UHS modes or change an unknown rail.
4. Trace MMC peripheral clock source/rate from the configured PLL/dividers and
   controller documentation. ARM's 300 MHz clock is not an MMC clock measurement.
   Establish an identification clock <=400 kHz with the actual divider equation.
5. Check AM1802 response ordering, read-to-clear status bits, FIFO access/packing,
   transfer-length controls, controller reset, timeout and CRC behavior, plus
   relevant silicon errata. No register code should be extrapolated from SPI.

## Read-only probe specification

Once those gates are resolved, add a separate opt-in driver target. Normal MYXA
must not initialize card hardware merely because storage code links.

Use native 1-bit SD at identification speed initially, one 512-byte buffer and
PIO, with no DMA/high-speed/4-bit transition until a basic read is verified.
The first limited target may explicitly support SD v2 high-capacity cards only;
report unsupported cards instead of guessing addressing. This is a bring-up
restriction, not the planned final compatibility promise.

Bounded states: controller setup → initial clocks → CMD0 → CMD8/check echo and
voltage → CMD55/ACMD41 bounded readiness polling → CMD2/CID → CMD3/RCA →
CMD9/CSD and capacity/addressing validation → CMD7/select and ready/busy check →
CMD17/single sector → verify transfer count, status and CRC → report.
Controller implementation must implement each command's native response class
and status validation. Legacy SDSC addressing/block-size support is a separate
path; never issue CMD17 with an assumed SDHC sector address for an unknown card.

Only expose single-sector reads in this test. CMD24/25 writes, erase, formatting,
partition changes, filesystem mounting in write mode and raw unrestricted command
entry points are excluded. Initialization commands change card protocol state,
but must not modify stored data. "Read-only" refers to card contents, not zero
controller-register writes. A failed command aborts with the exact stage/status.

Each task step must have a fixed work budget and yield to MIDI/control refresh.
Use a monotonic wrap-safe timer, bounded command and total-init deadlines, bounded
ACMD41 retries and bounded FIFO word handling. On failure/removal, stop reads,
invalidate the sector and report failure; do not retain a stale success flag.
Timeouts must not starve the DSP snapshot heartbeat. Actual deadline values need
validation against the card specification and hardware behavior.

## Validation and memory gate

Host test with fake controller registers: response classes, CRC failures, response
and data timeout, stuck FIFO, removal, truncated sector, SDHC vs SDSC addressing,
capacity bounds and timer wrap. Record a trace proving no content-write/erase
commands. Cross-compile and link against the full MYXA + FatFs budget build,
not only an isolated object; retain an explicit memory margin.

Then, after separate hardware authorization/recovery setup, read a known test
card sector and compare it byte-for-byte with a host dump. Repeat absent-card,
reinsertion and corrupt-card tests. Only after stable reads should read-only
filesystem mounting and patch listing be connected. Save/write work remains a
separate tested stage.

## Outcome

No evidence currently establishes every required hardware detail. Therefore this
pass completes the source audit and probe specification without fabricating a
working SD driver or a driver memory measurement. Existing 10752-byte filesystem
budget headroom excludes this driver and save logic. The next hardware-specific
input is a verified slot/clock/detect/power mapping; host-testable patch record
serialization can proceed independently while that is resolved.
