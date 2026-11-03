#ifndef MYXA_PANEL_UI_H
#define MYXA_PANEL_UI_H
#include "text.h"
#include <stdlib.h>
/* Renderer implemented separately so panel logic is host-testable. */
void myxa_screen_init(void);
void myxa_screen_draw(const char *line1,const char *line2,const char *line3,const char *line4);
static float edit_values[MYXA_PARAMETER_COUNT],transfer_values[MYXA_PARAMETER_COUNT];
static int current_patch=2,browse_patch=2,edited,screen_dirty=1,confirm_discard;
static int patch_busy,patch_wait,patch_step,patch_retries,patch_failed;
static uint16_t patch_serial;
static uint32_t patch_header,patch_expected,patch_word;
static uint16_t patch_command;
static t_delay_state patch_timer,screen_timer;
static int panel_status; /* 1 MIDI, 2 pad octave; 0 parameter */
static int selected_param=MYXA_CUTOFF_HZ-1;
static int pickup[12],last_raw[12]={-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1};
static int param_dirty[MYXA_PARAMETER_COUNT],param_wait,param_index,param_retries;
static uint32_t param_word;
static t_delay_state param_timer;
static const int panel_params[12]={MYXA_RESONANCE-1,MYXA_FILTER_ENV_OCTAVES-1,MYXA_MIXER_DRIVE-1,MYXA_PAN-1,MYXA_OUTPUT_GAIN_DB-1,MYXA_ATTACK_S-1,MYXA_AMP_DECAY_S-1,MYXA_FILTER_ATTACK_S-1,MYXA_FILTER_DECAY_S-1,MYXA_GLIDE_S-1,MYXA_LFO_RATE_HZ-1,MYXA_MOD_AMOUNT-1};
static const char *parameter_name(int i){
    if(i==MYXA_CUTOFF_HZ-1)return "Cutoff Hz";
    if(i==MYXA_RESONANCE-1)return "Resonance";
    if(i==MYXA_FILTER_ENV_OCTAVES-1)return "Filter EG oct";
    if(i==MYXA_MIXER_DRIVE-1)return "Mixer drive";
    if(i==MYXA_PAN-1)return "Pan";
    if(i==MYXA_OUTPUT_GAIN_DB-1)return "Patch dB";
    if(i==MYXA_ATTACK_S-1)return "Amp attack s";
    if(i==MYXA_AMP_DECAY_S-1)return "Amp decay s";
    if(i==MYXA_FILTER_ATTACK_S-1)return "Filt attack s";
    if(i==MYXA_FILTER_DECAY_S-1)return "Filt decay s";
    if(i==MYXA_GLIDE_S-1)return "Glide s";
    if(i==MYXA_LFO_RATE_HZ-1)return "LFO Hz";
    if(i==MYXA_MOD_AMOUNT-1)return "Mod amount";
    if(i==MYXA_OSC1_WAVE-1)return "Osc1 waveform";
    return "Parameter";
}
static int panel_needs_pickup(void){
    int i;for(i=0;i<12;i++)if(selected_param==panel_params[i]&&!pickup[i])return 1;return 0;
}
static void panel_draw(void){
    char name[22],value[22];int n=(int)(edit_values[selected_param]*100);
    if(!screen_dirty||!ft_delay(&screen_timer))return;
    ft_start_delay(&screen_timer,100000);
    name[0]=0;myxa_append(name,sizeof(name),myxa_factory_patches[current_patch].name);
    if(edited)myxa_append(name,sizeof(name)," *");
    myxa_value_text(value,sizeof(value),parameter_name(selected_param),n);
    if(panel_status){
        value[0]=0;
        if(panel_status==1){
            myxa_append(value,sizeof(value),"MIDI: ");
            if(notes.channel<0)myxa_append(value,sizeof(value),"Omni");
            else myxa_unsigned(value,sizeof(value),(unsigned)notes.channel+1);
        }else{myxa_append(value,sizeof(value),"Pad base MIDI ");myxa_unsigned(value,sizeof(value),pad_base);}
    }
    myxa_screen_draw(name,patch_failed?"Load failed: Enter":patch_busy?"Loading...":confirm_discard?"Discard? Enter/Exit":myxa_factory_patches[browse_patch].name,
                     value,
        panel_needs_pickup() ? "Pickup / MUTED" : "MUTED / FX pending");
    screen_dirty=0;
}
static void start_patch(int index){
    if(index<0||index>2||patch_busy)return;
    memcpy(transfer_values,myxa_factory_patches[index].values,sizeof(transfer_values));
    browse_patch=index;patch_header=0xb1000000u|((uint32_t)myxa_factory_patches[index].engine<<16)|++patch_serial;
    patch_busy=1;patch_wait=patch_step=patch_retries=patch_failed=0;confirm_discard=0;
    myxa_panic(&notes);memset(pad_notes,-1,sizeof(pad_notes));pending_trigger=0;awaiting=0;dirty=0;
    memset(param_dirty,0,sizeof(param_dirty));param_wait=0;screen_dirty=1;
}
static void patch_ack(uint16_t index,uint32_t value){
    if(index==MYXA_PATCH_ACK && patch_busy && patch_wait && value==patch_expected){
        patch_wait=0;patch_retries=0;patch_step++;
        if(patch_step==MYXA_PARAMETER_COUNT+2){
            patch_busy=0;current_patch=browse_patch;memcpy(edit_values,transfer_values,sizeof(edit_values));
            edited=0;memset(pickup,0,sizeof(pickup));memset(last_raw,-1,sizeof(last_raw));
            notes.mod=(uint8_t)(edit_values[MYXA_MOD_AMOUNT-1]*127);pending_trigger=0;
            publish(0);screen_dirty=1;
        }
    }
    if(param_wait && index==param_index+1 && value==param_word){param_wait=0;param_retries=0;}
}
static void patch_send(void){
    ft_set_module_param(0,patch_command,(int32_t)patch_word);ft_get_module_param(0,MYXA_PATCH_ACK);
    patch_wait=1;ft_start_delay(&patch_timer,50000);
}
static void panel_service(void){
    int i;
    if(patch_busy){
        if(patch_wait){
            if(ft_delay(&patch_timer)){
                if(++patch_retries>=5){patch_busy=0;patch_failed=1;screen_dirty=1;}else patch_send();
            }
        }else{
            if(patch_step==0){patch_command=MYXA_PATCH_BEGIN;patch_word=patch_header;}
            else if(patch_step<=MYXA_PARAMETER_COUNT){patch_command=MYXA_PATCH_DATA+patch_step-1;patch_word=myxa_bits(transfer_values[patch_step-1]);}
            else{patch_command=MYXA_PATCH_COMMIT;patch_word=myxa_patch_crc(patch_header,transfer_values);}
            patch_expected=myxa_checksum(patch_command,patch_word);patch_send();
        }
    }else if(!patch_failed){
        if(param_wait && ft_delay(&param_timer)){
            if(++param_retries>=5){param_wait=0;patch_failed=1;myxa_panic(&notes);publish(0);screen_dirty=1;}
            else{ft_set_module_param(0,param_index+1,(int32_t)param_word);ft_get_module_param(0,param_index+1);ft_start_delay(&param_timer,50000);}
        }
        if(!param_wait)for(i=0;i<MYXA_PARAMETER_COUNT;i++)if(param_dirty[i]){
            param_index=i;param_word=myxa_bits(edit_values[i]);param_dirty[i]=0;param_wait=1;param_retries=0;
            ft_set_module_param(0,i+1,(int32_t)param_word);ft_get_module_param(0,i+1);ft_start_delay(&param_timer,50000);break;
        }
    }
    panel_draw();
}
static void panel_edit(int id,float value){
    if(patch_busy||patch_failed||!myxa_valid(id,value))return;
    if(id==MYXA_MOD_AMOUNT-1){notes.mod=(uint8_t)(value*127);value=notes.mod/127.0f;publish(0);}
    panel_status=0;selected_param=id;edit_values[id]=value;param_dirty[id]=1;edited=1;screen_dirty=1;
}
/* Normalized pot API is independent of unverified hardware event IDs. */
static float panel_pot_value(int slot,int raw){
    int id=panel_params[slot];float x;
    if(raw<0)raw=0;
    if(raw>255)raw=255;
    x=raw/255.0f;
    if(slot>=5 && slot<=10)x*=x; /* Fine adjustment near short/slow end. */
    return myxa_minimum[id]+x*(myxa_maximum[id]-myxa_minimum[id]);
}
void myxa_panel_pot(int slot,uint8_t raw){
    int id,previous;float target,current;
    if(slot<0||slot>11||patch_busy||patch_failed)return;
    id=panel_params[slot];previous=last_raw[slot];last_raw[slot]=raw;
    target=edit_values[id];current=panel_pot_value(slot,raw);
    if(!pickup[slot] && ((target>=panel_pot_value(slot,(int)raw-2)&&target<=panel_pot_value(slot,(int)raw+2)) ||
       (previous>=0 && (panel_pot_value(slot,previous)-target)*(current-target)<=0)))pickup[slot]=1;
    panel_status=0;selected_param=id;screen_dirty=1;
    if(pickup[slot])panel_edit(id,current);
}
static int panel_filter_envelope;
static void panel_knob(uint8_t id,uint8_t raw){
    if(id==0x00)myxa_panel_pot(4,raw);
    else if(id==0x03)myxa_panel_pot(0,raw);
    else if(id==0x04)myxa_panel_pot(1,raw);
    else if(id==0x02)myxa_panel_pot(9,raw);
    else if(id==0x06)myxa_panel_pot(panel_filter_envelope?7:5,raw);
    else if(id==0x08)myxa_panel_pot(panel_filter_envelope?8:6,raw);
    else if(id==0x0a)myxa_panel_pot(10,raw);
    else if(id==0x05)myxa_panel_pot(11,raw);
    /* Sample Edit ID unverified: use Shift + EG Int for drive until audited. */
}
static int panel_shift;
static void panel_encoder(uint8_t id,int8_t delta){
    if(!delta||patch_busy)return;
    if(id==0 && panel_shift){
        int channel=notes.channel+1+(delta>0?1:-1);
        if(channel<0)channel=16;
        if(channel>16)channel=0;
        myxa_set_midi_channel(channel);panel_status=1;screen_dirty=1;return;
    }
    if(id==1 && panel_shift){myxa_pad_octave(delta);panel_status=2;screen_dirty=1;return;}
    if(id==0){browse_patch=(browse_patch+(delta>0?1:2))%3;confirm_discard=0;screen_dirty=1;}
    if(id==1 && !panel_shift){
        int v=(int)edit_values[MYXA_OSC1_WAVE-1]+(delta>0?1:-1);
        if(v<0)v=5;
        if(v>5)v=0;
        panel_edit(MYXA_OSC1_WAVE-1,(float)v);
    }
    if(id==2){
        float v=edit_values[MYXA_CUTOFF_HZ-1]*powf(2.0f,delta/24.0f);
        if(v<20)v=20;
        if(v>18000)v=18000;
        panel_edit(MYXA_CUTOFF_HZ-1,v);
    }
}
static void panel_knob_shifted(uint8_t id,uint8_t raw){
    if(id==0x00&&panel_shift)myxa_panel_pot(3,raw);
    else if(id==0x04&&panel_shift)myxa_panel_pot(2,raw);else panel_knob(id,raw);
}
static void panel_button(uint8_t id,bool down){
    if(id==0x0a){panel_shift=down;pickup[1]=pickup[2]=0;last_raw[1]=last_raw[2]=-1;pickup[3]=pickup[4]=0;last_raw[3]=last_raw[4]=-1;return;}
    if(down && id==0x02 && panel_shift){myxa_panel_panic();screen_dirty=1;return;}
    if(!down||patch_busy)return;
    if(id==0x20){
        int i;panel_filter_envelope=!panel_filter_envelope;
        for(i=5;i<=8;i++){pickup[i]=0;last_raw[i]=-1;}
        selected_param=panel_filter_envelope?MYXA_FILTER_ATTACK_S-1:MYXA_ATTACK_S-1;screen_dirty=1;
    }
    if(id==0x0d){browse_patch=current_patch;confirm_discard=0;screen_dirty=1;}
    if(id==0x09){
        if(edited && !confirm_discard && !patch_failed){confirm_discard=1;screen_dirty=1;}
        else start_patch(browse_patch);
    }
}
#endif
