# MYXA UK Bass 50

Fifty source-informed patches designed for the existing desktop engine:

| Numbers | Style | Count | Intended use |
| --- | --- | --- | --- |
| 01-10 | Big Beat | 10 | Driven breakbeat bass, octave weight, dry punch |
| 11-18 | Acid | 8 | Resonant saw/pulse bass and performed cutoff sweeps |
| 19-26 | Garage | 8 | Rounded subs, hollow plucks, soft fronts and metallic edges |
| 27-34 | Jungle | 8 | Detuned Reese tones, deep subs and sharper bass attacks |
| 35-42 | Rubber | 8 | Slower Moog-style vowel contours and elastic slides |
| 43-50 | Lush | 8 | Fuller mono bass/lead textures, gentle detune and dark room |

The original 50-patch research catalog is retained here for reference. The active
library has since been reduced by user selection: only Concrete Reese (29),
Rubber (35–42), and Lush (43–50) remain from this bank. See `presets/LIBRARY.md`
for the complete 26-patch active library, all stored in `presets/user/`.

These are **original sound designs and adapted recipes**, not authenticated
patches used on Prodigy, Fatboy Slim or other artists' records. Artist interviews
give stylistic context; programming tutorials and Moog charts supply specific
techniques. Each entry in `catalog.json` identifies its sources, architecture,
playing range and mod-wheel behavior. The final sound still needs listening
approval: signal measurements cannot certify professional or perceptual quality.

## Research and design

- [Alex Ball's Prodigy tutorial](https://www.youtube.com/watch?v=KwL2S5LRzFM),
  especially the single-saw, resonant, driven approach at 12:10 and the acid
  section at 18:27. Several other sounds in that tutorial rely on sampled waves,
  band-pass filters or oscillator sync; this bank does not claim to reproduce
  those sounds with our simpler engine.
- [Fatboy Slim's Synth History interview](https://www.synthhistory.com/post/interview-with-fatboy-slim)
  informs the big-beat/acid direction, not any numeric patch settings. The
  interview also makes the importance of sampling clear.
- [Roland's Beyond Acid tutorial](https://articles.roland.com/beyond-acid-pushing-the-tb-303-into-new-sonic-territory/)
  informs waveform, contour-decay and resonance contrasts. These patches use
  our ladder and glide, without the TB-303's accent circuitry or sequencer.
- [Attack's three Garage Basslines with SubLab](https://www.attackmagazine.com/technique/synth-secrets/making-3-garage-basslines-with-sublab/)
  supplies the softer triangle approach, including 38/53 ms attack starting
  points. Its external distortion, sample layer and maximizer are not imported.
- [Attack's Subby Bass with U-He Ace](https://www.attackmagazine.com/technique/synth-secrets/subby-bass-with-u-he-ace/)
  informs triangle fundamentals, shaped amplitude and small pitch transients.
- [Marc Adamo's Reese Bass tutorial](https://www.attackmagazine.com/technique/video-tutorials/reese-bass/)
  is a Reese reference. Our corresponding recipes use independent detuned
  oscillators and a quieter triangle to support the low end.
- [Moog's Model D manual](https://cdn.inmusicbrands.com/Moog/Model%20D/Minimoog_Model_D_Manual.pdf),
  the earlier Doctor Mix walkthrough and the locally approved bass architecture
  inform conventional oscillator layering and resonant envelope sounds.

Some Rubber patches use the existing `modeld18` architecture; all others use
`modeld`. The 18 dB tap is our established alternative, not a stock Model D
filter setting. Sub 37-style tones here use the shared oscillator/filter/contour
approach. The engine does not implement the complete Sub 37 modulation system,
duophony, continuous oscillator shapes, hard sync or its Multidrive circuitry.

## How the shortlist was made

The builder considers three restrained settings for each of 62 authored sound
designs, giving 186 candidates in memory. No rejected candidate is saved as a
patch or an audition WAV. One setting per design advances, and style quotas plus
log-spectrum/envelope diversity reduce the bank to 50. The score checks technical
usability; it is not an artist-reference match score or a perceptual ranking.

Final audio is rendered through the real native desktop voice, EQ and room at
48 kHz. Gain trims consider MIDI notes 24, 31, 36, 43, 48, 55 and 60, both the
saved mod-wheel position and full wheel, after effects. A 4x oversampled peak
estimate targets 0.82 before master volume. Active RMS targets 0.25 where peak
headroom allows; shorter plucks may be quieter. Nothing is hard-limited to force
equal loudness. Very low played notes can intentionally produce subsonic partials.

Checks cover valid parameter bounds, finite/non-silent output, headroom, distinct
settings, patch discovery, WAV headers and hashes of pre-existing user files.
The current bank has not been matched against isolated artist recordings, heard
in finished mixes, or tested on the Electribe DSP. Listening and mix judgment
remain necessary. Preset data does not establish a hardware CPU budget.

## Play and audition

Restart the desktop synth and select its Model D family to find `UK50` patches.
Start around G1-C3 for bass and an octave higher for melodic Lush sounds. Detuned
voices are deliberately mono; the room does not provide stereo unison or chorus.
Most basses are dry. The eight Lush voices use a modest room send.

Ordinary patches map the wheel to triangle-LFO cutoff movement. A few metallic
voices instead use audio-rate pitch colour, and punch voices use the filter
contour as a pitch transient; see each catalog entry. This is the engine's
existing CC1 behavior, without adding a modulation matrix or new hardware work.

The listening page is `desktop/live/outputs/uk-bass50/index.html`; every finalist
has its normal phrase and a full-wheel audition. Playback is level-trimmed to
the desktop's default master volume. The page filters by style and stops other
players when a new clip starts. No references or original recordings are embedded.

## Reproduce or verify

From the repository root:

```bash
desktop/live/.venv/bin/python desktop/live/build_uk_bass50.py --install
desktop/live/.venv/bin/python desktop/live/build_uk_bass50.py --verify
```

Installation requires that no `UK50` patches already exist; it refuses to replace
saved user settings. Final patch writes are exclusive and rolled back if the
installation fails. Verification is read-only for patches, and reports intentional
user edits as a mismatch with the published catalog. Local source snapshots and
audio/QA outputs live in the ignored `desktop/live/outputs/uk-bass50` folder.
