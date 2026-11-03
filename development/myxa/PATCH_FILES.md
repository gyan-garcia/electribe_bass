# MYXA patch files and simulated recovery

Status: implemented portable C codec/recovery state machine and desktop converter.
Tested with simulated storage only. No SD driver, FAT adapter or Save UI is connected.
This specification refines the initial design: v1 names are printable ASCII, not
UTF-8. Unsupported characters are rejected rather than replaced or truncated.

## Binary v1 record

Exactly 392 bytes for schema version 1's 54 parameters. All integers are unsigned
little-endian; floats are IEEE-754 binary32. No native C structure is serialized.

| Offset | Bytes | Meaning |
|---|---:|---|
| 0 | 4 | ASCII MYXA |
| 4 | 2 | File-format version, 1 |
| 6 | 2 | Parameter-schema version, 1 |
| 8 | 2 | Exact total file length, 392 |
| 10 | 2 | Engine ID 3 or 4 |
| 12 | 4 | Nonzero persistent patch ID |
| 16 | 4 | Nonzero generation, monotonically increasing |
| 20 | 1 | Name length, 1–32 |
| 21 | 3 | Reserved, zero |
| 24 | 32 | Printable ASCII name, zero-padded |
| 56 | 2 | Parameter count, 54 |
| 58 | 6 | Reserved, zero |
| 64 | 324 | 54 entries: uint16 stable ID + float32 value |
| 388 | 4 | CRC32/IEEE over bytes 0–387 |

Decoder requires every parameter exactly once, accepts arbitrary entry order,
and rejects invalid length, CRC, engine, metadata, reserved bytes, missing/duplicate
IDs, nonfinite values, out-of-range values and fractional enum selections. Failure
leaves the destination record unchanged. Unsupported file/schema versions remain
untouched and block automated overwrites. No implicit schema migration is applied.
Generation overflow is rejected rather than wrapped. Factory IDs are assigned by
the importer/caller; this code does not yet implement a library-wide ID allocator.

The desktop converter clamps float32 boundary rounding back to valid desktop
ranges when exporting JSON, then reproduces the same float32 values on reimport.
It preserves pan as metadata even though current desktop model/UI does not apply
pan. It preserves the existing fixed EQ and reverb values; custom EQ frequencies/
Q are rejected because this schema cannot represent them. It supports Model D
engine families only, and does not modify source presets. Float32 quantization
is part of the file contract; this is not an exact float64 JSON-value archive.

## Two-slot saving

Each logical patch has two backing files/slots with the same ID. Proposed card
names use a short-ID basename plus A/B extensions, e.g. P0000001.MXA/.MXB. The
actual FatFs adapter/path/ID allocation is still to implement. Full 32-bit patch
IDs do not all fit that particular 7-hex-digit example naming convention; final
path allocation must handle the full supported ID space or explicitly narrow it.

Load validates both, chooses the highest valid generation, and falls back from a
corrupt newer copy to the valid older copy. Equal-generation differing records,
foreign IDs, unsupported formats and read I/O failures block saving. If both files
are absent, a new patch can start at generation 1; damaged-only storage reports an
error rather than silently treating it as empty.

Save first snapshots the edited record in RAM and increments the generation.
It truncates only the inactive slot, writes up to 64 bytes per state-machine step,
flushes/closes, then reopens/reads and validates the complete record. Save reports
DONE only if name, ID, generation, engine and all values match the snapshot. The
old active slot is never deleted, renamed or truncated. An error invalidates the
save state until both slots are reloaded. A power loss after a valid new record
reaches media may recover the new generation even if the old session never
reported success; this ambiguity is expected and recoverable.

This protects records under the tested two-slot backend model. It does NOT prove
FAT metadata or SD controller power-loss durability. Both directory entries/FAT
chains may share sectors; card firmware can reorder/cache writes. Future backend
must implement real flush/close/readback semantics and power-loss fault tests.
No claim of universal atomicity is made. A callback that blocks indefinitely
would also violate the control/audio deadline constraints.

Read callbacks return actual size (0 for absent, negative for error) and must not
write beyond capacity. The final filesystem adapter must detect oversized files,
not silently read a valid 392-byte prefix from a longer file. Storage is single-
owner; concurrent loads/saves or callbacks mutating the same slots are unsupported.
myxa_store_load reads two records; it is not yet a nonblocking filesystem loader.
myxa_store_step performs one bounded backend call per invocation; the backend
must itself guarantee bounded latency. All data buffers are caller-owned, with
no heap allocation in the codec/recovery implementation.

## Tests and reproduction

```
gcc -std=c99 -Wall -Wextra -Werror -fsanitize=address,undefined development/myxa/patch_file.c development/myxa/test_patch_file.c -lm -o development/myxa/build/test_patch_file
ASAN_OPTIONS=detect_leaks=0 development/myxa/build/test_patch_file
desktop/live/.venv/bin/python development/myxa/test_patch_codec.py
```

C tests cover all three factory records, every truncated length, one-bit corruption
at every byte, 393 alternate-slot write cut points, interruptions between save
states, failed finish/readback, a valid but wrong readback, newest-copy fallback,
corrupt-only media, conflicting generations, I/O failures and generation exhaustion.
ASan/UBSan pass; LeakSanitizer is disabled because this host tracing environment
prevents it (the implementation allocates no heap).

Five Python cross-language tests compare C/Python bytes for all factory patches,
valid-CRC malformed fields, reordered IDs, schema boundary values, effect/pan
preservation and custom-EQ rejection. CLI smoke encode/decode also passed.

```
desktop/live/.venv/bin/python development/myxa/patch_codec.py encode presets/user/Moog-Res.json NEWFILE.MYX --id 3
desktop/live/.venv/bin/python development/myxa/patch_codec.py decode NEWFILE.MYX NEWFILE.json
```

Output files are created exclusively; existing files are never overwritten by
these commands. Conversion writes ordinary local test files, not card hardware.

## Linked resource result

```
python3 development/myxa/link_probe.py --compact-layout --minimal-arm --storage-budget --patch-storage-budget
```

This optional nonfunctional footprint experiment retains codec/load/save APIs
and one MyxaStore in the same ARM image as the actual FatFs footprint probe.
It does not attach them to disk I/O. The ARM build links and memory checks pass:
application used 108472 / 114688 bytes, leaving 6216 bytes (6.1 KiB), versus
10752 bytes before record/recovery support. Increment: 4536 bytes including code,
state, tables/retention and alignment. MyxaStore BSS is 928 bytes. Individual
linked function sizes are encode 488, decode 860, load 412, start 192, step 536
bytes; library/helpers and padding explain the rest. The probe conservatively
retains its earlier recovery/browser buffers too; sharing them is a future measured
optimization, not currently assumed. Stack high-water use is not established.

This crosses below the 8 KiB planning margin before real SD driver, save UI and
card timeout/recovery code. Do not call the complete storage feature memory-ready.
Next decision must compare further measured savings against verified external
memory/loader staging, and resolve the SD electrical/clock evidence in
SD_INTERFACE.md. No physical output or storage access was enabled.
