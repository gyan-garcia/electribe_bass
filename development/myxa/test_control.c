#include <assert.h>
#include "control.h"
int main(void){
 MyxaNotes s;int i;uint32_t w;myxa_notes_init(&s);
 myxa_note(&s,0,36,100,1);myxa_note(&s,16,48,90,1);assert(s.count==2);
 myxa_note(&s,16,48,0,0);assert(s.count==1&&s.held[0].note==36);
 myxa_note(&s,0,36,110,1);assert(s.count==1&&s.held[0].velocity==110);
 myxa_cc(&s,0,64,127);myxa_note(&s,0,36,0,0);assert(s.count==1&&!s.held[0].down);
 myxa_note(&s,16,36,100,1);myxa_cc(&s,0,64,0);assert(s.count==1&&s.held[0].source==16);
 myxa_note(&s,1,50,100,1);myxa_channel(&s,2);assert(s.count==1);
 myxa_note(&s,1,60,100,1);assert(s.count==1);
 myxa_note(&s,2,60,100,1);assert(s.count==2);
 myxa_cc(&s,2,123,0);assert(s.count==1);
 myxa_note(&s,16,36,0,0);assert(s.count==0);
 myxa_note(&s,16,36,0,0);assert(s.count==0);
 myxa_channel(&s,-1);
 for(i=0;i<33;i++)myxa_note(&s,0,i,100,1);
 assert(s.count==1&&s.held[0].note==32);
 w=myxa_snapshot(&s,1);assert((w&0xff000000u)==MYXA_NOTE_TAG&&(w&127)==32&&(w&(1u<<15)));
 myxa_panic(&s);assert(!(myxa_snapshot(&s,0)&(1u<<14)));
 myxa_note(&s,0,36,100,1);s.legato=1;
 assert(!myxa_retrigger(&s,36,1));s.legato=0;assert(myxa_retrigger(&s,36,1));
 myxa_bend(&s,0,16383);assert(s.bend[0]==8191);
 myxa_cc(&s,0,1,99);assert(s.mod==99);
 myxa_cc(&s,0,121,0);assert(s.bend[0]==0&&s.mod==99);
 myxa_cc(&s,0,120,0);assert(s.count==0);
 assert((myxa_expression(&s)&16383)==8192);
 return 0;
}
