"""Read linked ELF section placement; does not rebuild or flash."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DEV=ROOT/'development'
report={}
for cpu,tool in [('cpu',DEV/'toolchains/arm/usr/bin/arm-none-eabi-size'),('dsp',DEV/'toolchains/opt/uClinux/bfin-elf/bin/bfin-elf-size')]:
    elf=DEV/f'freetribe/{cpu}/build'/('cpu.elf' if cpu=='cpu' else 'bfin.elf')
    script=(DEV/f'freetribe/{cpu}/{cpu}.lds').read_text()
    regions=[]
    for name,base,length in re.findall(r'(\w+)\s*(?:\([^)]*\))?\s*:\s*ORIGIN\s*=\s*(0x[0-9a-fA-F]+),\s*LENGTH\s*=\s*(0x[0-9a-fA-F]+)',script):
        regions.append({'name':name,'base':int(base,16),'capacity':int(length,16),'sections':[]})
    for line in subprocess.check_output([str(tool),'-A',str(elf)],text=True).splitlines():
        match=re.match(r'^(\S+)\s+(\d+)\s+(\d+)\s*$',line)
        if not match:continue
        name,size,address=match.groups();size=int(size);address=int(address)
        for region in regions:
            if region['base']<=address<region['base']+region['capacity'] and size:
                region['sections'].append({'name':name,'size':size,'address':address})
    for r in regions:
        r['occupied_span']=max([s['address']+s['size']-r['base'] for s in r['sections']]+[0])
        r['remaining_span']=r['capacity']-r['occupied_span']
        print(cpu,r['name'],r['occupied_span'],'/',r['capacity'],'bytes; remaining',r['remaining_span'])
    report[cpu]={'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),'regions':regions}
report['limitations']='Linked baseline only. Unallocated space is not proven free runtime heap/stack capacity. DSP scratch stack is reserved by symbols, not sections. ARM embeds DSP loader, so DSP growth can also increase ARM footprint.'
out=DEV/'myxa/build';out.mkdir(exist_ok=True)
(out/'memory.json').write_text(json.dumps(report,indent=2)+'\n')
