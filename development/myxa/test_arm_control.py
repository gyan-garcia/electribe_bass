"""Exercise real ARM callback/retry code using a deterministic fake clock/link."""
from pathlib import Path
import tempfile,subprocess
HERE=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as folder:
    p=Path(folder)
    (p/'freetribe.h').write_text('''#include <stdint.h>
#include <stdbool.h>
#include <string.h>
typedef int t_status;
typedef struct {unsigned deadline;} t_delay_state;
static unsigned clock_us,sets;
#define SUCCESS 0
#define EVT_CHAN_NOTE_ON 1
#define EVT_CHAN_NOTE_OFF 2
#define EVT_CHAN_CONTROL_CHANGE 3
#define EVT_CHAN_PITCH_BEND 4
#define TRIGGER_EVENT 1
#define KNOB_EVENT 2
#define ENCODER_EVENT 3
#define BUTTON_EVENT 4
static void ft_start_delay(t_delay_state *s,unsigned delay){s->deadline=clock_us+delay;}
static bool ft_delay(t_delay_state *s){return clock_us>=s->deadline;}
static void ft_set_module_param(int m,int p,int32_t v){(void)m;(void)p;(void)v;sets++;}
static void ft_get_module_param(int m,int p){(void)m;(void)p;}
#define ft_register_midi_callback(a,b) ((void)(a),(void)(b))
#define ft_register_panel_callback(a,b) ((void)(a),(void)(b))
#define ft_register_dsp_callback(a,b,c) ((void)(a),(void)(b),(void)(c))
''')
    (p/'ft_error.h').write_text('')
    (p/'svc_dsp.h').write_text('#define MSG_TYPE_MODULE 0\n#define MODULE_PARAM_VALUE 2\n#define MSG_TYPE_SYSTEM 1\n#define SYSTEM_PROFILE 6\n#define svc_dsp_get_profile() ((void)0)\n')
    (p/'myxa_control.inc').write_text('#include "'+str(HERE/'control.h')+'"\n#include "'+str(HERE/'transport.h')+'"\n#include "'+str(HERE/'patch_transfer.h')+'"\n')
    (p/'myxa_panel.inc').write_text('#include "'+str(HERE/'panel_ui.h')+'"\n')
    (p/'test.c').write_text('#include <assert.h>\n#include "'+str(HERE/'arm_probe_app.c')+'"\n'+'''
void myxa_screen_init(void){}
void myxa_screen_draw(const char*a,const char*b,const char*c,const char*d){(void)a;(void)b;(void)c;(void)d;}
static void finish_patch(void){
 int guard=0;while(patch_busy){assert(++guard<60);app_run();ack(0,MYXA_PATCH_ACK,patch_expected);}
}
int main(void){
 uint32_t original;unsigned sent;
 app_init();finish_patch();sets=0;app_run();assert(awaiting&&sets==3);
 ack(0,MYXA_CMD_ACK,tx_note);assert(!awaiting);
 note_on(0,36,100);app_run();assert(awaiting&&(tx_note&(1u<<15)));original=tx_note;
 clock_us+=50000;app_run();assert(retries==1&&tx_note==original);
 ack(0,MYXA_CMD_ACK,0);assert(awaiting);
 ack(0,MYXA_CMD_ACK,original);assert(!awaiting);
 myxa_set_legato(1);note_on(0,48,100);app_run();assert(!(tx_note&(1u<<15)));
 ack(0,MYXA_CMD_ACK,tx_note);
 bend(0,127,127);cc(0,1,127);app_run();assert((tx_expression&16383)==16383);
 assert(((tx_expression>>14)&127)==127);ack(0,MYXA_CMD_ACK,tx_note);
 myxa_set_legato(0);note_off(0,48,0);app_run();assert((tx_note&127)==36&&(tx_note&(1u<<15)));
 ack(0,MYXA_CMD_ACK,tx_note);
 myxa_set_midi_channel(2);app_run();ack(0,MYXA_CMD_ACK,tx_note);
 note_on(0,60,100);assert(notes.count==0);
 pad(0,100,1);pad(0,110,1);assert(notes.count==1);
 pad_base=48;pad(0,0,0);assert(notes.count==0);
 note_on(1,60,100);app_run();
 for(int i=0;i<5;i++){clock_us+=50000;app_run();}
 assert(notes.count==0&&!(tx_note&(1u<<14)));
 ack(0,MYXA_CMD_ACK,tx_note);sent=sets;
 clock_us+=200000;app_run();assert(sets==sent+3); /* periodic complete refresh */
 ack(0,MYXA_CMD_ACK,tx_note);
 panel_encoder(0,1);assert(browse_patch==0);
 panel_button(0x09,1);assert(patch_busy);finish_patch();assert(current_patch==0&&!edited);
 float before=edit_values[MYXA_RESONANCE-1];
 myxa_panel_pot(0,255);assert(edit_values[MYXA_RESONANCE-1]==before&&!edited);
 myxa_panel_pot(0,0);assert(pickup[0]&&edited);
 panel_encoder(0,1);panel_button(0x09,1);assert(confirm_discard&&!patch_busy);
 panel_button(0x0d,1);assert(!confirm_discard&&browse_patch==current_patch);
 panel_encoder(0,1);panel_button(0x09,1);panel_button(0x09,1);assert(patch_busy);
 finish_patch();assert(current_patch==1&&!edited&&!pickup[0]);
 panel_encoder(2,1);assert(edited&&param_dirty[MYXA_CUTOFF_HZ-1]);
 panel_button(0x0a,1);panel_knob_shifted(0,255);panel_knob_shifted(0,0);
 assert(pickup[3]&&edit_values[MYXA_PAN-1]==-1);
 panel_button(0x0a,0);assert(!pickup[4]);
 panel_knob_shifted(0,0);panel_knob_shifted(0,255);
 assert(pickup[4]&&edit_values[MYXA_OUTPUT_GAIN_DB-1]==24);
 panel_button(0x0a,0);
 panel_knob_shifted(0x06,0);panel_knob_shifted(0x06,255);
 assert(edited&&edit_values[MYXA_ATTACK_S-1]==3);
 panel_button(0x20,1);assert(panel_filter_envelope&&!pickup[7]);
 panel_knob_shifted(0x06,0);panel_knob_shifted(0x06,255);
 assert(edit_values[MYXA_FILTER_ATTACK_S-1]==3);
 panel_knob_shifted(0x08,0);panel_knob_shifted(0x08,255);
 assert(edit_values[MYXA_FILTER_DECAY_S-1]==5);
 panel_knob_shifted(0x02,0);panel_knob_shifted(0x02,255);assert(edit_values[MYXA_GLIDE_S-1]==2);
 panel_knob_shifted(0x0a,0);panel_knob_shifted(0x0a,255);assert(edit_values[MYXA_LFO_RATE_HZ-1]==200);
 panel_knob_shifted(0x05,0);panel_knob_shifted(0x05,255);assert(notes.mod==127);
 panel_encoder(1,1);assert(edit_values[MYXA_OSC1_WAVE-1]>=0&&edit_values[MYXA_OSC1_WAVE-1]<=5);
 myxa_set_midi_channel(0);panel_button(0x0a,1);panel_encoder(0,1);assert(notes.channel==0&&panel_status==1);
 pad(0,100,1);int pressed=pad_notes[0];panel_encoder(1,1);assert(pad_base>pressed&&panel_status==2);
 pad(0,0,0);assert(notes.count==0);
 for(int j=0;j<20;j++){panel_encoder(1,1);}
 assert(pad_base==108);
 for(int j=0;j<20;j++){panel_encoder(1,-1);}
 assert(pad_base==0);
 pad(0,100,1);panel_button(0x02,1);assert(notes.count==0&&pending_trigger==1&&!awaiting);
 app_run();assert((tx_note&(1u<<15))&&!(tx_note&(1u<<14)));
 profile_report(1000,500);assert(myxa_profile_reports==1&&myxa_profile_peak_permille==500);
 profile_report(1000,1100);assert(myxa_profile_observed_overruns==1&&myxa_profile_peak_permille==1100);
 profile_report(0,0);assert(myxa_profile_reports==2);
 return 0;
}
''')
    subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-I'+folder,str(p/'test.c'),'-lm','-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
print('ARM retry/ack, recovery, refresh, MIDI expression, legato and pad tests passed.')
