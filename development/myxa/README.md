# MYXA firmware work

- DESIGN.md: v1 scope, architecture, storage and acceptance gates.
- AUDIT.md: source-confirmed findings and unresolved integration details.
- schema.json: initial stable parameter IDs/ranges and engine IDs.
- parameters.h: generated embedded factory patch values.
- export_schema.py: reproducible schema/factory export; refuses silent ID changes.

From repository root:

```
desktop/live/.venv/bin/python development/myxa/export_schema.py
```

These files are a host-validated integration foundation, not a completed firmware
port. They do not flash hardware. Next work is memory mapping and the dry DSP
adapter, followed by hardware-independent control-state tests.

Dry adapter and memory audit:

```
bash development/myxa/check_dry.sh
```

This compiles a host bridge and Blackfin object, checks three factory dry renders
against desktop output, and reports baseline ELF memory placement. It does not
link or install a new firmware image. Read AUDIT.md for measured limitations.

Full local link probe:

```
python3 development/myxa/link_probe.py
```

Creates a unique isolated source/build copy and a build/link-probe.log. The current
probe links the DSP but intentionally respects the original ARM memory boundary,
where the combined build currently fails by 2464 bytes. See AUDIT.md. It cannot
be used as an installation package. Each run preserves previous probe directories.

Updated isolated builds (both now link successfully):

```
python3 development/myxa/link_probe.py --compact-layout
python3 development/myxa/link_probe.py --compact-layout --minimal-arm
python3 development/myxa/verify_probe.py PATH_PRINTED_BY_BUILD --minimal
```

Omit `--minimal` when checking the old-app experiment. Logs and configuration are
stored inside each unique probe directory. The minimal shell leaves 54072 bytes
of ARM application space in the measured build; it is not a completed instrument.

Control tests:

```
gcc -std=c99 -Wall -Wextra -Werror -fsanitize=address,undefined development/myxa/test_control.c -o development/myxa/build/test_control
ASAN_OPTIONS=detect_leaks=0 development/myxa/build/test_control
python3 development/myxa/test_probe.py
```

`--minimal-arm` now builds the control-integration shell rather than the original
heartbeat-only shell. Audio remains physically muted. See AUDIT.md for unfinished
MIDI/controller, patch-transaction and transport-recovery work.

Expression and control-link recovery tests:

```
python3 development/myxa/test_arm_control.py
python3 development/myxa/test_probe.py
```

The first uses the real ARM application with fake clock/link functions; the second
uses the real DSP command receiver. Both are host tests. The updated probe adds
snapshot CRC/ack/retry/watchdog recovery and MIDI pitch bend/mod wheel, with the
remaining limitations recorded in AUDIT.md.

First patch/panel workflow is included in the same isolated control build. Use
main encoder to browse, Enter to load, Exit to cancel; edited patches require
confirmation. Shift + EG Int temporarily controls drive until Sample Edit's ID is
verified. Tests in test_arm_control.py and test_probe.py cover this workflow.

Render the real 128x64 screen on the host:

```
desktop/live/.venv/bin/python development/myxa/preview_screen.py
```

The pixel preview goes into ignored build/screen.png. FX/pan are preserved in the
patch transfer but not processed by this dry, muted probe. SD saving is not yet
implemented. See AUDIT.md for protocol details and current memory headroom.

Storage feasibility: see STORAGE_BUDGET.md. `--storage-budget` adds a pinned FatFs
link-size experiment with nonfunctional disk stubs; normal builds omit it. The
text-only screen now avoids printf and uGUI window machinery. Formatter test:

```
gcc -std=c99 -Wall -Wextra -Werror -fsanitize=address,undefined development/myxa/test_text.c -o development/myxa/build/test_text
ASAN_OPTIONS=detect_leaks=0 development/myxa/build/test_text
```

SD interface audit:

```
python3 development/myxa/audit_sd_interface.py
```

See SD_INTERFACE.md for the confirmed native MMCSD0 pinmux, unresolved board
signals/clock details and the read-only probe's implementation/validation gates.
No hardware SD adapter is enabled by this audit.

Patch-file codec, desktop conversion and simulated interrupted-save recovery are
implemented in patch_file.c/.h and patch_codec.py. See PATCH_FILES.md for the
392-byte format, two-slot assumptions and test commands. The optional
`--storage-budget --patch-storage-budget` build measures their complete linked
increment without connecting any card driver. Current combined free ARM span is
6216 bytes, below the planning margin; this is not completed SD saving.

Dry stereo output validation:

```
gcc -std=c99 -Wall -Wextra -Werror -fsanitize=address,undefined development/myxa/test_output.c -lm -o development/myxa/build/test_output
ASAN_OPTIONS=detect_leaks=0 development/myxa/build/test_output
python3 development/myxa/test_probe.py
python3 development/myxa/test_arm_control.py
```

The module computes stereo Q1.31 diagnostics with Pan and master protection;
physical outputs are still unconditionally muted. Level controls patch gain;
Shift + Level temporarily controls Pan until its dedicated event ID is verified.
Keep the normal bass-only probe separate from optional storage footprint builds.

See PANEL_MAP.md for current bass controls and temporary Shift shortcuts. Timing
observations and the pending hardware-loading/recovery checks are recorded in
FIRST_DEVICE_TEST.md. No test loader is invoked by these documents. The ARM shell
now connects glide, amp/filter envelope timing, oscillator waveform and LFO
controls; MIDI channel and pad octave are selectable via temporary Shift shortcuts.

See INSTALLATION_RESEARCH.md for the newly verified upstream documentation of
Hacktribe SD installation followed by external TRS MIDI Freetribe RAM loading.
This is a potential closed-case route, not a validated MYXA installation package.

The follow-up installation research now includes a first-person upstream report
of successful MIDI-loaded monosynth execution and a fake-MIDI test of the real
upstream client. See INSTALLATION_RESEARCH.md for the distinction between that
working route and MYXA-specific hardware validation, which remains pending.
