"""Host validation of actual DSP command decoder with hardware types stubbed."""
import subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as d:
    p=Path(d)
    (p/'module.h').write_text('#include <stdint.h>\ntypedef int32_t fract32;\n')
    (p/'myxa_dry_adapter.inc').write_text('#include "'+str(HERE/'dry_adapter.c')+'"\n')
    (p/'myxa_output.inc').write_text('#include "'+str(HERE/'output.h')+'"\n')
    (p/'myxa_transport.inc').write_text('#include "'+str(HERE/'transport.h')+'"\n#include "'+str(HERE/'patch_transfer.h')+'"\n')
    (p/'test.c').write_text('''#include <assert.h>
#include "'''+str(HERE/'link_probe_module.c')+'''"
int main(void){
    int32_t in[2]={0},out[2]={1,1};float f;int32_t bits;int i;
    module_init();assert(note_gate==0);
    uint32_t note=0xa1010000u|36u|(100u<<7)|(1u<<14)|(1u<<15);
    uint32_t expression=0xc0000000u|(1u<<21)|8192u;
    module_set_param(0x7000,(int32_t)note);
    assert(note_gate==0); /* partial update cannot open the gate */
    module_set_param(MYXA_CMD_EXPRESSION,(int32_t)expression);
    module_set_param(MYXA_CMD_COMMIT,(int32_t)myxa_checksum(note,expression));
    assert(note_gate==1&&note_trigger==1&&note_pitch>65&&note_pitch<66);
    assert(fabs(target_gain-pow(100.0/127,.7)*patch_gain)<1e-12);
    for(i=0;i<1000;i++)module_process(in,out);
    assert(out[0]==0&&out[1]==0&&isfinite(myxa_probe_sample)&&note_trigger==0);
    assert(myxa_probe_stereo[0]!=0&&myxa_probe_stereo[1]!=0); /* Notes reach the stereo diagnostic path. */
    f=200;memcpy(&bits,&f,4);module_set_param(MYXA_CUTOFF_HZ,bits);
    assert(settings[CUTOFF]==200);
    f=NAN;memcpy(&bits,&f,4);module_set_param(MYXA_CUTOFF_HZ,bits);assert(settings[CUTOFF]==200);
    f=1.5;memcpy(&bits,&f,4);module_set_param(MYXA_OSC1_WAVE,bits);
    assert(myxa_rejected_commands==2);
    module_set_param(0xffff,0);assert(myxa_rejected_commands==3);
    module_set_param(0x7000,0);assert(myxa_rejected_commands==4);
    module_set_param(0x7000,(int32_t)note);
    module_set_param(MYXA_CMD_EXPRESSION,(int32_t)expression);
    module_set_param(MYXA_CMD_COMMIT,(int32_t)myxa_checksum(note,expression));
    assert(note_trigger==0); /* duplicate retry is idempotent */
    for(i=0;i<24001;i++)module_process(in,out);
    assert(note_gate==0&&target_gain==0);
    module_set_param(0x7000,(int32_t)note);
    module_set_param(MYXA_CMD_EXPRESSION,(int32_t)expression);
    module_set_param(MYXA_CMD_COMMIT,(int32_t)myxa_checksum(note,expression));
    assert(note_gate==0); /* stale retry cannot revive timed-out note */
    note=0xa1020000u|36u|(100u<<7)|(1u<<14)|(1u<<15);
    expression=0xc0000000u|(2u<<21)|(127u<<14)|16383u;
    module_set_param(0x7000,(int32_t)note);
    module_set_param(MYXA_CMD_EXPRESSION,(int32_t)expression);
    module_set_param(MYXA_CMD_COMMIT,0);assert(note_gate==0);
    module_set_param(0x7000,(int32_t)note);
    module_set_param(MYXA_CMD_EXPRESSION,(int32_t)expression);
    module_set_param(MYXA_CMD_COMMIT,(int32_t)myxa_checksum(note,expression));
    assert(note_gate==1&&note_pitch>73&&note_pitch<74&&settings[MOD_AMOUNT]==1);
    assert(module_get_param(MYXA_CMD_ACK)==(int32_t)note);
    f=-1;memcpy(&bits,&f,4);module_set_param(MYXA_PAN,bits);
    assert(stereo.pan==-1&&myxa_float((uint32_t)module_get_param(MYXA_PAN))==-1);
    for(i=0;i<20000;i++)module_process(in,out);
    assert(myxa_probe_stereo[0]!=0&&myxa_probe_stereo[1]==0&&out[0]==0&&out[1]==0);
    f=0;memcpy(&bits,&f,4);module_set_param(MYXA_CMD_MASTER,bits);
    for(i=0;i<24000;i++)module_process(in,out);
    assert(myxa_probe_stereo[0]==0&&myxa_probe_stereo[1]==0);
    /* Full patch transfer: missing or corrupt fields leave active settings intact. */
    float original=settings[CUTOFF];uint32_t header=0xb1040001u;
    module_set_param(MYXA_PATCH_BEGIN,(int32_t)header);
    module_set_param(MYXA_PATCH_DATA+MYXA_CUTOFF_HZ-1,(int32_t)myxa_bits(999));
    module_set_param(MYXA_PATCH_COMMIT,0);assert(settings[CUTOFF]==original);
    for(int rank=0;rank<3;rank++){
        header=0xb1040000u+(uint32_t)rank+2;
        module_set_param(MYXA_PATCH_BEGIN,(int32_t)header);
        for(int j=0;j<MYXA_PARAMETER_COUNT;j++)module_set_param(MYXA_PATCH_DATA+j,(int32_t)myxa_bits(myxa_factory_patches[rank].values[j]));
        uint32_t crc=myxa_patch_crc(header,myxa_factory_patches[rank].values);
        module_set_param(MYXA_PATCH_COMMIT,(int32_t)(crc^1));assert(settings[CUTOFF]==original);
        module_set_param(MYXA_PATCH_COMMIT,(int32_t)crc);
        assert(settings[CUTOFF]==myxa_factory_patches[rank].values[MYXA_CUTOFF_HZ-1]);
        assert(memcmp(active_patch,myxa_factory_patches[rank].values,sizeof(active_patch))==0);
        original=settings[CUTOFF];voice.amp=.25;
        module_set_param(MYXA_PATCH_COMMIT,(int32_t)crc);assert(voice.amp==.25); /* lost ACK retry doesn't reset twice */
    }
    note=0xa1038000u;expression=0xc0000000u|(3u<<21)|8192;
    voice.amp=.5;target_gain=1;
    module_set_param(MYXA_CMD_NOTE,(int32_t)note);
    module_set_param(MYXA_CMD_EXPRESSION,(int32_t)expression);
    module_set_param(MYXA_CMD_COMMIT,(int32_t)myxa_checksum(note,expression));
    assert(voice.amp==0&&target_gain==0&&note_gate==0);
    module_process(in,out);assert(myxa_probe_stereo[0]==0&&myxa_probe_stereo[1]==0);
    return 0;
}
''')
    subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+d,str(p/'test.c'),'-lm','-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
print('DSP note decoding, parameter rejection and muted-output checks passed.')
