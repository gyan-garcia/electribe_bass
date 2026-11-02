#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -p "$project/downloads"
cd "$project/downloads"
apt-get download gcc-arm-none-eabi=15:13.2.rel1-2 \
    binutils-arm-none-eabi=2.42-1ubuntu1+23 \
    libnewlib-arm-none-eabi=4.4.0.20231231-2 \
    libnewlib-dev=4.4.0.20231231-2 picolibc-arm-none-eabi=1.8.6-2
if [ ! -f blackfin.tar.bz2 ]; then
    curl -fL --retry 3 \
        https://downloads.sourceforge.net/project/adi-toolchain/2014R1/2014R1-RC2/x86_64/blackfin-toolchain-elf-gcc-4.3-2014R1-RC2.x86_64.tar.bz2 \
        -o blackfin.tar.bz2
fi
cd "$project"
sha256sum -c downloads.sha256
