"""Decode pinned Freetribe SD configuration without accessing hardware."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];CPU=ROOT/'development/freetribe/cpu'
pin=CPU/'src/kernel/peripheral/per_pinmux.c'
startup=CPU/'src/kernel/system/startup.c'
hdr=CPU/'lib/am1802-csl/src/hardware/hw_syscfg0_AM1808.h'
soc=CPU/'lib/am1802-csl/src/hardware/soc_AM1808.h'
text=pin.read_text();definitions=hdr.read_text()
match=re.search(r'SYSCFG0_PINMUX\(10\)\)\s*=\s*(0x[0-9a-fA-F]+)',text)
if not match:raise SystemExit('PINMUX10 assignment changed; review required')
value=int(match[1],16)
fields=[]
for shift,signal in [(0,'CLK'),(4,'CMD'),(8,'DAT0'),(12,'DAT1'),(16,'DAT2'),(20,'DAT3')]:
    name=f'SYSCFG_PINMUX10_PINMUX10_{shift+3}_{shift}_MMCSD0_{signal}'
    found=re.search(r'#define\s+'+name+r'\s+\((0x[0-9A-Fa-f]+)u\)',definitions)
    if not found:raise SystemExit('Missing mux definition: '+name)
    actual=(value>>shift)&15
    if actual!=int(found[1],16):raise SystemExit('Mux mismatch: '+name)
    fields.append({'pinmux_bits':f'{shift+3}:{shift}','function':f'MMCSD0_{signal}','value':actual})
base=re.search(r'#define SOC_MMCSD_0_REGS\s+\((0x[0-9A-Fa-f]+)\)',soc.read_text())
if not base:raise SystemExit('Controller base definition changed')
enabled='PSCModuleControl(SOC_PSC_0_REGS, HW_PSC_MMCSD0, 0, PSC_MDCTL_NEXT_ENABLE)' in startup.read_text()
if not enabled:raise SystemExit('Controller power/clock enable not found')
report={'controller':'MMCSD0','register_base':base[1], 'pinmux10':hex(value),'signals':fields,
 'psc_enable_present':enabled,
 'gpio_fields':[{'pinmux_bits':'31:28','function':'GPIO4_0','value':(value>>28)&15},
                {'pinmux_bits':'27:24','function':'GPIO4_1','value':(value>>24)&15}],
 'interpretation':'Source configures native SD clock/CMD/DAT0..3. GPIO functions do not establish card detect/write protect.',
 'unknowns':['physical slot net continuity and board revision','card detect polarity/pin or verified command-probing policy',
             'card power rail/control and stabilization','actual MMC input clock and safe divider',
             'response/FIFO register semantics and silicon errata'],
 'ready_for_mmio':False,
 'source_sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (pin,startup,hdr,soc)}}
out=ROOT/'development/myxa/build/sd-interface.json';out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(report,indent=2)+'\n')
print('Confirmed in source: MMCSD0 at',base[1],'; PINMUX10',hex(value),'; CLK/CMD/DAT0..3; PSC enabled.')
print('Physical slot wiring, detect/power and clock remain unverified. No hardware access enabled.')
print(out)
