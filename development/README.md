# Electribe bass firmware development

Local build only. No scripts here upload firmware or access hardware.

## Baseline and requirements

Freetribe: https://github.com/bangcorrupt/freetribe

Pinned source: `5fe6658a6038fea70c8e802ae61d8a67bf22ff3a`.
Documentation: https://bangcorrupt.github.io/freetribe-docs/
Pinned docs: `d66cf387320ceea9b1b2485839137fcb369b0fd2`.
Recursive submodule revisions are pinned by the source tree.

Host: Ubuntu 24.04, x86_64; bash, make, git, xxd, tar, bzip2, dpkg-deb.
ARM: TI AM1802 ARM926EJ-S, `arm-none-eabi` GCC 13.2.1, binutils,
newlib and picolibc. Ubuntu packages are extracted locally, without system installation.
Blackfin: ADSP-BF523; upstream uses `-mcpu=bf527` plus `__ADSPBF523__`.
Keep this upstream combination until hardware differences are reviewed.
ADI 2014R1-RC2 ELF toolchain supplies GCC, bfin-elf-ldr, libbfdsp and libbffastfp.

The original Dockerfile uses Debian Bookworm with unpinned packages, old paths,
and a fragile SourceForge filename. This local environment avoids Docker.
The small CPU Makefile patch exposes picolibc paths for local extraction.

## Build

For setup on another Ubuntu 24.04 x86_64 host, retain these scripts, the patch
and checksum file; run `bash download.sh`, `bash bootstrap.sh`, then
`bash build.sh`. Downloads are checked against the recorded SHA-256 manifest.
The Blackfin checksum records the downloaded artifact; it is not an independent
publisher signature. The cached archives allow offline toolchain setup.

Run `bash build.sh` from this directory. It cleans both targets and selects
`APP=monosynth MODULE=monosynth`; the upstream default `APP=demo` does not exist.
DSP builds first, then its SPI loader is embedded into the ARM image.
Outputs: `freetribe/dsp/build/bfin.elf`, `bfin.ldr`, and
`freetribe/cpu/build/cpu.elf`, `cpu.bin`. These are development artifacts,
not a validated device update package.

Run `bash verify.sh` to compare binaries and debug ELFs from two clean builds
in the same directory. Logs go to `build-first.log` and `build-second.log`.
This verifies repeatability on this host/path, not across different host systems.

## Verified baseline (2026-11-01)

Two clean builds succeeded on this Ubuntu host, with identical SHA-256 hashes
for both ELFs and both binary outputs (see `build-first.sha256`).

ARM binary SHA-256:
`82d6f8551317fa80274867102e184f51a6a95d71d5ae2dd9237e882557bb80f5`

Blackfin loader SHA-256:
`39f37d8781637bb23d81f09e0801f3680b5507e356289490ce8c6fd5d675c5e1`

ARM linker reports 117152 bytes / 128 KiB (89.38%) for OC_RAM. The 8 KiB
ARM_RAM region is fully reserved for vectors/stack; this does not measure
runtime stack consumption. Upstream warnings remain, including stack usage,
unused values, string operations, and analyzer reports of recursion and null
dereferences in vendored LEAF. These require review before hardware use;
build success alone does not resolve them. No runtime or hardware validation was done.

## Bass direction

Start with the existing CPU app `cpu/src/apps/monosynth` and DSP module
`dsp/src/modules/monosynth`. ARM handles panel/MIDI/display; DSP receives
parameters over SPI and runs `module_process` per sample at 48 kHz.
The existing module uses Aleph_MonoVoice and fixed-point DSP.

Next milestones: audit note priority, legato, glide and MIDI parameter handling;
define a shared parameter schema; add a bass oscillator/sub oscillator and
filter saturation in small stages; build offline audio tests for tuning,
aliasing, clipping and envelope behavior; measure DSP cost before increasing
oscillator count or adding oversampling. Aim for Mariana-inspired bass character,
not feature parity or reproduction of proprietary code/assets.

Build verification cannot establish audio quality or real-time performance.
Hardware model/revision and a recovery/debug strategy remain future inputs.

## Resource constraints observed in source

The current ARM linker script places code/data in 128 KiB on-chip RAM, with
8 KiB ARM RAM used for vectors and stack; it does not presently place this
application in external DDR. DSP placement is 64 KiB L1 code plus a 16 KiB
code/cache region, two 32 KiB data banks and 4 KiB scratch. L2 is declared
with zero length. These are current linker constraints, not a complete hardware
memory inventory. Check linker maps before expanding the synth.

The existing CPU monosynth runs envelopes/LFOs and converts floating-point
control values into fixed-point DSP parameters. Its pad callback counts held
notes and has a TODO for a note stack; note priority and unmatched note-offs
need attention before relying on it as a performance instrument.
