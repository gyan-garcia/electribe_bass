"""Validate linked memory invariants; not a hardware startup test."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
work=Path(sys.argv[1]).resolve()
tool=ROOT/'development/toolchains/arm/usr/bin/arm-none-eabi-nm'
text=subprocess.check_output([str(tool),'-S',str(work/'cpu/build/cpu.elf')],text=True)
symbols={line.split()[-1]:int(line.split()[0],16) for line in text.splitlines() if len(line.split())>=3 and line.split()[0].isalnum()}
assert symbols['page_table']==0x8001c000
assert symbols['_heap_end']<=0x8001c000
assert symbols['_stack_low']==0xffff0080 and symbols['_stack']==0xffff2000
assert symbols['_heap_end']-symbols['_heap_start']==2048
if '--minimal' in sys.argv:
    assert 'g_leaf' not in symbols and 'g_mempool' not in symbols
loader=work/'dsp/build/bfin.ldr'
assert loader.is_file() and loader.stat().st_size>0
print('Verified page-table placement, heap/stack bounds and DSP loader.')
print('Free ARM application span:',0x8001c000-symbols['_heap_end'],'bytes (excludes reserved MMU table).')
