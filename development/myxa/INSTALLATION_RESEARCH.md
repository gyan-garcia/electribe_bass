# Closed-case installation feasibility investigation

Status: research/static analysis only. No update image generated, no updater or
MIDI loader executed, no hardware accessed. This corrects the earlier assumption
that a debugger is the only documented way to start Freetribe.

## Findings

Two distinct goals must be separated:

1. Direct, permanent MYXA installation as a SYSTEM.VSB: not established for our
   on-chip-linked build. Existing patched Korg firmware does not prove that an
   arbitrary Freetribe image with a header will boot or remain recoverable.
2. Closed-case test loading: upstream documents installing Hacktribe through the
   normal SD updater, then executing Freetribe from RAM using TRS MIDI SysEx.
   This is a credible existing route to investigate for MYXA before JTAG.

## Primary evidence inspected

- Korg sampler updater page:
  https://www.korg.com/us/support/download/software/0/368/2579/
  Factory source is sampler v2.02; Korg specifies intermediate v1.16 for devices
  on v1.15 or earlier. Installed version must be identified before any procedure.
- Hacktribe How-To:
  https://github.com/bangcorrupt/hacktribe/wiki/How-To
  Documents installing a patched SYSTEM.VSB through the normal SD update process.
- Maintainer's January 2025 announcement and replies:
  https://github.com/bangcorrupt/hacktribe/discussions/351
  Confirms Freetribe SysEx loader, external TRS MIDI only, and MIDI OUT required
  for acknowledgements. This source is newer than our pinned debugger guide.
- Upstream loader:
  https://github.com/bangcorrupt/hacktribe/blob/main/scripts/execute_freetribe.py
- Recovery/boot description:
  https://github.com/bangcorrupt/hacktribe/wiki/Debrick

Public Hacktribe code cloned only for inspection into ignored
build/research-hacktribe at revision 94c8e608e6918c432cac90b2c19042b2d65ae626.
No proprietary factory firmware was downloaded or patched in this investigation.
Third-party scripts were read, not imported/executed against MIDI hardware.

## SD update format and boot mismatch

The inspected e2_add_header.py describes a 256-byte Korg header with device/model,
version and source/destination lengths (default body 0x200000 bytes). e2-header.py
changes sampler/synth model fields. e2-firmware-patch.py requires a known factory
v2.02 SHA-256, applies the binary patch, and verifies the expected resulting hash.
A file that merely parses like a header is not a verified updater payload.
The supplied header script is a format clue, not a turnkey Freetribe installer.

Upstream recovery documentation says the ROM loads an SBL into on-chip RAM;
that SBL loads the main factory application at 0xc0000000 in external RAM.
Our ARM linker/init code starts at 0x80000000. Renaming cpu.bin or adding a
header leaves that execution-address mismatch unresolved. A permanent custom
update would require a verified compatible entry/loader or external-RAM layout,
length/validation handling, boot-state compatibility and a recovery path.
Keeping the original SBL intact is not itself proof of SD-only recovery: if
MYXA replaces the application containing the update UI, that UI is no longer
available. A JTAG recovery could still become necessary after a failed flash.

This investigation did not independently reverse engineer the factory updater's
complete validation rules/signature/checksum behavior. Hacktribe's working patch
route proves accepted modifications in a known image, not arbitrary payloads.

## Existing closed-case development route

Conceptual flow, not installation instructions:

factory sampler → install verified Hacktribe using stock SD updater → start the
upstream Freetribe RAM loader over bidirectional external MIDI → run MYXA probe.

The SD update would be a real persistent Hacktribe flash operation, requiring
separate user authorization. Subsequent app transfers are intended as RAM loads;
the uploaded application can still write hardware, so every reachable init path
must be reviewed. A normal power cycle should reload the flash-installed firmware
if that firmware/boot chain remains intact; this is an architectural expectation,
not a recovery guarantee for this untested MYXA combination.

A computer MIDI interface must connect to both Electribe MIDI IN and OUT with
correct TRS adapters. A computer-side USB-MIDI interface can be used; the
Electribe's own USB connection is not the documented loader transport. Neither
the Raspberry Pi nor internal wiring is required by this route. The MPK Mini
alone is not established as a bidirectional computer-to-Electribe MIDI interface.

## Client static audit

execute_freetribe.py sends the loader pivot command 0x58, waits for a magic-word
reply, pads the app to 256-byte chunks, calls load_cpu_ram for each acknowledged
chunk, then executes address 0x80000000. e2sysex.py implements RAM load/execute
as SysEx messages and waits for responses. Current inspected source permits
separate input/output port arguments. It also hardcodes global channel 0/model
0x24 after device discovery, which must be handled explicitly in a reviewed tool.

Missing checks in the upstream convenience script include a target image-size
bound, comprehensive reply-length/identity validation and bounded response waits.
It can hang waiting for a response or index a short reply. We should prepare a
bounded local wrapper/simulator before trying it on a live device. The loader
implementation is distributed in a firmware binary patch; the inspected public
Python files do not establish its exact resident memory range or maximum upload
size. Do not infer these from the bootloader-backup script's RAM dump length.

## MYXA static compatibility observations

The tested bass-only build's cpu.bin is 79492 bytes; the entry instructions and
linked address start at 0x80000000, matching the upstream client's execution
address. The client would pad this to 311 blocks / 79616 bytes. The embedded DSP
loader is included in the ARM binary already. These are format/address matches,
not execution proof. Build size will change with subsequent code.

Our revised MMU table occupies 0x8001c000–0x8001ffff, outside uploaded file bytes
and initialized at runtime. It is essential to establish the RAM loader's resident
code, stack, vectors, interrupt/cache/MMU state and handoff behavior before claiming
this layout is compatible. Check whether a power cycle can restore Hacktribe
without invoking any flash write from the test application. The initialized BSS,
stack, PLL/DDR and peripheral resets in MYXA must be audited for the inherited
state from Hacktribe rather than a debugger/cold boot assumption.

## Recommendation

Prefer the existing Hacktribe + TRS MIDI RAM-load route for a closed-case MYXA
prototype. Do not package our current image as SYSTEM.VSB. Next independent work:
review a bounded loader client in simulation, pin the exact compatible Hacktribe
patch/hash, establish upload residency/handoff details, identify installed firmware
and the user's bidirectional MIDI interface, and plan backups/recovery. Only then
present a concrete authorized installation/test procedure. No installation was
performed by this research.

## Follow-up: demonstrated route versus MYXA readiness

The stronger evidence is the actual completion report in discussion #351:
https://github.com/bangcorrupt/hacktribe/discussions/351
On January 28, 2025 the user enorrmann reports the monosynth running after the
loader/MIDI troubleshooting. This is first-person evidence of an executed
Freetribe example, rather than only an announced feature. It is not an independent
MYXA test, nor a hardware-revision compatibility matrix. The same discussion
contains failed MIDI discovery attempts, demonstrating that interface/adapter/
port configuration can block the route.

The maintainer's March 8, 2025 progress announcement independently describes
Hacktribe loading Freetribe applications over serial MIDI:
https://github.com/bangcorrupt/hacktribe/discussions/359

The source pinned for MYXA (5fe6658..., main commit dated 2025-11-08) is later
than the January user report. The report therefore does not prove the exact
pinned source plus our modifications. The current upstream bootloader branch
f812bf81250351ae07ad91fdd18111c64f99c41b (2025-06-14) was also inspected in an
ignored clone. It is a broader development branch, not a fully established source
match to the loader embedded in Hacktribe's January binary patch. Its name alone
must not be used to derive the active loader's placement or limits.

No factory firmware was downloaded. Static inspection of the BSDIFF patch's
inserted-byte stream confirms the output-image size 2097408 bytes (256-byte
header + 2 MiB body) and inserted magic/0x80000000 literals. Some nearby inserted
code references 0xffffxxxx addresses. These partial literal/code observations do
NOT establish the full receiver map, exact size bound, cache shutdown or handoff.
Only an ignored inserted fragment was extracted for inspection; no patched or
flashable firmware image was produced and no original firmware bytes were used.

## Offline execution of the real upstream Python client

A fake-only harness is provided as test_upstream_ram_loader.py. It substitutes
mido and E2Sysex before executing the inspected upstream client; no actual MIDI
backend is imported. It uses the upstream 7-bit byte codec and models the ACKs
expected by that client. This tests client control flow and data handling only;
the mock is not an ARM/loader emulator or an independent protocol conformance test.

```
python3 development/myxa/test_upstream_ram_loader.py PATH_TO_CPU_BIN
```

Tested binary SHA-256:
67abec2d094e6575c100e3624267b0716d835e44bd620a34ae1614e9f50bac85

Result: all 79492 input bytes are delivered exactly, padded to 79616 bytes in
311 blocks, followed by execution request 0x80000000. Bad magic prevents upload;
a bad first or final block ACK prevents execution. No firmware was sent anywhere.
The command fails if expected data or control flow differs. Report is saved to
ignored build/ram-loader-client-test.json. The harness currently depends on the
inspected upstream source clone in build/research-hacktribe; specify --repo for
another clone and review its revision before interpreting results.

At 31250-bit/s serial MIDI with 10 wire bits/byte, outgoing chunk frames alone
have a theoretical minimum of about 29.9 seconds, excluding replies, setup,
processing and retries. This is not a measured device upload time. Original
convenience client does not bound its waits or enforce an upload size limit;
those gaps must be addressed before using a MYXA-specific live loader.

### Evidence-based verdict

- Stock SD update of Hacktribe: established upstream procedure; still a flash
  operation that must be explicitly authorized and use the correct image/hash.
- Hacktribe → serial MIDI → Freetribe RAM execution: implemented upstream and
  supported by a first-person monosynth success report; not merely theoretical.
- MYXA client-side binary handling/address: checked locally and compatible with
  the inspected client flow, subject to real loader memory/handoff validation.
- MYXA boot, panel behavior and real-time DSP on the user's sampler: untested.
- Permanent direct MYXA SYSTEM.VSB installation: not established or recommended.

The next staged investigation should establish installed firmware and the
bidirectional MIDI interface, prepare verified backups/install/revert artifacts
without applying them, and add bounded protocol validation. A small muted
Freetribe reference test should precede MYXA audio-engine timing tests. Initial
Hacktribe flashing remains a risk boundary; a successful RAM load does not prove
performance or guarantee recovery from a bad flash. The documented closed-case
route gives a credible test path without claiming those remaining results.
