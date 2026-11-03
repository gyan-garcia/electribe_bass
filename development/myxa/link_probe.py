"""Build an isolated, silent link probe. Never writes the upstream checkout."""
from pathlib import Path
import os,shutil,subprocess,argparse,hashlib,zipfile,re
from datetime import datetime
ROOT=Path(__file__).resolve().parents[2];DEV=ROOT/'development';HERE=DEV/'myxa'
parser=argparse.ArgumentParser()
parser.add_argument('--compact-layout',action='store_true')
parser.add_argument('--minimal-arm',action='store_true')
parser.add_argument('--storage-budget',action='store_true')
parser.add_argument('--patch-storage-budget',action='store_true')
options=parser.parse_args()
if options.patch_storage_budget and not options.storage_budget:parser.error('--patch-storage-budget requires --storage-budget')
if options.storage_budget and not options.minimal_arm:parser.error('--storage-budget requires --minimal-arm')
work=HERE/('build/link-probe-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
if work.exists():raise SystemExit('Probe directory exists; inspect or move it before rebuilding.')
shutil.copytree(DEV/'freetribe',work,ignore=shutil.ignore_patterns('.git','build'))
if options.compact_layout:
    linker=work/'cpu/cpu.lds'
    script=linker.read_text()
    # Reserve the final aligned 16 KiB explicitly; do not grow physical RAM.
    script=script.replace('LENGTH = 0x20000','LENGTH = 0x1c000')
    script=script.replace('    ARM_RAM (rwx)', '    MMU_TABLE (rw) : ORIGIN = 0x8001c000, LENGTH = 0x4000\n    ARM_RAM (rwx)')
    script=script.replace('    /*\n     * Vector table', '''    .page_table (NOLOAD) :
    {
        KEEP(*(.bss.page_table))
    } > MMU_TABLE
    ASSERT(SIZEOF(.page_table) == 0x4000, "Unexpected page table size")
    ASSERT((ADDR(.page_table) & 0x3fff) == 0, "Page table misaligned")

    /*
     * Vector table''')
    assert '.page_table (NOLOAD)' in script
    linker.write_text(script)
if options.minimal_arm:
    app=work/'cpu/src/apps/myxa';app.mkdir()
    shutil.copyfile(HERE/'arm_probe_app.c',app/'myxa.c')
    shutil.copyfile(HERE/'screen.c',app/'screen.c')
    (app/'myxa_panel.inc').write_text('#include "'+str(HERE/'panel_ui.h')+'"\n')
    (app/'myxa_control.inc').write_text('#include "'+str(HERE/'control.h')+'"\n#include "'+str(HERE/'transport.h')+'"\n#include "'+str(HERE/'patch_transfer.h')+'"\n')
if options.storage_budget:
    archive=HERE/'build/ff16.zip'
    expected='99f7dc1f7e095356e4a9e3dbe29959090d8b948afe2bbc5441e52fdf4b85449e'
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest()!=expected:
        raise SystemExit('Missing/mismatched official ff16.zip; see STORAGE_BUDGET.md')
    fat=app/'fatfs';fat.mkdir()
    with zipfile.ZipFile(archive) as z:
        for name in ('ff.c','ff.h','ffconf.h','diskio.h'):
            (fat/name).write_bytes(z.read('source/'+name))
    config=(fat/'ffconf.h').read_text()
    for key,value in {'FF_CODE_PAGE':437,'FF_FS_TINY':1,'FF_FS_NORTC':1}.items():
        config=re.sub(r'(#define\s+'+key+r'\s+)\d+',lambda m:m[1]+str(value),config)
    (fat/'ffconf.h').write_text(config)
    shutil.copyfile(HERE/'storage_budget.c',app/'storage_budget.c')
    arm=app/'myxa.c'
    source=arm.read_text().replace('t_status app_init(void){','void myxa_storage_budget_keep(void);\nt_status app_init(void){\n    myxa_storage_budget_keep();')
    if options.patch_storage_budget:
        source=source.replace('myxa_storage_budget_keep();','myxa_storage_budget_keep();\n    myxa_record_budget_keep();').replace('void myxa_storage_budget_keep(void);','void myxa_storage_budget_keep(void);\nvoid myxa_record_budget_keep(void);')
        for name in ('patch_file.c','patch_file.h','parameters.h'):
            shutil.copyfile(HERE/name,app/name)
        with (work/'cpu/Makefile').open('a') as flags:
            flags.write('\nCFLAGS += -DMYXA_RECORD_BUDGET\n')
    arm.write_text(source)
module=work/'dsp/src/modules/myxa';module.mkdir()
with (work/'dsp/Makefile').open('a') as f:
    f.write('\n$(BUILD_DIR)/./src/modules/myxa/myxa.c.o: CFLAGS += -std=gnu99\n')
shutil.copyfile(HERE/'link_probe_module.c',module/'myxa.c')
(module/'myxa_output.inc').write_text('#include "'+str(HERE/'output.h')+'"\n')
(module/'myxa_transport.inc').write_text('#include "'+str(HERE/'transport.h')+'"\n#include "'+str(HERE/'patch_transfer.h')+'"\n')
(module/'myxa_dry_adapter.inc').write_text('#include "'+str(HERE/'dry_adapter.c')+'"\n')
env=os.environ.copy()
env.update(BFIN_TOOLCHAIN=str(DEV/'toolchains/opt/uClinux/bfin-elf/bin')+'/',
 LIB_GCC=str(DEV/'toolchains/arm/usr/lib/gcc/arm-none-eabi/13.2.1'),
 LIB_C=str(DEV/'toolchains/arm/usr/lib/arm-none-eabi/newlib'),SOURCE_DATE_EPOCH='1735603200',LC_ALL='C',TZ='UTC')
env['PATH']=str(DEV/'toolchains/arm/usr/bin')+':'+str(DEV/'toolchains/opt/uClinux/bfin-elf/bin')+':'+env['PATH']
args=['make','APP='+('myxa' if options.minimal_arm else 'monosynth'),'MODULE=myxa','CPUS=4',
 'NEWLIB='+str(DEV/'toolchains/arm/usr/include/newlib'),
 'PICOLIBC_SPECS='+str(DEV/'toolchains/arm/usr/lib/picolibc/arm-none-eabi/picolibc.specs'),
 'PICOLIBC_FLAGS=--picolibc-prefix='+str(DEV/'toolchains/arm/usr')]
logpath=work/'build.log'
with logpath.open('w') as log:
    result=subprocess.run(args,cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT)
print('Worktree:',work)
print('Build exit:',result.returncode,'Log:',logpath)
(work/'configuration.txt').write_text(str(vars(options))+'\n')
raise SystemExit(result.returncode)
