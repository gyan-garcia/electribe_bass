# Bass prototype panel map

Status: IDs supported by pinned Freetribe examples are connected; actual device
behavior remains untested. Unknown dedicated knob/button IDs are not invented.

| Control | Source event ID | Current prototype function |
|---|---|---|
| Main Value encoder | encoder 0x00 | Browse three factory patches |
| Menu/Enter | button 0x09 | Load; confirm discard if edited |
| Exit | button 0x0d | Cancel browsing/confirmation |
| Cutoff encoder | encoder 0x02 | Logarithmic cutoff increments |
| Resonance | knob 0x03 | Filter resonance |
| EG Int | knob 0x04 | Filter envelope amount |
| Shift + EG Int | same knob | Mixer drive, temporary substitute for Sample Edit |
| Level | knob 0x00 | Patch gain in dB |
| Shift + Level | same knob | Pan, temporary substitute for dedicated Pan |
| Pitch/Glide | knob 0x02 | Glide |
| Attack | knob 0x06 | Amp attack, or filter attack when switched |
| Decay/Release | knob 0x08 | Amp decay/release, or filter decay/release when switched |
| Amp EG | button 0x20 | Switch both timing knobs between amp/filter envelopes |
| Modulation Speed | knob 0x0a | LFO rate |
| Modulation Depth | knob 0x05 | Modulation amount, kept consistent with MIDI CC1 |
| Sample selector | encoder 0x01 | Oscillator 1 waveform |
| Shift + Value | encoder 0x00 | Global MIDI channel: Omni, 1–16 |
| Shift + Sample selector | encoder 0x01 | Pad octave, base C, MIDI 0–108 |
| Shift + Play | button 0x02 | Hard panic; temporary substitute for unverified Stop ID |

Shift is button 0x0a. ID evidence: upstream apps/monosynth, apps/zontar,
apps/midi-knob and kernel panel parser. These are source mappings, not measured
physical control events. Master Volume may be analog/codec-controlled; its
physical path is not verified. A validated software master API exists separately.

All absolute targets use pickup with crossing and a two-raw-step tolerance.
Attack, decay, glide and LFO-rate knobs use a quadratic response for finer low-end
control; pickup tests the same mapping. Switching envelope target resets timing
pickup; switching Shift resets affected shared-pot pickup. Relative encoders do
not need pickup. Amp/filter envelope choice is shown in the selected parameter
label; the matching LED is not yet implemented. Independent release times are not
invented: existing engine decay/release coupling remains.

Octave shifts change only new pad notes. Held pads retain their pressed note for
release tracking. MIDI octave is unaffected. Channel changes clear MIDI-held notes
and bend/sustain while preserving held pads. These global settings are in RAM;
persistence and full system pages remain pending. Master Volume, dedicated Pan,
Sample Edit, dedicated octave buttons, Stop and remaining effects controls still
need the physical event audit. Current shift shortcuts are explicitly temporary.

Hard panic is encoded as a complete checksummed snapshot with gate clear and
trigger bit set. It clears the DSP voice, target gain and stereo smoothing state;
ordinary note-off still follows release. Retried panic snapshots are idempotent.
Physical outputs remain unconditionally muted, independent of these controls.
