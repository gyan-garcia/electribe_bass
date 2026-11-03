/* Control integration probe: DSP outputs remain muted. */
#include "freetribe.h"
#include "ft_error.h"
#include "myxa_control.inc"
#include "svc_dsp.h"
static MyxaNotes notes;
static int8_t pad_notes[16];
static int pad_base=36;
static int dirty, pending_trigger, awaiting,retries;
static uint32_t tx_note,tx_expression;
static t_delay_state retry_timer,refresh_timer,profile_timer;
/* Polled observations only: these are not a worst-case per-frame profile. */
volatile uint32_t myxa_profile_period,myxa_profile_cycles,myxa_profile_peak_permille;
volatile uint32_t myxa_profile_reports,myxa_profile_observed_overruns;
static void profile_report(uint32_t period,uint32_t cycles){
    uint32_t ratio;
    myxa_profile_period=period;myxa_profile_cycles=cycles;
    if(!period)return;
    ratio=(uint32_t)(((uint64_t)cycles*1000)/period);
    if(ratio>myxa_profile_peak_permille)myxa_profile_peak_permille=ratio;
    myxa_profile_reports++;
    if(cycles>=period)myxa_profile_observed_overruns++;
}
static void publish(int trigger){dirty=1;pending_trigger|=trigger;}
void myxa_set_midi_channel(int channel);
static void myxa_pad_octave(int delta){
    int next=pad_base+(delta>0?12:-12);
    if(next<0)next=0;
    if(next>108)next=108;
    pad_base=next;
}
static void myxa_panel_panic(void){
    myxa_panic(&notes);memset(pad_notes,-1,sizeof(pad_notes));
    pending_trigger=1;dirty=1;awaiting=0;retries=0;
}
#include "myxa_panel.inc"
static void note_on(char c,char n,char v){
    if(patch_busy||patch_failed)return;
    int before=myxa_active_key(&notes);
    if(!myxa_accept(&notes,(uint8_t)c))return;
    myxa_note(&notes,(uint8_t)c,(uint8_t)n,(uint8_t)v,1);
    publish(myxa_retrigger(&notes,before,v!=0));
}
static void note_off(char c,char n,char v){
    if(patch_busy||patch_failed)return;
    int before=myxa_active_key(&notes);(void)v;
    myxa_note(&notes,(uint8_t)c,(uint8_t)n,0,0);publish(myxa_retrigger(&notes,before,0));
}
static void cc(char c,char k,char v){
    if(patch_busy||patch_failed)return;
    myxa_cc(&notes,(uint8_t)c,(uint8_t)k,(uint8_t)v);
    if(k==120 && myxa_accept(&notes,(uint8_t)c))memset(pad_notes,-1,sizeof(pad_notes));
    if(k==120&&myxa_accept(&notes,(uint8_t)c))myxa_panel_panic();
    else publish(0); /* Pedal fallback does not retrigger. */
}
static void bend(char c,char low,char high){if(patch_busy||patch_failed)return;myxa_bend(&notes,(uint8_t)c,((uint8_t)high<<7)|(uint8_t)low);publish(0);}
void myxa_set_legato(int enabled){notes.legato=enabled!=0;}
static void ack(uint16_t module,uint16_t index,uint32_t value){
    if(module==0)patch_ack(index,value);
    if(module==0 && index==MYXA_CMD_ACK && awaiting && value==tx_note){awaiting=0;retries=0;}
}
static void transmit(void){
    ft_set_module_param(0,MYXA_CMD_NOTE,(int32_t)tx_note);
    ft_set_module_param(0,MYXA_CMD_EXPRESSION,(int32_t)tx_expression);
    ft_set_module_param(0,MYXA_CMD_COMMIT,(int32_t)myxa_checksum(tx_note,tx_expression));
    ft_get_module_param(0,MYXA_CMD_ACK);
    ft_start_delay(&retry_timer,50000);
}
static void pad(uint8_t id,uint8_t velocity,bool down){
    if(patch_busy||patch_failed)return;
    int before=myxa_active_key(&notes);
    int i=id<16 ? id : (int)id-0x11; /* normal indices or continuous-mode IDs */
    if(i<0||i>=16)return;
    if(down){
        if(pad_notes[i]>=0)return; /* continuous pressure is not a retrigger */
        pad_notes[i]=pad_base+i;
        myxa_note(&notes,16,pad_notes[i],velocity ? (velocity>127 ? 127:velocity):100,1);
    }else if(pad_notes[i]>=0){myxa_note(&notes,16,pad_notes[i],0,0);pad_notes[i]=-1;}
    publish(myxa_retrigger(&notes,before,down));
}
/* API for upcoming settings UI; 0=Omni, 1..16=MIDI channel. */
void myxa_set_midi_channel(int channel){if(channel<0||channel>16)return;myxa_channel(&notes,channel-1);publish(0);}
t_status app_init(void){
    myxa_notes_init(&notes);memset(pad_notes,-1,sizeof(pad_notes));
    ft_register_midi_callback(EVT_CHAN_NOTE_ON,note_on);
    ft_register_midi_callback(EVT_CHAN_NOTE_OFF,note_off);
    ft_register_midi_callback(EVT_CHAN_CONTROL_CHANGE,cc);
    ft_register_midi_callback(EVT_CHAN_PITCH_BEND,bend);
    ft_register_dsp_callback(MSG_TYPE_MODULE,MODULE_PARAM_VALUE,ack);
    ft_register_dsp_callback(MSG_TYPE_SYSTEM,SYSTEM_PROFILE,profile_report);
    ft_start_delay(&profile_timer,100000);
    notes.mod=0; /* Moog Res factory mod amount is zero. */
    ft_start_delay(&refresh_timer,200000);
    ft_register_panel_callback(TRIGGER_EVENT,pad);
    ft_register_panel_callback(KNOB_EVENT,panel_knob_shifted);
    ft_register_panel_callback(ENCODER_EVENT,panel_encoder);
    ft_register_panel_callback(BUTTON_EVENT,panel_button);
    memcpy(edit_values,myxa_factory_patches[2].values,sizeof(edit_values));
    myxa_screen_init();start_patch(2);
    publish(0);return SUCCESS;
}
void app_run(void){
    panel_service();
    if(patch_busy||patch_failed)return;
    if(ft_delay(&profile_timer)){svc_dsp_get_profile();ft_start_delay(&profile_timer,100000);}
    if(awaiting){
        if(ft_delay(&retry_timer)){
            if(++retries>=5){
                myxa_panic(&notes);memset(pad_notes,-1,sizeof(pad_notes));
                pending_trigger=0;dirty=1;awaiting=0;retries=0;
            }else transmit();
        }
    }
    if(!awaiting && (dirty || ft_delay(&refresh_timer))){
        tx_note=myxa_snapshot(&notes,pending_trigger);tx_expression=myxa_expression(&notes);
        pending_trigger=0;dirty=0;awaiting=1;
        transmit();ft_start_delay(&refresh_timer,200000);
    }
}
