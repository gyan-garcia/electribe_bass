# MYXA ARM/SD feasibility checkpoint

## Measured results

All builds use the same 128 KiB physical on-chip region split into 112 KiB app
space and a reserved 16 KiB MMU table. The 8 KiB vectors/stack region is separate.
Free span is linker headroom, not allocated heap; the existing 2 KiB heap is
already reserved. These are silent probes, not hardware-tested firmware.

| Configuration | Application used | Free application span |
|---|---:|---:|
| Expression/recovery control probe, before patch UI | 71928 | 42760 |
| Patch workflow + original uGUI screen/formatting | 103056 | 11632 |
| Same workflow, lightweight text formatting/no window update | 90872 | 23816 |
| Optimized workflow + measured FatFs/storage budget probe | 103936 | 10752 |

The initial patch workflow/screen increment was 31128 bytes, including larger
DSP loader and application code. This is not all framebuffer RAM. The two
formatting/rendering changes recover 12184 bytes. Baseline symbol inspection
found vfprintf (3776 bytes), its dtoa engine (1744 bytes) plus formatting helpers,
and unneeded uGUI window/object drawing pulled in by UG_Update. Only four text
lines are drawn: UG_PutString performs drawing immediately. Removing UG_Update
removes unused window-manager dependencies. No framebuffer or transport buffers
were reduced. The 6x8 font and text rendering remain unchanged.

The new fixed-point formatter is tested against snprintf across signs, boundary
values and every destination size 1–22, with guard bytes and ASan/UBSan. Screen
PBM output before/after is byte-identical for the representative patch screen;
real control tests also pass. Future window widgets would require deliberately
restoring their update path. This optimization is specific to the current UI.

## Filesystem measurement, not a working SD driver

Official FatFs R0.16 source:
https://elm-chan.org/fsw/ff/arc/ff16.zip

Archive SHA-256:
99f7dc1f7e095356e4a9e3dbe29959090d8b948afe2bbc5441e52fdf4b85449e

This digest records the retrieved archive; it is not an independent publisher
signature. Source notices are retained in isolated builds. Licensing and
configuration references:
- https://elm-chan.org/fsw/ff/doc/appnote.html
- https://elm-chan.org/fsw/ff/doc/config.html

Configuration: read/write FAT, one volume, 512-byte sectors, tiny/shared sector
buffer, codepage 437, no long filenames, exFAT, formatting, string/printf APIs,
Unicode tables or RTC dependency. No filesystem locking/reentrancy: one ARM
storage worker must own all accesses. Global application patch names can remain
inside patch records, while card filenames use short IDs such as P0000001.MYX.
This does not limit the patch's displayed name to the filesystem's 8.3 filename.
Do not offer card formatting or promise arbitrary card/filesystem compatibility.

The retained API set is mount, open, close, read, write, sync, opendir, readdir,
closedir, rename, unlink, mkdir. storage_budget.c anchors these functions at link
time without invoking them, plus actual FatFs structures and proposed buffers:

| Data object | Measured ARM bytes |
|---|---:|
| FATFS (includes shared sector) | 560 |
| FIL (one open file) | 40 |
| DIR | 44 |
| FILINFO | 24 |
| Recovery/verification sector | 512 |
| Paged browser cache | 1024 |

The complete incremental linked cost is 13064 bytes, including code, objects,
alignment and artificial retention pointers. It excludes real SD/MMC driver,
save state machine, record serialization, naming UI, error messages and any
additional DMA buffers. Disk stubs return NOT READY and never access hardware.
No saved patch, filesystem image or card was written in this measurement.

Freetribe includes controller register headers but no complete SD block driver
in the pinned checkout. The driver interface and card wiring/pinmux must be
verified before selecting SPI vs native SD/MMC; do not infer wiring from the
presence of a controller header.

## Decision and gates

A constrained SD prototype is now plausible in on-chip RAM. Do not move to DDR
merely to solve the former UI formatting overhead. But the remaining 10752 bytes
are NOT proof that production storage fits or is reliable.

Next: verify the physical card interface against available board evidence, build
a bounded driver/block-I/O probe, and measure its linked increment. Keep a
provisional 8 KiB application margin for growth/error handling; with the current
filesystem probe that leaves only 2560 bytes before this margin is crossed.
This margin is a planning target, not hardware stack proof. If driver + save
logic exceed it, first measure further code-size savings; then validate DDR or
loader staging as a distinct hardware task. Do not silently shrink stacks,
transport queues or safety checks to make a link pass.

Storage operations must yield to control traffic and have bounded timeouts; an
unbounded blocking SD write can starve the 200 ms control refresh and trigger
the DSP's 500 ms watchdog. Test this before claiming audio-safe saving. Patch
write/flush/readback, backup recovery, card removal and power loss tests remain
required. FAT rename alone is not a power-loss transaction. SD support and
external-memory support are both still unimplemented.

## Reproduction

Download the archive above to development/myxa/build/ff16.zip; the build checks
its SHA-256 before extracting the four required source files. Then run:

```
python3 development/myxa/link_probe.py --compact-layout --minimal-arm
python3 development/myxa/link_probe.py --compact-layout --minimal-arm --storage-budget
python3 development/myxa/verify_probe.py PRINTED_BUILD_PATH --minimal
```

The storage flag is a nonfunctional footprint experiment. It is not enabled in
normal MYXA builds. Logs/configuration and original third-party notices remain
inside each isolated build directory. No files in development/freetribe change.
