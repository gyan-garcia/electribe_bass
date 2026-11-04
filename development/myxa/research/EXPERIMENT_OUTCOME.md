# Retained baseline: UK Res Bass

The user compared the experimental nonlinear ladder and compensation variants
against the original Moog Res and UK Res Bass patches and reported no useful
audible difference. At the user's request, the experimental engine, UI controls,
six starter patches, and generated auditions were removed.

UK Res Bass remains the retained patch baseline using the original `modeld18`
engine. Its parameters, EQ, reverb, and output gain are unchanged. Model D mode
now selects UK Res Bass by default. The historical bassline-v1 baseline, Moog Res,
the other user patches, and the UK50 bank remain intact.

The source research and read-only diagnostic measurements are retained as
research, not as approved implementation recommendations. Do not reintroduce
the rejected experiment as an accepted sound improvement. No hardware was
flashed.

Subsequent decisions supersede the filter details above: the active library now
contains 26 selected patches, and the user chose a fixed 24 dB/octave low-pass
engine. The six retained 18 dB patches (including UK Res Bass and Moog Res)
were retuned for that engine. See `desktop/live/24DB-MIGRATION.md`.
