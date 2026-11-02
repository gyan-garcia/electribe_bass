#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$project"
bash build.sh > build-first.log 2>&1
sha256sum freetribe/cpu/build/cpu.bin freetribe/dsp/build/bfin.ldr \
    freetribe/cpu/build/cpu.elf freetribe/dsp/build/bfin.elf > build-first.sha256
bash build.sh > build-second.log 2>&1
sha256sum -c build-first.sha256
