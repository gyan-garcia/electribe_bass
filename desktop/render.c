#include <math.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include "aleph.h"
#include "aleph_monovoice.h"

static void write_word(FILE *file, uint32_t value, unsigned bytes) {
    for (unsigned byte = 0; byte < bytes; byte++) fputc((value >> (8 * byte)) & 255, file);
}

static void render(const char *name, int mode) {
    static union { max_align_t alignment; char bytes[65536]; } memory;
    t_Aleph aleph;
    Aleph_MonoVoice voice;
    Aleph_init(&aleph, 48000, memory.bytes, sizeof(memory.bytes), NULL);
    Aleph_MonoVoice_init(&voice, &aleph);
    Aleph_MonoVoice_set_shape(&voice, 2);
    Aleph_MonoVoice_set_freq_offset(&voice, 65536);
    Aleph_MonoVoice_set_freq_slew(&voice, 0);
    Aleph_MonoVoice_set_res(&voice, INT32_MAX);
    FILE *file = fopen(name, "wb");
    if (!file) { perror(name); exit(1); }
    const uint32_t frames = 48000 * 8;
    fwrite("RIFF", 1, 4, file); write_word(file, 36 + frames * 2, 4);
    fwrite("WAVEfmt ", 1, 8, file); write_word(file, 16, 4);
    write_word(file, 1, 2); write_word(file, 1, 2);
    write_word(file, 48000, 4); write_word(file, 96000, 4);
    write_word(file, 2, 2); write_word(file, 16, 2);
    fwrite("data", 1, 4, file); write_word(file, frames * 2, 4);
    double energy = 0, peak = 0;
    const int notes[] = {33, 33, 45, 36, 33, 40, 31, 36};
    for (uint32_t frame = 0; frame < frames; frame++) {
        double time = frame / 48000.0;
        int note = mode == 2 ? notes[(frame / 24000) % 8] : 33;
        double frequency = 440 * pow(2, (note - 69) / 12.0);
        double cutoff = mode == 1 ? 90 * pow(60, time / 8) : 1200;
        double envelope = fmin(1, time / 0.01) * fmin(1, fmax(0, (7 - time) / 0.08));
        if (mode == 2) {
            double position = (frame % 24000) / 48000.0;
            envelope *= fmin(1, position / 0.005) * exp(-position * 7);
            cutoff = 180 + 2200 * exp(-position * 12);
        }
        Aleph_MonoVoice_set_freq(&voice, (int32_t)(frequency * 4294967296.0 / 48000));
        Aleph_MonoVoice_set_cutoff(&voice, (int32_t)(cutoff * 3.141592653589793 * 2147483648.0 / 48000));
        Aleph_MonoVoice_set_amp(&voice, (int32_t)(envelope * 0.6 * INT32_MAX));
        double sample = Aleph_MonoVoice_next(&voice) / 2147483648.0;
        energy += sample * sample;
        if (fabs(sample) > peak) peak = fabs(sample);
        write_word(file, (uint16_t)(int16_t)lrint(sample * 32767), 2);
    }
    if (fclose(file)) { perror(name); exit(1); }
    printf("%s peak=%.5f rms=%.5f\n", name, peak, sqrt(energy / frames));
    if (peak < 0.0001) { fprintf(stderr, "Silent render\n"); exit(1); }
}

int main(void) {
    render("outputs/sustained-bass.wav", 0);
    render("outputs/filter-sweep.wav", 1);
    render("outputs/bassline.wav", 2);
    return 0;
}
