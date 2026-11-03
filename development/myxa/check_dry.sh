#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root"
python3 development/myxa/memory_audit.py
desktop/live/.venv/bin/python development/myxa/export_schema.py
mkdir -p development/myxa/build
gcc -O3 -Wall -Wextra -Werror -shared -fPIC development/myxa/dry_adapter.c -lm -o development/myxa/build/dry_adapter.so
development/toolchains/opt/uClinux/bfin-elf/bin/bfin-elf-gcc -std=gnu99 -O2 -mcpu=bf527 -D__ADSPBF523__ -Wall -Wextra -c development/myxa/dry_adapter.c -o development/myxa/build/dry_adapter.o
development/toolchains/opt/uClinux/bfin-elf/bin/bfin-elf-size development/myxa/build/dry_adapter.o
desktop/live/.venv/bin/python development/myxa/test_dry_adapter.py
