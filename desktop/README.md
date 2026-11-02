# Desktop listening previews

Run `bash build.sh`, then `python3 check.py` in this directory.
Requires GCC, bash, make-independent source checkout, and Python 3 for checks.
The WAVs in `outputs/` are eight-second, mono, 16-bit PCM at 48 kHz:
`sustained-bass.wav`, `filter-sweep.wav`, and `bassline.wav`.

The renderer compiles the checked-out Aleph_MonoVoice DSP and its dependencies
directly. It bypasses the ARM app, SPI, device drivers and DSP module wrapper.
It supplies its own note/envelope/sweep automation. No firmware files are changed.
Outputs are listening previews, not recordings or bit-exact Blackfin emulation.

`include/fract_math.h` provides portable fixed-point intrinsics for the source;
hardware rounding modes and all corner cases have not been validated against
Blackfin. Signed wrapping in upstream phase accumulators uses GCC `-fwrapv`.
The unused FM voice source is excluded because it includes hardware registers.

Two observations affect the preview setup:

- Startup pitch slew begins at zero: `Aleph_LPFOnePole_set_output` writes the
  target, not the output. A small starting phase increment leads to integer
  division by zero in `_polyblep`. The harness sets pitch slew coefficient to
  zero before rendering. This needs separate firmware investigation.
- The CPU's oscillator scaling is approximately `2^31 / 48000`; in this native
  voice it produces an octave below the requested note. The harness uses
  `2^32 / 48000`, verified with a sustained 55 Hz A1 tone. This host-side tuning
  correction is not applied to the firmware. Filter scaling follows the CPU's
  existing conversion. These controls are not a claim of device equivalence.

The harness uses a larger, aligned memory pool for 64-bit host pointers, two
unison saw oscillators, the upstream filter/DC blocker, and 60% amplitude.
The checks validate WAV format, non-silence, output headroom, release, A1 tuning,
and byte-identical repeat renders. They do not prove audio quality, hardware
timing, exact math equivalence, or Mariana-like character.
