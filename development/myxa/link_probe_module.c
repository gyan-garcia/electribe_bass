/* Validated control integration probe. Physical outputs remain muted. */
#include "module.h"
#include "myxa_dry_adapter.inc"
#include <string.h>
#include "myxa_transport.inc"
#include "myxa_output.inc"
#define MYXA_CMD_MASTER 0x7004
#define MYXA_CMD_NOTE 0x7000
#define MYXA_NOTE_TAG 0xa1000000u
volatile float myxa_probe_sample;
volatile int32_t myxa_probe_stereo[2];
static MyxaOutput stereo;
volatile uint32_t myxa_rejected_commands;
static float note_pitch,note_gate,note_trigger,note_velocity;
static uint32_t staged_note,staged_expression,acknowledged,staged_mask,age;
static MyxaPatchRx patch_rx;
static float active_patch[MYXA_PARAMETER_COUNT];
static double gain_coefficient,target_gain,patch_gain;
#define MYXA_TIMEOUT_SAMPLES 24000

void module_init(void){
    memset(&patch_rx,0,sizeof(patch_rx));memcpy(active_patch,myxa_factory_patches[2].values,sizeof(active_patch));
    myxa_output_init(&stereo,48000);
    myxa_output_pan(&stereo,active_patch[MYXA_PAN-1]);
    myxa_dry_init(2);note_pitch=49;note_gate=note_trigger=note_velocity=0;
    staged_mask=acknowledged=age=0;
    gain_coefficient=1.0-exp(-1.0/(.005*48000));target_gain=0;
    patch_gain=pow(10.,myxa_factory_patches[2].values[MYXA_OUTPUT_GAIN_DB-1]/20.);
}
void module_process(fract32 *in,fract32 *out){
    float sample;(void)in;
    if(age<MYXA_TIMEOUT_SAMPLES && ++age==MYXA_TIMEOUT_SAMPLES){
        synth_reset(&voice);note_gate=note_trigger=0;target_gain=0;staged_mask=0;
    }
    myxa_dry_process(&note_pitch,&note_gate,&note_trigger,&sample,1);
    note_trigger=0;
    voice.gain+=gain_coefficient*(target_gain-voice.gain);
    myxa_probe_sample=sample*voice.gain;
    {
        int32_t lr[2];myxa_output_sample(&stereo,myxa_probe_sample,lr);
        myxa_probe_stereo[0]=lr[0];myxa_probe_stereo[1]=lr[1];
        if(!isfinite(myxa_probe_sample)){synth_reset(&voice);note_gate=note_trigger=0;target_gain=0;}
    }
    out[0]=0;out[1]=0; /* Physical output mute remains unconditional. */
}
void module_set_param(uint16_t index,int32_t value){
    uint32_t word=(uint32_t)value;
    if(index==MYXA_PATCH_BEGIN || index==MYXA_PATCH_COMMIT || (index>=MYXA_PATCH_DATA && index<MYXA_PATCH_DATA+MYXA_PARAMETER_COUNT)){
        int result=myxa_patch_receive(&patch_rx,index,word);
        if(result<0){myxa_rejected_commands++;return;}
        if(index==MYXA_PATCH_BEGIN){synth_reset(&voice);note_gate=note_trigger=0;target_gain=0;staged_mask=0;}
        if(result==1){
            int i;
            memcpy(active_patch,patch_rx.values,sizeof(active_patch));
            for(i=0;i<PARAM_COUNT;i++)settings[i]=active_patch[i];
            architecture=(patch_rx.header>>16)&255;
            synth_prepare(&prepared,settings,48000);synth_reset(&voice);
            patch_gain=pow(10.,active_patch[MYXA_OUTPUT_GAIN_DB-1]/20.);
            myxa_output_pan(&stereo,active_patch[MYXA_PAN-1]);
            target_gain=0;note_gate=note_trigger=0;staged_mask=acknowledged=0;age=0;
        }
    }else if(index==MYXA_CMD_NOTE){
        if((word&0xff000000u)!=MYXA_NOTE_TAG){myxa_rejected_commands++;staged_mask=0;return;}
        staged_note=word;staged_mask=1;
    }else if(index==MYXA_CMD_EXPRESSION){
        if(staged_mask!=1 || (word&0xe0000000u)!=0xc0000000u ||
           ((word>>21)&255)!=((staged_note>>16)&255)){myxa_rejected_commands++;staged_mask=0;return;}
        staged_expression=word;staged_mask=3;
    }else if(index==MYXA_CMD_COMMIT){
        if(staged_mask!=3 || word!=myxa_checksum(staged_note,staged_expression)){
            myxa_rejected_commands++;staged_mask=0;return;
        }
        staged_mask=0;
        /* Retries acknowledge the same state without retriggering or reviving a timed-out note. */
        if(staged_note==acknowledged)return;
        if(acknowledged && age<MYXA_TIMEOUT_SAMPLES){
            unsigned delta=((staged_note>>16)-(acknowledged>>16))&255;
            if(delta==0 || delta>=128){myxa_rejected_commands++;return;}
        }
        acknowledged=staged_note;age=0;
        if((staged_note&(1u<<14)) && ((staged_note>>7)&127)){
            float bend=((int)(staged_expression&16383)-8192)*(2.0f/8192);
            note_pitch=440*exp2f(((float)(staged_note&127)-69+bend)/12);
            note_velocity=(float)((staged_note>>7)&127)/127;
            target_gain=pow((double)((staged_note>>7)&127)/127,.7)*patch_gain;
            note_gate=1;
            if(staged_note&(1u<<15))note_trigger=1;
        }else{note_gate=0;note_trigger=0;if(staged_note&(1u<<15)){synth_reset(&voice);target_gain=0;stereo.left=stereo.right=0;}} /* Preserve pitch/velocity through the release, as on desktop. */
        {
            double mod=(double)((staged_expression>>14)&127)/127;
            if(settings[MOD_AMOUNT]!=mod)myxa_dry_set_parameter(MOD_AMOUNT,mod);
        }
    }else if(index==MYXA_CMD_MASTER){
        if(myxa_output_master(&stereo,myxa_float(word)))myxa_rejected_commands++;
    }else if(index>=1 && index<=MYXA_OUTPUT_GAIN_DB){
        float decoded;int k=index-1;memcpy(&decoded,&word,sizeof(decoded));
        if(!isfinite(decoded)||decoded<myxa_minimum[k]||decoded>myxa_maximum[k]||
           (myxa_discrete[k] && decoded!=(int)decoded)){myxa_rejected_commands++;return;}
        active_patch[k]=decoded;
        if(index==MYXA_PAN)myxa_output_pan(&stereo,decoded);
        else if(index==MYXA_OUTPUT_GAIN_DB){
            patch_gain=pow(10.,decoded/20.);
            target_gain=pow((double)note_velocity,.7)*patch_gain;
        }else myxa_dry_set_parameter(k,decoded);
    }else myxa_rejected_commands++;
}
int32_t module_get_param(uint16_t index){
    int32_t value=0;if(index==MYXA_PATCH_ACK)return (int32_t)patch_rx.ack;
    if(index==MYXA_CMD_ACK)return (int32_t)acknowledged;
    if(index==MYXA_CMD_MASTER){int32_t bits;memcpy(&bits,&stereo.master,4);return bits;}
    if(index>=1 && index<=MYXA_OUTPUT_GAIN_DB){float f=index<=PARAM_COUNT?(float)settings[index-1]:active_patch[index-1];memcpy(&value,&f,sizeof(value));}return value;
}
uint32_t module_get_param_count(void){return MYXA_OUTPUT_GAIN_DB;}
void module_get_param_name(uint16_t index,char *text){(void)index;text[0]=0;}
