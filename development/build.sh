#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PATH="$project/toolchains/arm/usr/bin:$project/toolchains/opt/uClinux/bfin-elf/bin:$PATH"
export BFIN_TOOLCHAIN="$project/toolchains/opt/uClinux/bfin-elf/bin/"
export LIB_GCC="$project/toolchains/arm/usr/lib/gcc/arm-none-eabi/13.2.1"
export LIB_C="$project/toolchains/arm/usr/lib/arm-none-eabi/newlib"
export SOURCE_DATE_EPOCH=1735603200
export LC_ALL=C
export TZ=UTC
cd "$project/freetribe"
make clean
make APP=monosynth MODULE=monosynth NEWLIB="$project/toolchains/arm/usr/include/newlib" \
    PICOLIBC_SPECS="$project/toolchains/arm/usr/lib/picolibc/arm-none-eabi/picolibc.specs" \
    PICOLIBC_FLAGS="--picolibc-prefix=$project/toolchains/arm/usr" CPUS=4
sha256sum cpu/build/cpu.bin dsp/build/bfin.ldr
