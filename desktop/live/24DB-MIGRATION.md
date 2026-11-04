# Fixed Model D low-pass filter

The user selected a single 24 dB/octave low-pass engine. All 26 active patches
are stored in `presets/user/`; all now have architecture `modeld` and reserved
`filter_mode` value zero. No filter type or slope control is exposed or MIDI
learnable. Existing parameter IDs and the 47-slot native contract are retained.

The six former 18 dB patches were adjusted using the existing demonstration
sequence, matching normalized time-varying spectral bands by tuning cutoff and
filter contour depth. Clean patch gain was then adjusted to match RMS level.
Oscillator settings, resonance, envelope times, EQ and reverb were preserved.
The spectral error improved over an unadjusted 24 dB conversion for all six;
this is an approximate sound match, not a listening approval or waveform identity.

| Patch | Old cutoff | New cutoff |
| --- | --- | --- |
| BOSS 03 | 58.38 Hz | 68.74 Hz |
| Moog Res | 64.84 Hz | 71.15 Hz |
| UK Res Bass | 76.31 Hz | 90.99 Hz |
| UK50 Rubber — Amber Envelope | 115.00 Hz | 124.43 Hz |
| UK50 Rubber — Liquorice | 90.30 Hz | 96.55 Hz |
| UK50 Rubber — Bubblegum | 85.00 Hz | 89.80 Hz |

The other 20 active patch files are byte-for-byte unchanged. Embedded factory
values for UK Res Bass, BOSS 03 and Moog Res were regenerated from the migrated
desktop patches. The native DSP always returns the fourth low-pass stage,
including when a caller supplies legacy engine/mode values. Compatibility slots
remain accepted; they do not expose alternative filters.

Original JSON files for all 26 patches, the original C source, six converted JSON
files, level-matched WAV pairs, a listening page, and numerical results are under:

`outputs/24db-migration-20261104T023849Z/`

`outputs/active-24db-migration.json` records the actual folder. The UTC timestamp
in that generated folder name is an artifact identifier. Backups are outside the
active library and are not displayed by the patch selector.

`migrate_24db.py --apply` performed the one-time fit while the original engine
was still present. It must not be used to fit 18 dB references through the new
fixed engine. The frozen source and original JSONs are retained for replay.

The removed high-pass mode is not emulated by a separate effect. Historical
research patches imported later are normalized to low-pass/24 dB; they are not
automatically fitted. No hardware was flashed.
