#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$project"
sha256sum -c downloads.sha256
mkdir -p toolchains/arm
for package in downloads/*.deb; do
    dpkg-deb -x "$package" toolchains/arm
done
tar -xjf downloads/blackfin.tar.bz2 -C toolchains
if [ ! -d freetribe ]; then
    git clone https://github.com/bangcorrupt/freetribe.git freetribe
fi
git -C freetribe checkout 5fe6658a6038fea70c8e802ae61d8a67bf22ff3a
git -C freetribe submodule update --init --recursive
if git -C freetribe apply --check ../local-build.patch; then
    git -C freetribe apply ../local-build.patch
else
    git -C freetribe apply --reverse --check ../local-build.patch
fi
printf '%s\n' 'Toolchains ready. Run bash build.sh.'
