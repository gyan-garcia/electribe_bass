#ifndef MYXA_CONTROL_H
#define MYXA_CONTROL_H
#include <stdint.h>
#include <string.h>
#define MYXA_HELD_MAX 32
#define MYXA_CMD_NOTE 0x7000
#define MYXA_NOTE_TAG 0xa1000000u
/* MIDI channels 0..15, pads source 16. Repeated note-on replaces its entry. */
typedef struct { uint8_t source,note,velocity,down; } MyxaHeld;
typedef struct {
    MyxaHeld held[MYXA_HELD_MAX];
    uint8_t count,sustain[16],sequence;
    int16_t bend[16];
    uint8_t mod,legato;
    int8_t channel; /* -1 Omni */
} MyxaNotes;
static inline void myxa_notes_init(MyxaNotes *s){memset(s,0,sizeof(*s));s->channel=-1;}
static inline void myxa_remove(MyxaNotes *s,int i){
    memmove(s->held+i,s->held+i+1,(s->count-i-1)*sizeof(MyxaHeld));s->count--;
}
static inline void myxa_panic(MyxaNotes *s){s->count=0;memset(s->sustain,0,sizeof(s->sustain));memset(s->bend,0,sizeof(s->bend));}
static inline int myxa_accept(MyxaNotes *s,int source){return source==16 || (source>=0 && source<16 && (s->channel<0 || source==s->channel));}
static inline void myxa_note(MyxaNotes *s,int source,int note,int velocity,int on){
    int i;
    if(!myxa_accept(s,source)||note<0||note>127||velocity<0||velocity>127)return;
    if(!velocity)on=0;
    for(i=0;i<s->count;i++)if(s->held[i].source==source && s->held[i].note==note)break;
    if(!on){
        if(i<s->count){if(source<16 && s->sustain[source])s->held[i].down=0;else myxa_remove(s,i);}
        return;
    }
    if(i<s->count)myxa_remove(s,i);
    if(s->count==MYXA_HELD_MAX)myxa_panic(s);
    s->held[s->count++]=(MyxaHeld){source,note,velocity,1};
}
static inline void myxa_cc(MyxaNotes *s,int channel,int cc,int value){
    int i;
    if(channel<0||channel>15||!myxa_accept(s,channel))return;
    if(cc==64){
        s->sustain[channel]=value>=64;
        if(value<64)for(i=s->count-1;i>=0;i--)if(s->held[i].source==channel&&!s->held[i].down)myxa_remove(s,i);
    }else if(cc==1){s->mod=value;}else if(cc==121){
        s->bend[channel]=0;myxa_cc(s,channel,64,0);
    }else if(cc==120){myxa_panic(s);
    }else if(cc==123){
        for(i=s->count-1;i>=0;i--)if(s->held[i].source==channel){
            myxa_remove(s,i);
        }
        s->sustain[channel]=0;
    }
}
static inline void myxa_channel(MyxaNotes *s,int channel){
    int i;if(channel < -1 || channel>15)return;
    for(i=s->count-1;i>=0;i--)if(s->held[i].source<16)myxa_remove(s,i);
    memset(s->sustain,0,sizeof(s->sustain));memset(s->bend,0,sizeof(s->bend));s->channel=channel;
}
static inline int myxa_active_key(MyxaNotes *s){
    return s->count ? s->held[s->count-1].source*128+s->held[s->count-1].note : -1;
}
static inline int myxa_retrigger(MyxaNotes *s,int before,int note_on){
    int after=myxa_active_key(s);
    return after>=0 && (note_on ? (before<0 || !s->legato) : (after!=before && !s->legato));
}
static inline void myxa_bend(MyxaNotes *s,int channel,int value){
    if(channel>=0&&channel<16&&myxa_accept(s,channel)&&value>=0&&value<=16383)s->bend[channel]=value-8192;
}
static inline uint32_t myxa_expression(MyxaNotes *s){
    int bend=0;
    if(s->count && s->held[s->count-1].source<16)bend=s->bend[s->held[s->count-1].source];
    return 0xc0000000u|((uint32_t)s->sequence<<21)|((uint32_t)s->mod<<14)|(uint32_t)(bend+8192);
}
static inline uint32_t myxa_snapshot(MyxaNotes *s,int trigger){
    uint32_t word=MYXA_NOTE_TAG | ((uint32_t)(++s->sequence)<<16);
    if(s->count){MyxaHeld *n=&s->held[s->count-1];word|=n->note|((uint32_t)n->velocity<<7)|(1u<<14);if(trigger)word|=1u<<15;}
    if(trigger && !s->count)word|=1u<<15; /* Empty triggered snapshot means hard panic. */
    return word;
}
#endif
