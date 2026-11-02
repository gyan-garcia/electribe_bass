"""Desktop performance and isolated Blackfin object checks; never opens devices."""
import ctypes
import json
from pathlib import Path
import subprocess
import time

import numpy as np

from engine import Synth
from model import ROOT, read_patch


def main():
    directory=Path(__file__).parent/'outputs'
    directory.mkdir(exist_ok=True)
    report={'rate':48000,'buffer_frames':256,'budget_ms':256/48,'hardware_timing_verified':False}
    for key,filename in (('bass','model-d-bass.json'),('filter_fm','model-d-modulation.json')):
        patch=read_patch(ROOT/'presets'/filename)
        if key=='filter_fm':
            patch['parameters'].update(filter_mod_enabled=1,mod_amount=1,osc3_fixed_hz=200)
        synth=Synth(patch)
        try:
            synth.send('midi',('note_on',0,31,100))
            for _ in range(50): synth.render(256)
            times=[]
            for _ in range(1200):
                start=time.perf_counter_ns()
                synth.render(256)
                times.append((time.perf_counter_ns()-start)/1e6)
            report[key]={'median_ms':float(np.median(times)),
                         'p99_ms':float(np.percentile(times,99)),
                         'max_ms':max(times),'clipped_blocks':synth.clipped}
            synth.modeld_voice.library.synth_state_size.restype=ctypes.c_int
            report['native_state_bytes']=synth.modeld_voice.library.synth_state_size()
        finally: synth.close()
    prefix=ROOT/'development/toolchains/opt/uClinux/bfin-elf/bin/bfin-elf-'
    obj=directory/'modeld-bfin.o'
    command=[str(prefix)+'gcc','-std=gnu99','-O3','-mcpu=bf527','-DMODEL_D_EMBEDDED',
             '-c',str(Path(__file__).parent/'native/modeld.c'),'-o',str(obj)]
    subprocess.run(command,check=True)
    report['blackfin_compile']=command
    report['blackfin_size']=subprocess.check_output([str(prefix)+'size',str(obj)],text=True)
    report['blackfin_unresolved_symbols']=subprocess.check_output([str(prefix)+'nm','-u',str(obj)],text=True)
    report['limits']='Object only: excludes linked maths libraries, buffers, firmware and cycle cost. No on-device timing.'
    target=directory/'modeld-validation.json'
    target.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
