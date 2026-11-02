#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
aleph=../development/freetribe/dsp/lib/aleph-dsp
mkdir -p build outputs
includes=(-Iinclude -I"$aleph/lib/libfixmath/libfixmath")
while IFS= read -r directory; do includes+=(-I"$directory"); done < <(find "$aleph/src" -type d)
sources=()
while IFS= read -r source; do sources+=("$source"); done < <(find "$aleph/src" -name '*.c' ! -name 'aleph_fm_voice.c' | sort)
gcc -std=gnu11 -g -O1 -fwrapv -ffunction-sections -fdata-sections \
    "${includes[@]}" "${sources[@]}" render.c -Wl,--gc-sections -lm -o build/render
./build/render
