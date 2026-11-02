#!/usr/bin/env bash
set -euo pipefail
app=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$app"
for command in gcc g++ pkg-config dpkg-deb; do command -v "$command" >/dev/null; done
if [ ! -x .venv/bin/python ]; then python -m venv --system-site-packages .venv; fi
if [ ! -f libportaudio2_19.6.0-1.2build3_amd64.deb ] || [ ! -f libasound2-dev_1.2.11-1ubuntu0.3_amd64.deb ]; then
    apt-get download libportaudio2=19.6.0-1.2build3 libasound2-dev=1.2.11-1ubuntu0.3
fi
mkdir -p vendor outputs
dpkg-deb -x libportaudio2_19.6.0-1.2build3_amd64.deb vendor
dpkg-deb -x libasound2-dev_1.2.11-1ubuntu0.3_amd64.deb vendor
test -f /lib/x86_64-linux-gnu/libasound.so.2
ln -sfn /lib/x86_64-linux-gnu/libasound.so.2 vendor/usr/lib/x86_64-linux-gnu/libasound.so
ln -sfn libportaudio.so.2 vendor/usr/lib/x86_64-linux-gnu/libportaudio.so
export PKG_CONFIG_PATH="$app/vendor/usr/lib/x86_64-linux-gnu/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export CXXFLAGS="-I$app/vendor/usr/include ${CXXFLAGS:-}"
export LDFLAGS="-L$app/vendor/usr/lib/x86_64-linux-gnu ${LDFLAGS:-}"
.venv/bin/python -m pip install --no-cache-dir --find-links wheels -r requirements.txt
.venv/bin/python -c 'from engine import build_library; print(build_library()); print(build_library("modeld"))'
printf '%s\n' 'Ready. Run bash launch.sh.'
